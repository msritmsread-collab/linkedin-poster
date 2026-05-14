"""
SQLite database layer for LinkedIn Auto-Poster.

Tables:
  sessions       — one row per generation trigger (image + optional topic)
  options        — three rows per session (A, B, C content options)
  blocked_angles — rejected topic hashes, blocked for 6 months
  settings       — key-value store for user configuration (token, schedule, topics)
  users          — authenticated users (admin + regular)
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "linkedin_poster.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # GCS FUSE does not support WAL shared-memory locks — use DELETE journal mode
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist. Seed admin user on first run."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT    NOT NULL,
                topic       TEXT,
                image_path  TEXT,
                status      TEXT    NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending','approved','rejected'))
            );

            CREATE TABLE IF NOT EXISTS options (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id       INTEGER NOT NULL REFERENCES sessions(id),
                label            TEXT    NOT NULL CHECK(label IN ('A','B','C')),
                angle_name       TEXT    NOT NULL,
                content          TEXT    NOT NULL,
                status           TEXT    NOT NULL DEFAULT 'pending'
                                 CHECK(status IN ('pending','approved','posted','rejected')),
                approved_at      TEXT,
                posted_at        TEXT,
                linkedin_post_id TEXT
            );

            CREATE TABLE IF NOT EXISTS blocked_angles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_hash   TEXT    NOT NULL UNIQUE,
                keywords     TEXT    NOT NULL,
                blocked_at   TEXT    NOT NULL,
                blocked_until TEXT   NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS post_analytics (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                linkedin_post_id TEXT    NOT NULL UNIQUE,
                option_id        INTEGER REFERENCES options(id),
                angle_name       TEXT,
                fetched_at       TEXT    NOT NULL,
                impressions      INTEGER DEFAULT 0,
                likes            INTEGER DEFAULT 0,
                comments         INTEGER DEFAULT 0,
                shares           INTEGER DEFAULT 0,
                clicks           INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS follower_snapshots (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at  TEXT NOT NULL,
                total        INTEGER NOT NULL,
                organic_gain INTEGER DEFAULT 0,
                paid_gain    INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS engagement_alerts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                linkedin_post_id    TEXT    NOT NULL,
                option_id           INTEGER REFERENCES options(id),
                angle_name          TEXT,
                triggered_at        TEXT    NOT NULL,
                impressions         INTEGER DEFAULT 0,
                engagement_rate     REAL    DEFAULT 0,
                avg_engagement_rate REAL    DEFAULT 0,
                multiple            REAL    DEFAULT 0,
                content_preview     TEXT,
                dismissed           INTEGER NOT NULL DEFAULT 0,
                dismissed_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'user'
                              CHECK(role IN ('admin','user')),
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    NOT NULL
            );
        """)

        # Seed default admin if no users exist
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            from passlib.context import CryptContext
            _pwd = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
            admin_email = os.getenv("ADMIN_EMAIL", "admin@msread.com")
            admin_pass  = os.getenv("ADMIN_PASSWORD", "Admin123!")
            conn.execute(
                "INSERT INTO users (email, password_hash, role, active, created_at) VALUES (?,?,?,1,?)",
                (admin_email, _pwd.hash(admin_pass), "admin", datetime.utcnow().isoformat()),
            )

        # Auto-generate JWT secret if not present
        row = conn.execute("SELECT value FROM settings WHERE key='jwt_secret'").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES ('jwt_secret', ?)",
                (secrets.token_hex(32),),
            )


# ── Sessions ─────────────────────────────────────────────────────────────────

def create_session(topic: Optional[str], image_path: Optional[str]) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (created_at, topic, image_path, status) VALUES (?,?,?,'pending')",
            (datetime.utcnow().isoformat(), topic, image_path),
        )
        return cur.lastrowid


