"""
LinkedIn Auto-Poster — REST API Routes

POST /api/trigger                        Manually trigger content generation
GET  /api/sessions                       List sessions (filter by status)
GET  /api/sessions/{id}                  Get session + 3 options
POST /api/sessions/{id}/approve/{label}  Approve option A/B/C → post to LinkedIn
POST /api/sessions/{id}/reject           Reject all options (block topic 6mo)
GET  /api/posts                          Published post history
POST /api/sessions/{id}/image            Upload/replace image for a session
"""

import os
import shutil
import uuid
from typing import List, Optional


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend import database as db
from backend.api.generator import generate_options
from backend.api import linkedin as li
from backend.auth import get_current_user

router = APIRouter()

_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "images")
_MAX_UPLOAD_MB = 10
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
os.makedirs(_UPLOAD_DIR, exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class RejectBody(BaseModel):
    keywords: Optional[str] = None  # comma-separated topic keywords for block list


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_upload(file: UploadFile) -> str:
    ext = (file.filename or "image.jpg").rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed. Allowed: {', '.join('.' + e for e in _ALLOWED_EXTENSIONS)}")
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(_UPLOAD_DIR, filename)
    contents = file.file.read()
    if len(contents) > _MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {_MAX_UPLOAD_MB}MB.")
    with open(dest, "wb") as f:
        f.write(contents)
    return dest


def _do_generate(session_id: int, topic: Optional[str]):
    """Background task: generate options and save to DB."""
    blocks = db.get_active_blocks()
    blocked_keywords = [b["keywords"] for b in blocks]
    try:
        options = generate_options(topic=topic, blocked_keywords=blocked_keywords)
        db.save_options(session_id, options)
    except Exception as e:
        db.update_session_status(session_id, "rejected")
        raise RuntimeError(f"Generation failed for session {session_id}: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_generation(
    background_tasks: BackgroundTasks,
    topic: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    _user: dict = Depends(get_current_user),
):
    """
    Manually trigger content generation.
    Optionally provide a topic hint and/or an image to attach.
    Returns immediately with session_id; generation runs in background.
    """
    image_path = _save_upload(image) if image else None
    session_id = db.create_session(topic=topic, image_path=image_path)
    background_tasks.add_task(_do_generate, session_id, topic)
    return {"session_id": session_id, "status": "generating"}


@router.get("/sessions")
async def list_sessions(status: Optional[str] = None, _user: dict = Depends(get_current_user)):
    """List all sessions. Filter by status: pending, approved, rejected."""
    sessions = db.list_sessions(status=status)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: int, _user: dict = Depends(get_current_user)):
    """Get a session and its 3 content options."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/image")
async def upload_session_image(session_id: int, image: UploadFile = File(...), _user: dict = Depends(get_current_user)):
    """Upload or replace the image for a session (before approval)."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "pending":
        raise HTTPException(status_code=400, detail="Cannot update image after approval/rejection")

    image_path = _save_upload(image)
    with db._conn() as conn:
        conn.execute(
            "UPDATE sessions SET image_path = ? WHERE id = ?",
            (image_path, session_id),
        )
    return {"session_id": session_id, "image_path": image_path}


@router.post("/sessions/{session_id}/approve/{label}")
async def approve_option(session_id: int, label: str, _user: dict = Depends(get_current_user)):
    """
    Approve one option (A, B, or C) and post it to LinkedIn.
    Rejects the other two options.
    """
    label = label.upper()
    if label not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="Label must be A, B, or C")

    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Session is already {session['status']}")

    option = db.approve_option(session_id, label)
    if not option:
        raise HTTPException(status_code=404, detail=f"Option {label} not found")

    # Post to LinkedIn
    content = option["content"]
    image_path = session.get("image_path")

    try:
        if li.has_token():
            post_id = li.post_to_linkedin(content, image_path)
        else:
            post_id = li.post_to_linkedin_dryrun(content, image_path)

        db.mark_option_posted(option["id"], post_id)
        return {
            "status": "posted",
            "session_id": session_id,
            "label": label,
            "linkedin_post_id": post_id,
            "dry_run": not li.has_token(),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LinkedIn posting failed: {e}")


@router.post("/sessions/{session_id}/reject")
async def reject_session(session_id: int, body: RejectBody = RejectBody(), _user: dict = Depends(get_current_user)):
    """
    Reject all options in a session and block the topic for 6 months.
    Provide comma-separated keywords describing the topic to block.
    """
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Session is already {session['status']}")

    keywords = body.keywords or session.get("topic") or f"session_{session_id}"
    db.reject_all_options(session_id, keywords)
    return {"status": "rejected", "session_id": session_id, "blocked_keywords": keywords}


@router.get("/posts")
async def list_published_posts(_user: dict = Depends(get_current_user)):
    """Get history of all published posts."""
    posts = db.list_published_posts()
    return {"posts": posts, "count": len(posts)}


@router.get("/health")
async def health():
    return {"status": "ok", "linkedin_configured": li.has_token()}
