"""Database layer — SQLite connection, schema, and migrations."""

import sqlite3
from pathlib import Path

from applyr.config import load_config

SCHEMA_VERSION = 1

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS offers (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    company           TEXT,
    summary           TEXT,
    -- Dates
    date_received     TEXT,
    date_applied      TEXT,
    date_responded    TEXT,
    -- Scoring
    compatibility_pct INTEGER DEFAULT 0,
    -- Status & tracking
    status            TEXT    DEFAULT 'pending',
    applied           INTEGER DEFAULT 0,
    canal             TEXT,
    cv_used           TEXT,
    follow_up_date    TEXT,
    follow_up_done    INTEGER DEFAULT 0,
    follow_up_notes   TEXT,
    -- Location & salary
    work_mode         TEXT,
    location          TEXT,
    salary_min        INTEGER,
    salary_max        INTEGER,
    salary_period     TEXT    DEFAULT 'annual',
    -- Classification
    seniority_level   TEXT,
    role_category     TEXT,
    tech_stack        TEXT,
    -- Materials
    cover_letter      INTEGER DEFAULT 0,
    cover_letter_file TEXT,
    -- Contact & context
    contact_name      TEXT,
    contact_role      TEXT,
    job_url           TEXT,
    rejection_reason  TEXT,
    notes             TEXT,
    created_at        TEXT    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS offer_topics (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id  INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    topic     TEXT,
    score     INTEGER,
    detail    TEXT
);

CREATE TABLE IF NOT EXISTS skill_gaps (
    skill      TEXT    PRIMARY KEY,
    frequency  INTEGER DEFAULT 1,
    total_gap  INTEGER DEFAULT 0,
    last_seen  TEXT
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

VALID_STATUSES = ("pending", "applied", "waiting", "in_process", "rejected", "discarded", "offer")
VALID_CHANNELS = ("linkedin_easy", "linkedin_direct", "email", "portal", "referral", "other")
VALID_WORK_MODES = ("remote", "hybrid", "onsite")
VALID_SENIORITY = ("trainee", "entry_level", "junior", "mid", "senior", "lead", "director")
VALID_ROLE_CATEGORIES = ("backend", "frontend", "fullstack", "ai", "devops", "data", "mobile", "qa", "other")

STATUS_LABELS = {
    "pending": "Pending",
    "applied": "Applied",
    "waiting": "Waiting Response",
    "in_process": "In Process",
    "rejected": "Rejected",
    "discarded": "Discarded",
    "offer": "Offer Received",
}


def get_db_path() -> str:
    """Get database path from config."""
    config = load_config()
    return config["general"]["db_path"]


def get_conn(db_path: str | None = None) -> sqlite3.Connection:
    """Open a connection to the SQLite database."""
    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | None = None):
    """Create tables if they don't exist."""
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        # Set schema version if not present
        existing = conn.execute("SELECT version FROM schema_version").fetchone()
        if not existing:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        conn.commit()
    finally:
        conn.close()
