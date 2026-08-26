"""Tests for database schema and operations."""

import pytest
import sqlite3

from applyr.db import init_db, get_conn, SCHEMA_VERSION, VALID_STATUSES, VALID_CHANNELS, VALID_SEVERITIES
import applyr.db as db_module


@pytest.mark.unit
class TestInitDb:

    def test_creates_tables(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            names = {r["name"] for r in tables}
            assert "offers" in names
            assert "offer_topics" in names
            assert "schema_version" in names
            assert "learning_gaps" in names
            assert "skill_gaps" not in names
        finally:
            conn.close()

    def test_schema_version_set(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            assert row["version"] == SCHEMA_VERSION
        finally:
            conn.close()

    def test_idempotent_init(self, tmp_db):
        # Running init again should not crash
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            assert row["version"] == SCHEMA_VERSION
        finally:
            conn.close()


@pytest.mark.unit
class TestMigrationV1ToV2:

    def test_drops_skill_gaps_table(self, tmp_db):
        """Migration from v1 to v2 drops the skill_gaps table."""
        # Manually create v1 schema with skill_gaps table
        conn = get_conn(tmp_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_gaps (
                skill      TEXT    PRIMARY KEY,
                frequency  INTEGER DEFAULT 1,
                total_gap  INTEGER DEFAULT 0,
                last_seen  TEXT
            )
        """)
        conn.execute("UPDATE schema_version SET version = 1")
        conn.commit()
        conn.close()

        # Verify skill_gaps exists before migration
        conn = get_conn(tmp_db)
        tables_before = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert "skill_gaps" in {r["name"] for r in tables_before}
        conn.close()

        # Run init_db which should migrate to v2
        init_db(tmp_db)

        # Verify skill_gaps is gone after migration
        conn = get_conn(tmp_db)
        tables_after = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables_after}
        assert "skill_gaps" not in names
        assert "offers" in names
        assert "offer_topics" in names
        assert "schema_version" in names

        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row["version"] == SCHEMA_VERSION
        conn.close()

    def test_migration_idempotent(self, tmp_db):
        """Running migration twice should not crash."""
        init_db(tmp_db)
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            assert row["version"] == SCHEMA_VERSION
        finally:
            conn.close()


@pytest.mark.unit
class TestAc45OutputEquivalence:
    """AC-4.5: gaps, plan, and summary must produce byte-identical output
    before and after the skill_gaps migration."""

    def _setup_v1_with_data(self, tmp_db):
        """Create a v1 database with skill_gaps table and offer data."""
        conn = get_conn(tmp_db)
        # Create skill_gaps table (v1)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS skill_gaps (
                skill      TEXT    PRIMARY KEY,
                frequency  INTEGER DEFAULT 1,
                total_gap  INTEGER DEFAULT 0,
                last_seen  TEXT
            )
        """)
        # Insert some offer data
        conn.execute(
            "INSERT INTO offers (title, company, status, compatibility_pct) VALUES (?, ?, ?, ?)",
            ("Dev", "Acme", "applied", 50),
        )
        conn.execute(
            "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (?, ?, ?, ?)",
            (1, "tech_stack", 40, "needs improvement"),
        )
        # Insert skill_gaps data (v1 accumulator)
        conn.execute(
            "INSERT INTO skill_gaps (skill, frequency, total_gap, last_seen) VALUES (?, ?, ?, ?)",
            ("tech_stack", 1, 25, "2026-01-01"),
        )
        conn.execute("UPDATE schema_version SET version = 1")
        conn.commit()
        conn.close()

    def test_gaps_output_before_and_after_migration(self, tmp_db, tmp_applyr, monkeypatch):
        """gaps command output must be identical before and after migration."""
        from applyr.commands.analytics import cmd_gaps

        self._setup_v1_with_data(tmp_db)

        # Capture output before migration
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        cmd_gaps(as_json=False)
        output_before = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Run migration
        init_db(tmp_db)

        # Capture output after migration
        sys.stdout = io.StringIO()
        cmd_gaps(as_json=False)
        output_after = sys.stdout.getvalue()
        sys.stdout = old_stdout

        # Outputs must contain the same skill gap info
        # (the label "Tech Stack" appears, not the raw key "tech_stack")
        assert "Tech Stack" in output_before
        assert "Tech Stack" in output_after
        assert output_before == output_after


@pytest.mark.unit
class TestOffersCrud:

    def test_insert_and_query(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                ("Dev", "Acme", "pending"),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM offers WHERE id = 1").fetchone()
            assert row["title"] == "Dev"
            assert row["company"] == "Acme"
            assert row["status"] == "pending"
            assert row["compatibility_pct"] == 0
        finally:
            conn.close()

    def test_offer_topics_foreign_key(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme")
            )
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (?, ?, ?, ?)",
                (1, "tech_stack", 80, "ok"),
            )
            conn.commit()
            topics = conn.execute(
                "SELECT * FROM offer_topics WHERE offer_id = 1"
            ).fetchall()
            assert len(topics) == 1
            assert topics[0]["score"] == 80
        finally:
            conn.close()

    def test_cascade_delete(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score) VALUES (?, ?, ?)",
                (1, "tech_stack", 90),
            )
            conn.commit()
            conn.execute("DELETE FROM offers WHERE id = 1")
            conn.commit()
            topics = conn.execute("SELECT * FROM offer_topics WHERE offer_id = 1").fetchall()
            assert len(topics) == 0
        finally:
            conn.close()


@pytest.mark.unit
class TestEnumConstants:

    def test_valid_statuses(self):
        assert "pending" in VALID_STATUSES
        assert "applied" in VALID_STATUSES
        assert "offer" in VALID_STATUSES
        assert len(VALID_STATUSES) == 7

    def test_valid_channels(self):
        assert "linkedin_easy" in VALID_CHANNELS
        assert len(VALID_CHANNELS) == 6

    def test_valid_severities(self):
        assert "low" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert len(VALID_SEVERITIES) == 3


@pytest.mark.unit
class TestMigrationV4ToV5:

    def test_creates_learning_gaps_table(self, tmp_db):
        """Migration from v4 to v5 creates learning_gaps table."""
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 4")
        conn.commit()
        conn.close()

        init_db(tmp_db)

        conn = get_conn(tmp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "learning_gaps" in names

        # Compare against the constant, not a literal: init_db migrates all the
        # way to the latest version, so a hardcoded number breaks on every bump.
        from applyr.db import SCHEMA_VERSION

        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row["version"] == SCHEMA_VERSION
        conn.close()

    def test_migration_idempotent(self, tmp_db):
        """Running migration twice should not crash."""
        init_db(tmp_db)
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            assert row["version"] == SCHEMA_VERSION
        finally:
            conn.close()


@pytest.mark.unit
class TestLearningGapsCrud:

    def test_insert_and_query(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
            conn.execute(
                "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity, suggested_action) "
                "VALUES (?, ?, ?, ?, ?)",
                (1, "tech_stack", "Missing LangChain", "high", "Build a RAG project"),
            )
            conn.commit()
            rows = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchall()
            assert len(rows) == 1
            assert rows[0]["topic"] == "tech_stack"
            assert rows[0]["gap_detail"] == "Missing LangChain"
            assert rows[0]["severity"] == "high"
            assert rows[0]["suggested_action"] == "Build a RAG project"
        finally:
            conn.close()

    def test_cascade_delete(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
            conn.execute(
                "INSERT INTO learning_gaps (offer_id, topic, gap_detail) VALUES (?, ?, ?)",
                (1, "tech_stack", "Missing skill"),
            )
            conn.commit()
            conn.execute("DELETE FROM offers WHERE id = 1")
            conn.commit()
            rows = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchall()
            assert len(rows) == 0
        finally:
            conn.close()

    def test_default_severity(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
            conn.execute(
                "INSERT INTO learning_gaps (offer_id, topic, gap_detail) VALUES (?, ?, ?)",
                (1, "english", "Needs B2"),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM learning_gaps WHERE id = 1").fetchone()
            assert row["severity"] == "medium"
        finally:
            conn.close()

    def test_indexes_exist(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='learning_gaps'"
            ).fetchall()
            names = {r["name"] for r in indexes}
            assert "idx_learning_gaps_offer_id" in names
            assert "idx_learning_gaps_topic" in names
            assert "idx_learning_gaps_severity" in names
        finally:
            conn.close()


@pytest.mark.unit
class TestMigrationV6ToV7:
    """`applied` and `response_status` shipped with no writer, so every existing
    database holds 0 and 'no_response' on offers that were plainly sent and
    plainly answered. The migration derives both from the status."""

    def _seed(self, tmp_db, status):
        conn = get_conn(tmp_db)
        conn.execute(
            "INSERT INTO offers (title, company, status, applied, response_status) VALUES (?, ?, ?, 0, 'no_response')",
            ("Backend Dev", "Acme", status),
        )
        conn.execute("UPDATE schema_version SET version = 6")
        conn.commit()
        conn.close()
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            return dict(conn.execute("SELECT * FROM offers").fetchone())
        finally:
            conn.close()

    @pytest.mark.parametrize("status", ["applied", "waiting", "in_process", "rejected", "offer"])
    def test_sent_offers_get_the_applied_flag(self, tmp_db, status):
        assert self._seed(tmp_db, status)["applied"] == 1

    @pytest.mark.parametrize("status", ["pending", "discarded"])
    def test_unsent_offers_stay_unflagged(self, tmp_db, status):
        assert self._seed(tmp_db, status)["applied"] == 0

    @pytest.mark.parametrize("status", ["in_process", "rejected", "offer"])
    def test_answered_offers_record_the_response(self, tmp_db, status):
        assert self._seed(tmp_db, status)["response_status"] == status

    @pytest.mark.parametrize("status", ["applied", "waiting"])
    def test_unanswered_offers_keep_no_response(self, tmp_db, status):
        assert self._seed(tmp_db, status)["response_status"] == "no_response"

    def test_send_dates_are_not_invented(self, tmp_db):
        """There is no honest source for a send date that was never recorded."""
        assert self._seed(tmp_db, "applied")["date_applied"] is None


class TestMigrationV7ToV8:
    """`confidence` shipped with no backfill by design — there is no honest
    way to invent a certainty nobody recorded for topics scored before this
    migration existed."""

    def test_existing_topic_rows_get_null_confidence(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES ('Backend Dev', 'Acme')")
        conn.execute(
            "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (1, 'tech_stack', 70, 'legacy')"
        )
        conn.execute("UPDATE schema_version SET version = 7")
        conn.commit()
        conn.close()

        init_db(tmp_db)

        conn = get_conn(tmp_db)
        try:
            row = dict(conn.execute("SELECT * FROM offer_topics WHERE offer_id = 1").fetchone())
        finally:
            conn.close()
        assert row["confidence"] is None

    def test_migration_idempotent(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 7")
        conn.commit()
        conn.close()

        init_db(tmp_db)
        init_db(tmp_db)  # must not raise on the second pass

        conn = get_conn(tmp_db)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        finally:
            conn.close()
        assert version == SCHEMA_VERSION


class TestMigrationV8ToV9:
    """`weights_used` shipped with no backfill by design — there is no honest
    way to invent a weight config nobody recorded for offers scored before
    this migration existed."""

    def test_existing_offer_rows_get_null_weights_used(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company, compatibility_pct) VALUES ('Backend Dev', 'Acme', 70)")
        conn.execute("UPDATE schema_version SET version = 8")
        conn.commit()
        conn.close()

        init_db(tmp_db)

        conn = get_conn(tmp_db)
        try:
            row = dict(conn.execute("SELECT * FROM offers WHERE title = 'Backend Dev'").fetchone())
        finally:
            conn.close()
        assert row["weights_used"] is None

    def test_migration_idempotent(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 8")
        conn.commit()
        conn.close()

        init_db(tmp_db)
        init_db(tmp_db)  # must not raise on the second pass

        conn = get_conn(tmp_db)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        finally:
            conn.close()
        assert version == SCHEMA_VERSION

    def test_fresh_install_has_weights_used_column(self, tmp_db):
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(offers)").fetchall()}
        finally:
            conn.close()
        assert "weights_used" in columns


@pytest.mark.unit
class TestMigrationV9ToV10:
    """`company` used to be fully optional, which let `add` create offers no
    duplicate check could ever match again and no follow-up could act on.
    This migration rebuilds `offers` with company NOT NULL + non-empty,
    backfilling any pre-existing empty/NULL value with a placeholder."""

    def _seed_v9(self, tmp_path, company):
        """Build a standalone v9 database from scratch (never through tmp_db,
        which already has the v10 CHECK constraint active) so a bad company
        value can legitimately be inserted, matching the pattern used for the
        v7/v8 migration tests above."""
        import sqlite3

        db_path = str(tmp_path / "v9.db")
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE offers (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                title             TEXT    NOT NULL,
                company           TEXT,
                summary           TEXT,
                date_received     TEXT,
                date_applied      TEXT,
                date_responded    TEXT,
                compatibility_pct INTEGER DEFAULT 0,
                status            TEXT    DEFAULT 'pending',
                applied           INTEGER DEFAULT 0,
                canal             TEXT,
                cv_used           TEXT,
                follow_up_date    TEXT,
                follow_up_done    INTEGER DEFAULT 0,
                follow_up_notes   TEXT,
                work_mode         TEXT,
                location          TEXT,
                salary_min        INTEGER,
                salary_max        INTEGER,
                salary_period     TEXT    DEFAULT 'annual',
                seniority_level   TEXT,
                role_category     TEXT,
                tech_stack        TEXT,
                language          TEXT,
                cover_letter      INTEGER DEFAULT 0,
                cover_letter_file TEXT,
                contact_name      TEXT,
                contact_role      TEXT,
                job_url           TEXT,
                rejection_reason  TEXT,
                response_status   TEXT    DEFAULT 'no_response',
                notes             TEXT,
                created_at        TEXT    DEFAULT CURRENT_TIMESTAMP,
                weights_used      TEXT
            );
            CREATE TABLE offer_topics (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id   INTEGER REFERENCES offers(id) ON DELETE CASCADE,
                topic      TEXT,
                score      INTEGER,
                detail     TEXT,
                confidence TEXT
            );
            CREATE TABLE learning_gaps (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id        INTEGER REFERENCES offers(id) ON DELETE CASCADE,
                topic           TEXT NOT NULL,
                gap_detail      TEXT NOT NULL,
                severity        TEXT DEFAULT 'medium',
                suggested_action TEXT,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        """)
        conn.execute(
            "INSERT INTO offers (title, company, compatibility_pct) VALUES (?, ?, ?)",
            ("Legacy offer", company, 55),
        )
        conn.execute(
            "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (1, 'tech_stack', 55, 'legacy')"
        )
        conn.execute(
            "INSERT INTO learning_gaps (offer_id, topic, gap_detail) VALUES (1, 'tech_stack', 'legacy gap')"
        )
        conn.execute("INSERT INTO schema_version (version) VALUES (9)")
        conn.commit()
        conn.close()
        return db_path

    def test_null_company_is_backfilled_with_a_placeholder(self, tmp_path):
        db_path = self._seed_v9(tmp_path, None)
        init_db(db_path)
        conn = get_conn(db_path)
        try:
            row = conn.execute("SELECT company FROM offers WHERE id = 1").fetchone()
        finally:
            conn.close()
        assert row["company"]  # non-empty
        assert row["company"] != "None"

    def test_empty_string_company_is_backfilled_with_a_placeholder(self, tmp_path):
        db_path = self._seed_v9(tmp_path, "   ")
        init_db(db_path)
        conn = get_conn(db_path)
        try:
            row = conn.execute("SELECT company FROM offers WHERE id = 1").fetchone()
        finally:
            conn.close()
        assert row["company"].strip()

    def test_real_company_is_preserved_unchanged(self, tmp_path):
        db_path = self._seed_v9(tmp_path, "Acme")
        init_db(db_path)
        conn = get_conn(db_path)
        try:
            row = conn.execute("SELECT company FROM offers WHERE id = 1").fetchone()
        finally:
            conn.close()
        assert row["company"] == "Acme"

    def test_offer_topics_and_learning_gaps_survive_the_rebuild(self, tmp_path):
        """The regression this migration almost shipped with: rebuilding
        `offers` while `PRAGMA foreign_keys` is (even transiently) ON
        cascade-deletes every child row via ON DELETE CASCADE before the
        table is even dropped."""
        db_path = self._seed_v9(tmp_path, "Acme")
        init_db(db_path)
        conn = get_conn(db_path)
        try:
            topics = conn.execute("SELECT * FROM offer_topics WHERE offer_id = 1").fetchall()
            gaps = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchall()
        finally:
            conn.close()
        assert len(topics) == 1
        assert len(gaps) == 1

    def test_new_row_without_company_is_rejected(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO offers (title, company) VALUES ('X', NULL)")
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO offers (title, company) VALUES ('X', '')")
        finally:
            conn.close()

    def test_migration_idempotent(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 9")
        conn.commit()
        conn.close()

        init_db(tmp_db)
        init_db(tmp_db)  # must not raise on the second pass

        conn = get_conn(tmp_db)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        finally:
            conn.close()
        assert version == SCHEMA_VERSION


@pytest.mark.unit
class TestMigrationV12ToV13:
    """`job_description` and `cv_evidence_used` ship with no backfill, same
    reasoning as `weights_used` in TestMigrationV8ToV9: there is no honest way
    to invent a job posting or a verification run that never happened for
    offers recorded before this migration existed.

    Starts from v12, not v10: (10, 11) and (11, 12) are owned by the sibling
    feat/cc-visual-ui branch (copied verbatim into MIGRATIONS so this
    branch's own v10->v13 path stays complete — see the ownership note above
    SCHEMA_VERSION in db.py) and are that branch's own tests to cover, not
    this one's."""

    def test_existing_offer_rows_get_null_evidence_columns(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company, compatibility_pct) VALUES ('Backend Dev', 'Acme', 70)")
        conn.execute("UPDATE schema_version SET version = 12")
        conn.commit()
        conn.close()

        init_db(tmp_db)

        conn = get_conn(tmp_db)
        try:
            row = dict(conn.execute("SELECT * FROM offers WHERE title = 'Backend Dev'").fetchone())
        finally:
            conn.close()
        assert row["job_description"] is None
        assert row["cv_evidence_used"] is None

    def test_migration_idempotent(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 12")
        conn.commit()
        conn.close()

        init_db(tmp_db)
        init_db(tmp_db)  # must not raise on the second pass

        conn = get_conn(tmp_db)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        finally:
            conn.close()
        assert version == SCHEMA_VERSION

    def test_fresh_install_has_evidence_columns(self, tmp_db):
        init_db(tmp_db)
        conn = get_conn(tmp_db)
        try:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(offers)").fetchall()}
        finally:
            conn.close()
        assert "job_description" in columns
        assert "cv_evidence_used" in columns


@pytest.mark.unit
class TestSchemaWarningGoesToStderr:
    """A bare print() put a prose line above the payload of every `--json`
    command, so an agent parsing the output hit a JSONDecodeError on character
    one. applyr is built to be driven by agents; warnings are not data."""

    def _run(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 5,))
        conn.commit()
        conn.close()
        init_db(tmp_db)

    def test_nothing_reaches_stdout(self, tmp_db, capsys):
        self._run(tmp_db)
        assert capsys.readouterr().out == ""

    def test_the_warning_still_reaches_stderr(self, tmp_db, capsys):
        self._run(tmp_db)
        assert "newer than" in capsys.readouterr().err

    def test_a_current_database_warns_about_nothing(self, tmp_db, capsys):
        init_db(tmp_db)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "newer than" not in captured.err


class TestMigrationGapFailsCleanly:
    """P0 quality-gate item (roadmap doc, section 2): 'migration failures' is
    an explicit contract case to protect. MIGRATIONS has no gap for any
    version currently shipped, so this simulates one — a database whose
    schema_version has no defined path forward — rather than waiting for a
    real gap to exist to test the failure mode at all."""

    def _make_gapped_db(self, tmp_db, monkeypatch):
        """Create a v6 database with a migration gap (missing 6→7 path)."""
        gapped = dict(db_module.MIGRATIONS)
        del gapped[(6, 7)]
        monkeypatch.setattr(db_module, "MIGRATIONS", gapped)

        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 6")
        conn.commit()
        conn.close()

    def test_undefined_migration_path_raises_runtime_error(self, tmp_db, monkeypatch):
        self._make_gapped_db(tmp_db, monkeypatch)
        with pytest.raises(RuntimeError, match="No migration path from schema v6 to v7"):
            init_db(tmp_db)

    def test_gap_does_not_corrupt_the_stored_version(self, tmp_db, monkeypatch):
        """A failed migration must not silently mark the database as
        upgraded — schema_version stays at the last version that actually
        applied, not the target that was never reached."""
        self._make_gapped_db(tmp_db, monkeypatch)

        with pytest.raises(RuntimeError):
            init_db(tmp_db)

        conn = get_conn(tmp_db)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        finally:
            conn.close()
        assert version == 6


class TestMigrationFailureIsAStructuredCliError:
    """Same gap as above, but through the CLI entry point — confirms
    init_db()'s RuntimeError becomes a clean die(code='db_error'), not an
    unhandled traceback, per cli.py's existing `except Exception` around
    init_db() (see main(), the 'Commands that need DB initialized' block)."""

    def _make_gapped_db(self, tmp_db, monkeypatch):
        """Create a v6 database with a migration gap (missing 6→7 path)."""
        gapped = dict(db_module.MIGRATIONS)
        del gapped[(6, 7)]
        monkeypatch.setattr(db_module, "MIGRATIONS", gapped)

        conn = get_conn(tmp_db)
        conn.execute("UPDATE schema_version SET version = 6")
        conn.commit()
        conn.close()

    def test_migration_gap_dies_with_db_error_code(self, tmp_db, tmp_applyr, monkeypatch, capsys):
        self._make_gapped_db(tmp_db, monkeypatch)

        from applyr.cli import main
        import sys as sys_module
        monkeypatch.setattr(sys_module, "argv", ["applyr", "--json", "stats"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
        import json as json_module
        payload = json_module.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "db_error"
