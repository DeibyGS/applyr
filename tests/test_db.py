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
            assert "skill_gaps" in names
            assert "schema_version" in names
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

    def test_skill_gaps_upsert(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO skill_gaps (skill, frequency, total_gap, last_seen) VALUES (?, ?, ?, ?)",
                ("python", 1, 20, "2026-01-01"),
            )
            conn.execute(
                """INSERT INTO skill_gaps (skill, frequency, total_gap, last_seen)
                   VALUES (?, 1, ?, ?)
                   ON CONFLICT(skill) DO UPDATE SET
                       frequency = frequency + 1,
                       total_gap = total_gap + excluded.total_gap,
                       last_seen = excluded.last_seen""",
                ("python", 15, "2026-02-01"),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM skill_gaps WHERE skill = 'python'").fetchone()
            assert row["frequency"] == 2
            assert row["total_gap"] == 35
            assert row["last_seen"] == "2026-02-01"
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