def get_session(session_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        session = dict(row)
        session["options"] = _get_options(conn, session_id)
        return session


def list_sessions(status: Optional[str] = None) -> List[dict]:
    with _conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        sessions = []
        for row in rows:
            s = dict(row)
            s["options"] = _get_options(conn, s["id"])
            sessions.append(s)
        return sessions


def update_session_status(session_id: int, status: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = ? WHERE id = ?", (status, session_id)
        )


# ── Options ───────────────────────────────────────────────────────────────────

def save_options(session_id: int, options: List[dict]):
    """options: list of {label, angle_name, content}"""
    with _conn() as conn:
        conn.executemany(
            "INSERT INTO options (session_id, label, angle_name, content) VALUES (?,?,?,?)",
            [(session_id, o["label"], o["angle_name"], o["content"]) for o in options],
        )


def approve_option(session_id: int, label: str) -> dict:
    """Mark one option as approved, reject the rest, update session status."""
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE options SET status='approved', approved_at=? WHERE session_id=? AND label=?",
            (now, session_id, label),
        )
        conn.execute(
            "UPDATE options SET status='rejected' WHERE session_id=? AND label!=?",
            (session_id, label),
        )
        conn.execute(
            "UPDATE sessions SET status='approved' WHERE id=?", (session_id,)
        )
        row = conn.execute(
            "SELECT * FROM options WHERE session_id=? AND label=?",
            (session_id, label),
        ).fetchone()
        return dict(row) if row else {}


def mark_option_posted(option_id: int, linkedin_post_id: str):
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE options SET status='posted', posted_at=?, linkedin_post_id=? WHERE id=?",
            (now, linkedin_post_id, option_id),
        )
        session_id = conn.execute(
            "SELECT session_id FROM options WHERE id=?", (option_id,)
        ).fetchone()["session_id"]
        conn.execute(
            "UPDATE sessions SET status='approved' WHERE id=?", (session_id,)
        )


def reject_all_options(session_id: int, topic_keywords: str):
    """Reject all options and block this topic for 6 months."""
    now = datetime.utcnow()
    blocked_until = (now + timedelta(days=180)).isoformat()
    topic_hash = _hash_topic(topic_keywords)
    with _conn() as conn:
        conn.execute(
            "UPDATE options SET status='rejected' WHERE session_id=?", (session_id,)
        )
        conn.execute(
            "UPDATE sessions SET status='rejected' WHERE id=?", (session_id,)
        )
        conn.execute(
            """INSERT INTO blocked_angles (topic_hash, keywords, blocked_at, blocked_until)
               VALUES (?,?,?,?)
               ON CONFLICT(topic_hash) DO UPDATE SET blocked_until=excluded.blocked_until""",
            (topic_hash, topic_keywords, now.isoformat(), blocked_until),
        )


def _get_options(conn, session_id: int) -> List[dict]:
    rows = conn.execute(
        "SELECT * FROM options WHERE session_id = ? ORDER BY label", (session_id,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Blocked angles ────────────────────────────────────────────────────────────

def get_active_blocks() -> List[dict]:
    """Return topics still within their 6-month block window."""
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM blocked_angles WHERE blocked_until > ?", (now,)
        ).fetchall()
        return [dict(r) for r in rows]


def _hash_topic(text: str) -> str:
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()


# ── Settings (key-value) ──────────────────────────────────────────────────────

import json as _json

_DEFAULTS = {
    "linkedin_token": "",
    "linkedin_org_id": "6456959",
    "linkedin_member_id": "",       # For personal profile mode
    "post_mode": "org",             # "org" = company page, "personal" = personal profile
    "schedule_days": _json.dumps(["mon", "wed", "fri"]),
    "schedule_time": "09:00",
    "default_topics": _json.dumps([]),
    "reference_posts": _json.dumps([]),
}


def get_setting(key: str) -> Optional[str]:
    with _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if row:
            return row["value"]
        return _DEFAULTS.get(key)


def set_setting(key: str, value: str):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        result = dict(_DEFAULTS)
        result.update({r["key"]: r["value"] for r in rows})
        return result


# ── Analytics ─────────────────────────────────────────────────────────────────

def upsert_post_analytics(linkedin_post_id: str, option_id: Optional[int],
                          angle_name: str, stats: dict):
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute("""
            INSERT INTO post_analytics
              (linkedin_post_id, option_id, angle_name, fetched_at,
               impressions, likes, comments, shares, clicks)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(linkedin_post_id) DO UPDATE SET
              fetched_at=excluded.fetched_at,
              impressions=excluded.impressions,
              likes=excluded.likes,
              comments=excluded.comments,
              shares=excluded.shares,
              clicks=excluded.clicks
        """, (
            linkedin_post_id, option_id, angle_name, now,
            stats.get("impressions", 0), stats.get("likes", 0),
            stats.get("comments", 0), stats.get("shares", 0),
            stats.get("clicks", 0),
        ))


def save_follower_snapshot(total: int):
    """Save a follower count snapshot. Uses the networkSizes total follower count."""
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO follower_snapshots (captured_at, total, organic_gain, paid_gain) VALUES (?,?,0,0)",
            (now, total),
        )


