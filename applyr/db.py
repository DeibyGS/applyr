"""Database layer — SQLite connection, schema, and migrations."""

import sqlite3
from pathlib import Path

from applyr.config import load_config
from applyr.errors import warn

SCHEMA_VERSION = 7

# Migration registry: maps (from_version, to_version) -> list of SQL statements
# Add entries here when schema changes in future versions.
MIGRATIONS: dict[tuple[int, int], list[str]] = {
    (1, 2): ["DROP TABLE IF EXISTS skill_gaps"],
    (2, 3): [
        # Strip file extensions from cv_used values (AC-3.10)
        "UPDATE offers SET cv_used = REPLACE(REPLACE(cv_used, '.html', ''), '.md', '') WHERE cv_used IS NOT NULL"
    ],
    # Offers recorded before v1.1.0 carry no language; they are left NULL rather
    # than backfilled with a guess, so `cv generate` falls back to the configured
    # default instead of asserting a language nobody chose.
    (3, 4): ["ALTER TABLE offers ADD COLUMN language TEXT"],
    (4, 5): [
        """CREATE TABLE IF NOT EXISTS learning_gaps (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id        INTEGER REFERENCES offers(id) ON DELETE CASCADE,
            topic           TEXT NOT NULL,
            gap_detail      TEXT NOT NULL,
            severity        TEXT DEFAULT 'medium',
            suggested_action TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_learning_gaps_offer_id ON learning_gaps(offer_id)",
        "CREATE INDEX IF NOT EXISTS idx_learning_gaps_topic ON learning_gaps(topic)",
        "CREATE INDEX IF NOT EXISTS idx_learning_gaps_severity ON learning_gaps(severity)",
    ],
    # Phase 3 Analytics: response tracking
    (5, 6): ["ALTER TABLE offers ADD COLUMN response_status TEXT DEFAULT 'no_response'"],
    # Both columns existed but nothing ever wrote them, so every database in
    # the wild holds applied = 0 on offers that were plainly sent, and
    # no_response on offers that were plainly answered. Derive both from the
    # status, which is the column users actually maintained. `date_applied` is
    # deliberately left alone: there is no honest way to invent a send date.
    (6, 7): [
        """UPDATE offers SET applied = CASE
               WHEN status IN ('applied', 'waiting', 'in_process', 'rejected', 'offer') THEN 1
               ELSE 0 END""",
        """UPDATE offers SET response_status = status
               WHERE status IN ('in_process', 'rejected', 'offer')""",
    ],
}

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
    language          TEXT,
    -- Materials
    cover_letter      INTEGER DEFAULT 0,
    cover_letter_file TEXT,
    -- Contact & context
    contact_name      TEXT,
    contact_role      TEXT,
    job_url           TEXT,
    rejection_reason  TEXT,
    response_status   TEXT    DEFAULT 'no_response',
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

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS learning_gaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id        INTEGER REFERENCES offers(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL,
    gap_detail      TEXT NOT NULL,
    severity        TEXT DEFAULT 'medium',
    suggested_action TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_learning_gaps_offer_id ON learning_gaps(offer_id);
CREATE INDEX IF NOT EXISTS idx_learning_gaps_topic ON learning_gaps(topic);
CREATE INDEX IF NOT EXISTS idx_learning_gaps_severity ON learning_gaps(severity);
"""

VALID_STATUSES = ("pending", "applied", "waiting", "in_process", "rejected", "discarded", "offer")
VALID_CHANNELS = ("linkedin_easy", "linkedin_direct", "email", "portal", "referral", "other")
VALID_WORK_MODES = ("remote", "hybrid", "onsite")
VALID_SENIORITY = ("trainee", "entry_level", "junior", "mid", "senior", "lead", "director")
VALID_ROLE_CATEGORIES = ("backend", "frontend", "fullstack", "ai", "devops", "data", "mobile", "qa", "other")
# Only languages applyr can write a CV in. Validated at `add` time rather than
# accepting any ISO code, because an unknown language would silently fall back to
# English headings — the mixed-language CV this field exists to prevent. Adding a
# language means adding its headings to CV_HEADINGS in cv.py; nothing else.
VALID_LANGUAGES = ("en", "es")
VALID_SEVERITIES = ("low", "medium", "high")

# Statuses that mean the application actually went out. `pending` was never
# sent and `discarded` was dropped before sending, so neither counts. This is
# the meaning of the `applied` column on a row.
SENT_STATUSES = frozenset({"applied", "waiting", "in_process", "rejected", "offer"})

# Statuses only reachable because the company replied — reaching one stamps
# `date_responded` and `response_status`. `waiting` is deliberately excluded:
# it means the application is out and no reply has arrived yet.
REPLY_STATUSES = frozenset({"in_process", "rejected", "offer"})

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


def get_schema_version(conn: sqlite3.Connection) -> int | None:
    """Read the stored schema version, or None if the table doesn't exist yet."""
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return None
    return row["version"] if row else None


def _run_migrations(conn: sqlite3.Connection, current: int, target: int) -> None:
    """Run sequential migrations from current version to target version."""
    version = current
    while version < target:
        next_version = version + 1
        steps = MIGRATIONS.get((version, next_version))
        if steps is None:
            raise RuntimeError(
                f"No migration path from schema v{version} to v{next_version}. "
                f"Database may need manual intervention."
            )
        for sql in steps:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError as exc:
                # init_db runs SCHEMA_SQL before migrating, and its
                # `CREATE TABLE IF NOT EXISTS` already gives a newly created
                # database every current column. An ADD COLUMN migration is then
                # a no-op rather than a failure — SQLite has no
                # `ADD COLUMN IF NOT EXISTS` to say so. Every other operational
                # error is real and must surface.
                if "duplicate column name" not in str(exc):
                    raise
        version = next_version
    conn.execute("UPDATE schema_version SET version = ?", (target,))


def init_db(db_path: str | None = None):
    """Create tables if they don't exist, and run pending migrations."""
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        existing = conn.execute("SELECT version FROM schema_version").fetchone()
        if not existing:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        else:
            db_version = existing["version"]
            if db_version < SCHEMA_VERSION:
                _run_migrations(conn, db_version, SCHEMA_VERSION)
            elif db_version > SCHEMA_VERSION:
                # stderr, not stdout: this used to be a bare print(), which put
                # a prose line above the payload of every `--json` command and
                # broke the parse for exactly the agent callers applyr is built
                # for. `warn` exists for this — "warnings are not data".
                warn(
                    f"Warning: database schema v{db_version} is newer than "
                    f"applyr v{SCHEMA_VERSION}. Consider upgrading applyr."
                )
        conn.commit()
    finally:
        conn.close()
