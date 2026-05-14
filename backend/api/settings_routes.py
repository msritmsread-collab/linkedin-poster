"""
Settings API — LinkedIn credentials, schedule, and topic preferences.
All configuration is stored in SQLite (no .env required).

GET  /api/settings          — get current settings (token masked)
PUT  /api/settings          — save settings, reschedule if needed
POST /api/settings/test     — test LinkedIn API connection
"""

import json
import os
from typing import List, Optional


from fastapi import APIRouter, Depends
from pydantic import BaseModel
import requests

from backend import database as db
from backend.auth import get_current_user
from backend.api.linkedin import _API_VERSION

router = APIRouter()

VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class ReferencePost(BaseModel):
    label: str        # e.g. "Brand Story Example 1"
    text: str         # full post text to use as reference


class SettingsBody(BaseModel):
    linkedin_token: Optional[str] = None
    linkedin_org_id: Optional[str] = None
    linkedin_member_id: Optional[str] = None   # For personal profile mode
    post_mode: Optional[str] = None            # "org" or "personal"
    schedule_days: Optional[List[str]] = None
    schedule_time: Optional[str] = None
    default_topics: Optional[List[str]] = None
    reference_posts: Optional[List[ReferencePost]] = None


def _mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return "" if not token else "****"
    return token[:4] + "****" + token[-4:]


@router.get("/settings")
async def get_settings(_user: dict = Depends(get_current_user)):
    raw = db.get_all_settings()
    return {
        "linkedin_token_masked": _mask_token(raw.get("linkedin_token", "")),
        "linkedin_token_set": bool(raw.get("linkedin_token", "").strip()),
        "linkedin_org_id": raw.get("linkedin_org_id", "6456959"),
        "linkedin_member_id": raw.get("linkedin_member_id", ""),
        "post_mode": raw.get("post_mode", "org"),
        "schedule_days": json.loads(raw.get("schedule_days", '["mon","wed","fri"]')),
        "schedule_time": raw.get("schedule_time", "09:00"),
        "default_topics": json.loads(raw.get("default_topics", "[]")),
        "reference_posts": json.loads(raw.get("reference_posts", "[]")),
    }


@router.put("/settings")
async def save_settings(body: SettingsBody, _user: dict = Depends(get_current_user)):
    changed_schedule = False

    if body.linkedin_token is not None:
        db.set_setting("linkedin_token", body.linkedin_token.strip())

    if body.linkedin_org_id is not None:
        db.set_setting("linkedin_org_id", body.linkedin_org_id.strip())

    if body.linkedin_member_id is not None:
        # Strip full URLs — extract trailing digits only
        import re as _re
        raw_id = body.linkedin_member_id.strip()
        # If it looks like a URL, pull out the numeric suffix
        numeric = _re.search(r'(\d+)\s*/?$', raw_id)
        clean_id = numeric.group(1) if numeric else raw_id
        db.set_setting("linkedin_member_id", clean_id)

    if body.post_mode is not None and body.post_mode in ("org", "personal"):
        db.set_setting("post_mode", body.post_mode)

    if body.schedule_days is not None:
        days = [d.lower() for d in body.schedule_days if d.lower() in VALID_DAYS]
        db.set_setting("schedule_days", json.dumps(days))
        changed_schedule = True

    if body.schedule_time is not None:
        # Validate HH:MM format
        parts = body.schedule_time.strip().split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            db.set_setting("schedule_time", body.schedule_time.strip())
            changed_schedule = True

    if body.default_topics is not None:
        topics = [t.strip() for t in body.default_topics if t.strip()]
        db.set_setting("default_topics", json.dumps(topics))

    if body.reference_posts is not None:
        refs = [{"label": r.label.strip(), "text": r.text.strip()}
                for r in body.reference_posts if r.text.strip()]
        db.set_setting("reference_posts", json.dumps(refs))

    # Trigger scheduler reschedule if schedule changed
    if changed_schedule:
        try:
            from backend.scheduler import reschedule
            reschedule()
        except Exception:
            pass  # Scheduler may not be running in all contexts

    return {"status": "saved", "schedule_updated": changed_schedule}


@router.post("/settings/test")
async def test_linkedin_connection(_user: dict = Depends(get_current_user)):
    """Test the saved LinkedIn token. Works for both org and personal mode."""
    token = db.get_setting("linkedin_token") or ""
    post_mode = db.get_setting("post_mode") or "org"

    if not token.strip():
        return {"ok": False, "error": "No LinkedIn token saved. Please enter your token in Settings."}

    try:
        if post_mode == "personal":
            auth_header = {"Authorization": f"Bearer {token}"}

            # Primary: OpenID Connect userinfo endpoint (requires openid + profile scopes)
            resp = requests.get(
                "https://api.linkedin.com/v2/userinfo",
                headers=auth_header,
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                # 'sub' is the numeric LinkedIn member ID
                member_id = data.get("sub", "")
                name = data.get("name") or data.get("given_name", "")
                return {"ok": True, "name": name or "LinkedIn User", "member_id": member_id, "mode": "personal"}

            # Fallback: legacy /v2/me (works if r_liteprofile scope present)
            resp2 = requests.get(
                "https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName)",
                headers=auth_header,
                timeout=8,
            )
            if resp2.ok:
                data = resp2.json()
                member_id = data.get("id", "")
                name = f"{data.get('localizedFirstName','')} {data.get('localizedLastName','')}".strip()
                return {"ok": True, "name": name or "LinkedIn User", "member_id": member_id, "mode": "personal"}

            if resp.status_code == 401 or resp2.status_code == 401:
                return {"ok": False, "error": "Token is invalid or expired. Please regenerate it."}

            # Token is valid for posting but can't read profile yet
            member_id = db.get_setting("linkedin_member_id") or ""
            return {
                "ok": True,
                "name": "LinkedIn User",
                "member_id": member_id,
                "mode": "personal",
                "note": "Token valid. Add 'Sign In with LinkedIn using OpenID Connect' product to your app, then regenerate token with openid + profile + w_member_social scopes to auto-detect Member ID.",
            }
        else:
            org_id = db.get_setting("linkedin_org_id") or "6456959"
            resp = requests.get(
                f"https://api.linkedin.com/rest/organizations/{org_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "LinkedIn-Version": _API_VERSION,
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                name = data.get("localizedName") or data.get("name", {}).get("localized", {})
                return {"ok": True, "org_name": str(name), "org_id": org_id, "mode": "org"}
            elif resp.status_code == 401:
                return {"ok": False, "error": "Token is invalid or expired. Please re-generate it."}
            elif resp.status_code == 403:
                return {"ok": False, "error": "Token lacks rw_organization_admin scope. Check your LinkedIn app permissions."}
            else:
                return {"ok": False, "error": f"LinkedIn API returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
