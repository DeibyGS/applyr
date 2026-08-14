"""Tests for database schema and operations."""

import pytest
import sqlite3

from applyr.db import init_db, get_conn, SCHEMA_VERSION, VALID_STATUSES, VALID_CHANNELS, VALID_SEVERITIES


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
                "INSERT INTO offers (title) VALUES (?)", ("Test",)
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
            conn.execute("INSERT INTO offers (title) VALUES (?)", ("Test",))
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
            conn.execute("INSERT INTO offers (title) VALUES (?)", ("Test",))
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
            conn.execute("INSERT INTO offers (title) VALUES (?)", ("Test",))
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
            conn.execute("INSERT INTO offers (title) VALUES (?)", ("Test",))
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
            "INSERT INTO offers (title, status, applied, response_status) VALUES (?, ?, 0, 'no_response')",
            ("Backend Dev", status),
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
        conn.execute("INSERT INTO offers (title) VALUES ('Backend Dev')")
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
