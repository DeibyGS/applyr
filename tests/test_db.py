"""Tests for database schema and operations."""

import pytest
import sqlite3

from applyr.db import init_db, get_conn, SCHEMA_VERSION, VALID_STATUSES, VALID_CHANNELS


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
        assert row["version"] == 2
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