def get_follower_history(limit: int = 30) -> List[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM follower_snapshots ORDER BY captured_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_post_analytics() -> List[dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT pa.*, o.posted_at, o.content, s.topic
            FROM post_analytics pa
            LEFT JOIN options o ON o.id = pa.option_id
            LEFT JOIN sessions s ON s.id = o.session_id
            ORDER BY o.posted_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ── Engagement alerts ─────────────────────────────────────────────────────────

def check_engagement_alerts() -> int:
    """
    Compare each recent post's engagement rate against the fleet average.
    Creates an alert row when a post ≤14 days old exceeds 1.5× the average.
    Returns the number of new alerts created.
    """
    THRESHOLD = 1.5
    WINDOW_DAYS = 14

    with _conn() as conn:
        # Compute fleet average engagement rate (all posts with impressions > 0)
        avg_row = conn.execute("""
            SELECT AVG((pa.likes + pa.comments + pa.shares) * 100.0 / pa.impressions) as avg_rate
            FROM post_analytics pa
            WHERE pa.impressions > 0
        """).fetchone()
        avg_rate = avg_row["avg_rate"] if avg_row and avg_row["avg_rate"] else None
        if not avg_rate or avg_rate <= 0:
            return 0  # Not enough data yet

        # Find recent posts above threshold
        rows = conn.execute("""
            SELECT
                pa.linkedin_post_id,
                pa.option_id,
                pa.angle_name,
                pa.impressions,
                (pa.likes + pa.comments + pa.shares) * 100.0 / pa.impressions AS eng_rate,
                o.content,
                o.posted_at
            FROM post_analytics pa
            LEFT JOIN options o ON o.id = pa.option_id
            WHERE pa.impressions > 0
              AND o.posted_at IS NOT NULL
              AND datetime(o.posted_at) >= datetime('now', ?)
        """, (f"-{WINDOW_DAYS} days",)).fetchall()

        new_alerts = 0
        now = datetime.utcnow().isoformat()

        for row in rows:
            eng_rate = row["eng_rate"] or 0
            if eng_rate <= THRESHOLD * avg_rate:
                continue

            # Check for existing undismissed alert
            exists = conn.execute(
                "SELECT COUNT(*) FROM engagement_alerts WHERE linkedin_post_id=? AND dismissed=0",
                (row["linkedin_post_id"],),
            ).fetchone()[0]
            if exists:
                continue

            multiple = round(eng_rate / avg_rate, 2)
            content = row["content"] or ""
            preview = content[:120].strip() + ("..." if len(content) > 120 else "")

            conn.execute("""
                INSERT INTO engagement_alerts
                  (linkedin_post_id, option_id, angle_name, triggered_at,
                   impressions, engagement_rate, avg_engagement_rate, multiple, content_preview)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                row["linkedin_post_id"], row["option_id"], row["angle_name"],
                now, row["impressions"], round(eng_rate, 2),
                round(avg_rate, 2), multiple, preview,
            ))
            new_alerts += 1

        return new_alerts


def get_undismissed_alerts() -> List[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM engagement_alerts WHERE dismissed=0 ORDER BY triggered_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def dismiss_alert(alert_id: int):
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE engagement_alerts SET dismissed=1, dismissed_at=? WHERE id=?",
            (now, alert_id),
        )


# ── Users ────────────────────────────────────────────────────────────────────

def create_user(email: str, password_hash: str, role: str = "user") -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, role, active, created_at) VALUES (?,?,?,1,?)",
            (email.lower().strip(), password_hash, role, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_user_by_email(email: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> List[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def update_user(user_id: int, **kwargs):
    """Update user fields: active, role, password_hash."""
    allowed = {"active", "role", "password_hash"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [user_id]
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)


# ── Published posts view ──────────────────────────────────────────────────────

def list_published_posts() -> List[dict]:
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                o.id, o.session_id, o.label, o.angle_name, o.content,
                o.posted_at, o.linkedin_post_id,
                s.topic, s.image_path, s.created_at as session_created_at
            FROM options o
            JOIN sessions s ON s.id = o.session_id
            WHERE o.status = 'posted'
            ORDER BY o.posted_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
