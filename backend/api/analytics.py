"""
LinkedIn Page Analytics fetcher for MS. READ.

Pulls from LinkedIn REST API:
  - Follower count + growth (organizationalEntityFollowerStatistics)
  - Per-post impressions, likes, comments, shares (organizationalEntityShareStatistics)

Requires scopes: r_organization_social_feed  (part of Marketing Developer Platform)
Results are cached in SQLite and returned even when the API is unavailable.
"""

from typing import Optional


import requests
from fastapi import APIRouter, Depends

from backend import database as db
from backend.api.linkedin import _get_token, _get_org_id, _get_post_mode, _get_member_id, _API_VERSION
from backend.auth import get_current_user

router = APIRouter()


def _li_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "LinkedIn-Version": _API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _org_urn() -> str:
    return f"urn:li:organization:{_get_org_id()}"


def _person_urn() -> str:
    return f"urn:li:person:{_get_member_id()}"


# ── LinkedIn API calls ────────────────────────────────────────────────────────

def fetch_follower_stats() -> Optional[dict]:
    """Fetch current follower count from LinkedIn (org mode only)."""
    if _get_post_mode() == "personal":
        # LinkedIn API does not expose personal profile follower counts
        return {"total": None, "note": "Follower stats not available for personal profiles."}
    try:
        resp = requests.get(
            "https://api.linkedin.com/rest/organizationalEntityFollowerStatistics",
            headers=_li_headers(),
            params={"q": "organizationalEntity", "organizationalEntity": _org_urn()},
            timeout=10,
        )
        if not resp.ok:
            return None
        elements = resp.json().get("elements", [])
        if not elements:
            return None

        el = elements[0]
        total = el.get("totalFollowerCount", 0)
        organic = el.get("organicFollowerCount", 0)
        paid = el.get("paidFollowerCount", 0)

        db.save_follower_snapshot(total=total, organic_gain=organic, paid_gain=paid)
        return {"total": total, "organic": organic, "paid": paid}
    except Exception:
        return None


def fetch_post_stats(linkedin_post_id: str, option_id: Optional[int],
                     angle_name: str) -> Optional[dict]:
    """Fetch impressions + engagement for a single post. Mode-aware."""
    try:
        if _get_post_mode() == "personal":
            # Personal profile: use memberShareStatistics
            resp = requests.get(
                "https://api.linkedin.com/rest/memberShareStatistics",
                headers=_li_headers(),
                params={"q": "member", "shares[0]": linkedin_post_id},
                timeout=10,
            )
        else:
            resp = requests.get(
                "https://api.linkedin.com/rest/organizationalEntityShareStatistics",
                headers=_li_headers(),
                params={
                    "q": "organizationalEntity",
                    "organizationalEntity": _org_urn(),
                    "shares[0]": linkedin_post_id,
                },
                timeout=10,
            )
        if not resp.ok:
            return None
        elements = resp.json().get("elements", [])
        if not elements:
            return None

        stats_data = elements[0].get("totalShareStatistics", {})
        stats = {
            "impressions": stats_data.get("impressionCount", 0),
            "likes":       stats_data.get("likeCount", 0),
            "comments":    stats_data.get("commentCount", 0),
            "shares":      stats_data.get("shareCount", 0),
            "clicks":      stats_data.get("clickCount", 0),
        }
        db.upsert_post_analytics(linkedin_post_id, option_id, angle_name, stats)
        return stats
    except Exception:
        return None


def refresh_all_post_stats():
    """Refresh analytics for all published posts from LinkedIn API."""
    posts = db.list_published_posts()
    refreshed = 0
    for post in posts:
        pid = post.get("linkedin_post_id", "")
        if not pid or pid.startswith("dry-run"):
            continue
        result = fetch_post_stats(
            linkedin_post_id=pid,
            option_id=post.get("id"),
            angle_name=post.get("angle_name", ""),
        )
        if result:
            refreshed += 1
    return refreshed


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(_user: dict = Depends(get_current_user)):
    """
    Return full analytics dashboard data:
    - Follower history (last 30 snapshots)
    - Per-post performance stats
    - Angle breakdown summary
    - Overall totals
    """
    follower_history = db.get_follower_history(limit=30)
    post_analytics = db.get_post_analytics()

    # Latest follower count
    latest_followers = follower_history[0]["total"] if follower_history else None

    # Follower growth: diff between oldest and newest snapshot in history
    follower_growth = None
    if len(follower_history) >= 2:
        follower_growth = follower_history[0]["total"] - follower_history[-1]["total"]

    # Totals across all posts
    total_impressions = sum(p.get("impressions", 0) for p in post_analytics)
    total_likes       = sum(p.get("likes", 0) for p in post_analytics)
    total_comments    = sum(p.get("comments", 0) for p in post_analytics)
    total_shares      = sum(p.get("shares", 0) for p in post_analytics)
    total_clicks      = sum(p.get("clicks", 0) for p in post_analytics)

    # Engagement rate per post (likes+comments+shares / impressions)
    for p in post_analytics:
        imp = p.get("impressions", 0)
        eng = p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0)
        p["engagement_rate"] = round((eng / imp * 100), 2) if imp > 0 else 0

    # Angle breakdown: avg impressions and engagement per angle
    angle_map: dict = {}
    for p in post_analytics:
        angle = p.get("angle_name") or "Unknown"
        if angle not in angle_map:
            angle_map[angle] = {"posts": 0, "impressions": 0, "engagement": 0}
        angle_map[angle]["posts"] += 1
        angle_map[angle]["impressions"] += p.get("impressions", 0)
        angle_map[angle]["engagement"] += (
            p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0)
        )

    angle_summary = []
    for angle, data in angle_map.items():
        n = data["posts"]
        angle_summary.append({
            "angle": angle,
            "posts": n,
            "avg_impressions": round(data["impressions"] / n) if n else 0,
            "avg_engagement": round(data["engagement"] / n, 1) if n else 0,
        })
    angle_summary.sort(key=lambda x: x["avg_impressions"], reverse=True)

    return {
        "followers": {
            "total": latest_followers,
            "growth": follower_growth,
            "history": follower_history,
        },
        "totals": {
            "posts": len(post_analytics),
            "impressions": total_impressions,
            "likes": total_likes,
            "comments": total_comments,
            "shares": total_shares,
            "clicks": total_clicks,
        },
        "posts": post_analytics,
        "by_angle": angle_summary,
    }


@router.post("/analytics/refresh")
async def refresh_analytics(_user: dict = Depends(get_current_user)):
    """
    Refresh live stats from LinkedIn API for all published posts
    and capture a new follower snapshot.
    """
    from backend.api.linkedin import has_token
    if not has_token():
        return {"ok": False, "error": "LinkedIn token not configured."}

    follower_data = fetch_follower_stats()
    posts_refreshed = refresh_all_post_stats()
    new_alerts = db.check_engagement_alerts()

    return {
        "ok": True,
        "followers": follower_data,
        "posts_refreshed": posts_refreshed,
        "new_alerts": new_alerts,
    }
