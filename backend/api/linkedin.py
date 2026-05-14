"""
LinkedIn API client — supports both company page (org) and personal profile posting.

Org mode   : POST /rest/posts          (Marketing Developer Platform, w_organization_social)
Personal   : POST /v2/ugcPosts         (Share on LinkedIn product, w_member_social)

Image upload:
  Org mode : /rest/images              (versioned API)
  Personal : /v2/assets?action=registerUpload  (legacy API, no version header)

Credentials are read from the SQLite settings table (set via the web UI Settings page).
"""

import os
import requests
from typing import Optional

_BASE_REST  = "https://api.linkedin.com/rest"
_BASE_V2    = "https://api.linkedin.com/v2"
_API_VERSION = "202507"


# ── Settings readers ──────────────────────────────────────────────────────────

def _get_token() -> str:
    try:
        from backend.database import get_setting
        token = get_setting("linkedin_token") or ""
    except Exception:
        token = ""
    return token or os.getenv("LINKEDIN_ACCESS_TOKEN", "")


def _get_org_id() -> str:
    try:
        from backend.database import get_setting
        org_id = get_setting("linkedin_org_id") or ""
    except Exception:
        org_id = ""
    return org_id or os.getenv("LINKEDIN_ORGANIZATION_ID", "6456959")


def _get_member_id() -> str:
    try:
        from backend.database import get_setting
        member_id = get_setting("linkedin_member_id") or ""
    except Exception:
        member_id = ""
    return member_id or os.getenv("LINKEDIN_MEMBER_ID", "")


def _get_post_mode() -> str:
    try:
        from backend.database import get_setting
        mode = get_setting("post_mode") or "org"
    except Exception:
        mode = "org"
    return mode if mode in ("org", "personal") else "org"


def has_token() -> bool:
    return bool(_get_token().strip())


def _org_urn() -> str:
    return f"urn:li:organization:{_get_org_id()}"


def _person_urn() -> str:
    member_id = _get_member_id()
    if not member_id:
        raise EnvironmentError(
            "LinkedIn Member ID not configured. Please go to Settings, "
            "click 'Test LinkedIn Connection', and save your Member ID."
        )
    return f"urn:li:member:{member_id}"


def _author_urn() -> str:
    return _person_urn() if _get_post_mode() == "personal" else _org_urn()


# ── Headers ───────────────────────────────────────────────────────────────────

def _rest_headers(extra: Optional[dict] = None) -> dict:
    """Headers for versioned /rest/* endpoints (org mode)."""
    token = _get_token()
    if not token:
        raise EnvironmentError("LinkedIn token not configured.")
    h = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": _API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _v2_headers(content_type: str = "application/json") -> dict:
    """Headers for legacy /v2/* endpoints (personal mode — no version header)."""
    token = _get_token()
    if not token:
        raise EnvironmentError("LinkedIn token not configured.")
    return {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": content_type,
    }


def _guess_content_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")


# ── Image upload — org mode (/rest/images) ────────────────────────────────────

def _upload_image_org(image_path: str) -> str:
    """Upload image via versioned /rest/images API. Returns image URN."""
    resp = requests.post(
        f"{_BASE_REST}/images?action=initializeUpload",
        headers=_rest_headers(),
        json={"initializeUploadRequest": {"owner": _org_urn()}},
    )
    resp.raise_for_status()
    data = resp.json()
    upload_url = data["value"]["uploadUrl"]
    image_urn  = data["value"]["image"]

    with open(image_path, "rb") as f:
        image_data = f.read()

    requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {_get_token()}",
                 "Content-Type": _guess_content_type(image_path)},
        data=image_data,
    ).raise_for_status()
    return image_urn


# ── Image upload — personal mode (/v2/assets) ─────────────────────────────────

