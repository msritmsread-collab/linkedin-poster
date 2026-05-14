"""
APScheduler — Auto-generates LinkedIn content based on user-configured schedule.
Default: Monday, Wednesday, Friday at 09:00 Asia/Kuala_Lumpur

Schedule and topics are read from the DB settings table (configurable via Settings UI).
Supports live rescheduling when the user updates their schedule.
"""

import json
import logging
import os
import sys


from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from backend import database as db
from backend.api.generator import generate_options

logger = logging.getLogger("linkedin_poster.scheduler")

MYT = pytz.timezone("Asia/Kuala_Lumpur")

_scheduler: AsyncIOScheduler = None
JOB_ID = "linkedin_auto_generate"
ANALYTICS_JOB_ID = "analytics_auto_refresh"

# APScheduler day-of-week map
_DAY_MAP = {
    "mon": "0", "tue": "1", "wed": "2", "thu": "3",
    "fri": "4", "sat": "5", "sun": "6",
}


async def scheduled_analytics_refresh():
    """Auto-refresh post stats and check for engagement alerts every 6 hours."""
    from backend.api.analytics import refresh_all_post_stats
    from backend.api.linkedin import has_token
    if not has_token():
        return  # Skip silently — no token configured yet
    try:
        refreshed = refresh_all_post_stats()
        alerts = db.check_engagement_alerts()
        logger.info(f"Analytics auto-refresh: {refreshed} posts updated, {alerts} new alert(s).")
    except Exception as e:
        logger.error(f"Analytics auto-refresh failed: {e}")


async def scheduled_generate():
    """Auto-generate 3 LinkedIn post options and save to DB."""
    # Read latest topics from settings at trigger time
    raw_topics = db.get_setting("default_topics") or "[]"
    try:
        topics = json.loads(raw_topics)
    except Exception:
        topics = []

    topic_hint = ", ".join(topics) if topics else None

    blocks = db.get_active_blocks()
    blocked_keywords = [b["keywords"] for b in blocks]

    session_id = db.create_session(topic=topic_hint, image_path=None)
    logger.info(f"Scheduler: created session {session_id} (topic: {topic_hint!r})")

    try:
        options = generate_options(topic=topic_hint, blocked_keywords=blocked_keywords)
        db.save_options(session_id, options)
        logger.info(f"Session {session_id}: 3 options generated. Awaiting approval.")
    except Exception as e:
        logger.error(f"Session {session_id}: generation failed: {e}")
        db.update_session_status(session_id, "rejected")
        raise


def _build_trigger() -> CronTrigger:
    """Build a CronTrigger from DB settings."""
    raw_days = db.get_setting("schedule_days") or '["mon","wed","fri"]'
    raw_time = db.get_setting("schedule_time") or "09:00"

    try:
        days = json.loads(raw_days)
    except Exception:
        days = ["mon", "wed", "fri"]

    try:
        hour, minute = raw_time.split(":")
        hour, minute = int(hour), int(minute)
    except Exception:
        hour, minute = 9, 0

    # Convert day names to APScheduler format (0=mon … 6=sun)
    dow = ",".join(_DAY_MAP[d] for d in days if d in _DAY_MAP) or "0,2,4"

    return CronTrigger(
        day_of_week=dow,
        hour=hour,
        minute=minute,
        timezone=MYT,
    )


def reschedule():
    """Rebuild the cron job from current DB settings. Called after settings update."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        logger.warning("Reschedule called but scheduler not running.")
        return
    trigger = _build_trigger()
    _scheduler.reschedule_job(JOB_ID, trigger=trigger)
    raw_days = db.get_setting("schedule_days") or '["mon","wed","fri"]'
    raw_time = db.get_setting("schedule_time") or "09:00"
    logger.info(f"Scheduler rescheduled: days={raw_days}, time={raw_time} MYT")


def create_scheduler() -> AsyncIOScheduler:
    """Create, configure, and return an APScheduler instance."""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=MYT)

    trigger = _build_trigger()
    _scheduler.add_job(
        scheduled_generate,
        trigger=trigger,
        id=JOB_ID,
        name="LinkedIn Auto-Generate",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    _scheduler.add_job(
        scheduled_analytics_refresh,
        trigger=IntervalTrigger(hours=6),
        id=ANALYTICS_JOB_ID,
        name="Analytics Auto-Refresh",
        replace_existing=True,
        misfire_grace_time=600,
    )

    return _scheduler
