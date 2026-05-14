"""
LinkedIn Page Analytics fetcher for MS. READ.

Org mode:
  - Follower count:  /v2/networkSizes/{orgUrn}?edgeType=CompanyFollowedByMember
  - Share stats:     /rest/organizationalEntityShareStatistics (shares=List format)

Personal mode:
  - Post stats:      /rest/memberCreatorPostAnalytics (per metric type)

Org endpoints require scope: rw_organization_admin
Personal endpoints require scope: r_member_postAnalytics

Results are cached in SQLite and returned even when the API is unavailable.
"""

from typing import Optional

import requests
from fastapi import APIRouter, Depends

from backend import database as db
from backend.api.linkedin import (
    _get_token, _get_org_id, _get_post_mode, _get_member_id,
    _rest_headers, _API_VERSION, _org_urn, _person_urn,
    fetch_follower_count, fetch_org_share_stats, fetch_personal_post_stats,
)
from backend.auth import get_current_user

router = APIRouter()


# ── Internal fetch helpers (used by scheduler too) ────────────────────────────

def fetch_follower_stats() -> Optional[dict]:
    """Fetch current follower count from LinkedIn.

    Org mode: uses /v2/networkSizes for total follower count.
    Personal mode: not available via API.
    """
    if _get_post_mode() == "personal":
        return {"total": None, "note": "Follower count not available for personal profiles."}

    total = fetch_follower_count()
    if total is None:
        return None

    db.save_follower_snapshot(total=total)
    return {"total": total}


def fetch_post_stats(linkedin_post_id: str, option_id: Optional[int],
                     angle_name: str) -> Optional[dict]:
    """Fetch impressions + engagement for a single post. Mode-aware."""
    if _get_post_mode() == "personal":
        result = fetch_personal_post_stats(linkedin_post_id)
    else:
        result = fetch_org_share_stats(linkedin_post_id)

    if result:
        db.upsert_post_analytics(linkedin_post_id, option_id, angle_name, result)
    return result


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