def _upload_image_personal(image_path: str) -> str:
    """Upload image via legacy /v2/assets API. Returns digitalmediaAsset URN."""
    person_urn = _person_urn()

    # Step 1 — register upload
    reg = requests.post(
        f"{_BASE_V2}/assets?action=registerUpload",
        headers=_v2_headers(),
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        },
    )
    reg.raise_for_status()
    reg_data    = reg.json()
    upload_url  = (reg_data["value"]["uploadMechanism"]
                   ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
                   ["uploadUrl"])
    asset_urn   = reg_data["value"]["asset"]

    # Step 2 — binary upload
    with open(image_path, "rb") as f:
        image_data = f.read()

    requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {_get_token()}",
                 "Content-Type": _guess_content_type(image_path)},
        data=image_data,
    ).raise_for_status()

    return asset_urn


# ── Post — org mode (/rest/posts) ────────────────────────────────────────────

def _post_org(content: str, image_path: Optional[str] = None) -> str:
    """Post to LinkedIn company page via versioned /rest/posts API."""
    payload: dict = {
        "author": _org_urn(),
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    if image_path and os.path.exists(image_path):
        image_urn = _upload_image_org(image_path)
        payload["content"] = {
            "media": {"altText": "MS. READ workplace", "id": image_urn}
        }

    resp = requests.post(f"{_BASE_REST}/posts", headers=_rest_headers(), json=payload)
    if not resp.ok:
        raise RuntimeError(f"LinkedIn post failed [{resp.status_code}]: {resp.text}")

    post_id = resp.headers.get("X-RestLi-Id") or resp.headers.get("x-restli-id", "")
    if not post_id:
        try:
            post_id = resp.json().get("id", "unknown")
        except Exception:
            post_id = "unknown"
    return post_id


# ── Post — personal mode (/v2/ugcPosts) ───────────────────────────────────────

def _post_personal(content: str, image_path: Optional[str] = None) -> str:
    """Post to personal LinkedIn profile via legacy /v2/ugcPosts API."""
    person_urn = _person_urn()

    if image_path and os.path.exists(image_path):
        asset_urn = _upload_image_personal(image_path)
        share_content = {
            "shareCommentary": {"text": content},
            "shareMediaCategory": "IMAGE",
            "media": [{
                "status": "READY",
                "description": {"text": ""},
                "media": asset_urn,
                "title": {"text": ""},
            }],
        }
    else:
        share_content = {
            "shareCommentary": {"text": content},
            "shareMediaCategory": "NONE",
        }

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content,
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }

    resp = requests.post(f"{_BASE_V2}/ugcPosts", headers=_v2_headers(), json=payload)
    if not resp.ok:
        raise RuntimeError(f"LinkedIn personal post failed [{resp.status_code}]: {resp.text}")

    post_id = resp.headers.get("X-RestLi-Id") or resp.headers.get("x-restli-id", "")
    if not post_id:
        try:
            post_id = resp.json().get("id", "unknown")
        except Exception:
            post_id = "unknown"
    return post_id


# ── Public interface ──────────────────────────────────────────────────────────

def post_to_linkedin(content: str, image_path: Optional[str] = None) -> str:
    """Post to LinkedIn — routes to org or personal API based on settings."""
    if _get_post_mode() == "personal":
        return _post_personal(content, image_path)
    return _post_org(content, image_path)


def upload_image(image_path: str) -> str:
    """Upload image — routes to correct API based on post mode."""
    if _get_post_mode() == "personal":
        return _upload_image_personal(image_path)
    return _upload_image_org(image_path)


def post_to_linkedin_dryrun(content: str, image_path: Optional[str] = None) -> str:
    """Simulate a post without making any API call."""
    mode = _get_post_mode()
    print("[LinkedIn DRY RUN] Would post:")
    print(f"  Mode: {mode}")
    try:
        print(f"  Author: {_author_urn()}")
    except Exception:
        print("  Author: (not configured)")
    print(f"  Image: {image_path}")
    print(f"  Content ({len(content.split())} words): {content[:120]}...")
    return "dry-run-id-000"
