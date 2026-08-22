"""Adversarial verification for the Visual UI slice 1 contract.

Independent of the implementer's tests — derives expected behavior from the
contract in the task brief (ui_intake migration, `add --intake-id`
atomicity/idempotency, and the read-only `GET /api/jobs*` surface), not from
reading applyr/intake.py / applyr/ui/api.py first.

Run: python3 -m pytest tests/test_visual_ui_slice1.adversarial.test.py -q
"""

import sqlite3
import threading

import pytest

pytest.importorskip("fastapi", reason="requires the optional applyr[ui] extra")
from fastapi.testclient import TestClient

from applyr.commands.core import cmd_add
from applyr.db import get_conn, init_db, SCHEMA_VERSION
from applyr.intake import create_intake, get_intake
from applyr.ui.server import create_app


def _offer_count(db_path):
    conn = get_conn(db_path)
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM offers").fetchone()["c"]
    finally:
        conn.close()


@pytest.mark.unit
class TestIntakeIdAtomicity:
    """`add --intake-id` MUST succeed or fail as one unit — never a
    half-created offer, never a silently re-promoted intake row."""

    def test_nonexistent_intake_id_creates_no_offer(self, tmp_db):
        with pytest.raises(SystemExit):
            cmd_add('{"title": "Dev", "company": "Acme"}', intake_id=999999)
        assert _offer_count(tmp_db) == 0

    def test_already_promoted_intake_id_creates_no_duplicate_offer(self, tmp_db):
        intake = create_intake("some posting", db_path=tmp_db)
        cmd_add(f'{{"title": "First", "company": "Acme"}}', intake_id=intake["id"])
        assert _offer_count(tmp_db) == 1

        with pytest.raises(SystemExit):
            cmd_add('{"title": "Second", "company": "Acme"}', intake_id=intake["id"])
        # No second offer should have been created off the already-promoted row.
        assert _offer_count(tmp_db) == 1

    def test_already_promoted_intake_row_is_untouched_by_the_failed_retry(self, tmp_db):
        intake = create_intake("some posting", db_path=tmp_db)
        cmd_add('{"title": "First", "company": "Acme"}', intake_id=intake["id"])
        promoted_before = get_intake(intake["id"], db_path=tmp_db)

        with pytest.raises(SystemExit):
            cmd_add('{"title": "Second", "company": "Other Co"}', intake_id=intake["id"])
        promoted_after = get_intake(intake["id"], db_path=tmp_db)

        assert promoted_after["offer_id"] == promoted_before["offer_id"] == 1
        assert promoted_after["promoted_at"] == promoted_before["promoted_at"]

    def test_unrelated_failure_after_offer_insert_rolls_back_everything(self, tmp_db):
        """A die() triggered by something unrelated to intake_id (bad
        confidence value on a topic) fires *after* the offer INSERT has
        already executed in the same uncommitted transaction. The contract's
        promise ("same transaction ... succeeds or fails as one unit")
        implies this failure must roll back the offer too, not just skip the
        intake promotion."""
        intake = create_intake("some posting", db_path=tmp_db)
        payload = (
            '{"title": "Dev", "company": "Acme", '
            '"topics": {"tech_stack": {"score": 80, "detail": "ok", "confidence": "not-a-real-level"}}}'
        )
        with pytest.raises(SystemExit):
            cmd_add(payload, intake_id=intake["id"])

        assert _offer_count(tmp_db) == 0
        row = get_intake(intake["id"], db_path=tmp_db)
        assert row["status"] == "pending"
        assert row["offer_id"] is None

    def test_successful_promotion_sets_offer_id_and_promoted_at(self, tmp_db):
        intake = create_intake("some posting", db_path=tmp_db)
        cmd_add('{"title": "Dev", "company": "Acme"}', intake_id=intake["id"])
        row = get_intake(intake["id"], db_path=tmp_db)
        assert row["status"] == "promoted"
        assert row["offer_id"] == 1
        assert row["promoted_at"] is not None

    def test_add_without_intake_id_never_touches_ui_intake(self, tmp_db):
        """Regression guard for the byte-for-byte-identical-behavior AC:
        today's usage (no --intake-id) must not create or mutate any
        ui_intake row."""
        create_intake("untouched pending row", db_path=tmp_db)
        cmd_add('{"title": "Dev", "company": "Acme"}')
        conn = get_conn(tmp_db)
        try:
            rows = conn.execute("SELECT status, offer_id FROM ui_intake").fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"
        assert rows[0]["offer_id"] is None


@pytest.mark.unit
class TestIntakePromotionConcurrency:
    """Idempotency risk: two near-simultaneous `add --intake-id` calls
    against the same row (double-submit from the dashboard, or a naive
    client retry) must not both succeed."""

    def test_two_concurrent_promotions_of_the_same_row_do_not_both_succeed(self, tmp_db):
        intake = create_intake("racy posting", db_path=tmp_db)
        results = []
        barrier = threading.Barrier(2)

        def worker(company):
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            try:
                cmd_add(f'{{"title": "Dev", "company": "{company}"}}', intake_id=intake["id"])
                results.append("ok")
            except SystemExit:
                results.append("fail")
            except sqlite3.OperationalError as exc:
                # A locked-database error surfacing to the caller as an
                # unhandled exception (rather than a clean die()) would
                # itself be a defect worth flagging separately.
                results.append(f"db_error:{exc}")

        t1 = threading.Thread(target=worker, args=("Acme",))
        t2 = threading.Thread(target=worker, args=("Other Co",))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results.count("ok") == 1, f"expected exactly one success, got {results}"
        assert _offer_count(tmp_db) == 1, "double promotion created more than one offer"


@pytest.mark.unit
class TestMigrationDataIntegrity:

    def _seed_v10_db(self, tmp_path):
        """Build a schema-v10 database (pre-ui_intake) with real data, the
        same way test_db.py's `_seed_v9` helper builds a pre-migration
        fixture — hand-rolled SQL, not init_db(), so it reflects what a
        database looked like *before* this slice, independent of the
        current SCHEMA_SQL string."""
        db_path = str(tmp_path / "v10.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL CHECK (length(trim(company)) > 0),
                compatibility_pct INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE offer_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
                topic TEXT, score INTEGER, detail TEXT, confidence TEXT
            );
            CREATE TABLE learning_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
                topic TEXT NOT NULL, gap_detail TEXT NOT NULL,
                severity TEXT DEFAULT 'medium', suggested_action TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
            INSERT INTO offers (title, company, compatibility_pct, status)
                VALUES ('Real Offer', 'RealCo', 88, 'applied');
            INSERT INTO offer_topics (offer_id, topic, score, detail, confidence)
                VALUES (1, 'tech_stack', 90, 'strong match', 'high');
            INSERT INTO learning_gaps (offer_id, topic, gap_detail)
                VALUES (1, 'english', 'needs more practice');
            INSERT INTO schema_version (version) VALUES (10);
            """
        )
        conn.commit()
        conn.close()
        return db_path

    def test_upgrade_from_v10_preserves_existing_offers_topics_gaps(self, tmp_path):
        db_path = self._seed_v10_db(tmp_path)
        init_db(db_path)

        conn = get_conn(db_path)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
            offer = conn.execute("SELECT * FROM offers WHERE id = 1").fetchone()
            topic = conn.execute("SELECT * FROM offer_topics WHERE offer_id = 1").fetchone()
            gap = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchone()
            # ui_intake must exist post-upgrade and be usable.
            conn.execute("SELECT * FROM ui_intake").fetchall()
        finally:
            conn.close()

        assert version == SCHEMA_VERSION
        assert offer["title"] == "Real Offer"
        assert offer["company"] == "RealCo"
        assert offer["compatibility_pct"] == 88
        assert topic["score"] == 90
        assert gap["gap_detail"] == "needs more practice"

    def test_migration_applied_exactly_once_reopening_is_a_noop(self, tmp_path):
        db_path = self._seed_v10_db(tmp_path)
        init_db(db_path)
        # Re-opening (any command run after upgrade) must not error and
        # must not double-apply the (10, 11) migration.
        init_db(db_path)
        init_db(db_path)

        conn = get_conn(db_path)
        try:
            version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name='ui_intake'"
            ).fetchone()["c"]
        finally:
            conn.close()

        assert version == SCHEMA_VERSION
        assert count == 1


@pytest.mark.unit
class TestJobsReadApi:

    @pytest.fixture
    def client(self, tmp_db):
        return TestClient(create_app())

    def _seed_offers(self, tmp_db, n):
        conn = get_conn(tmp_db)
        try:
            for i in range(n):
                conn.execute(
                    "INSERT INTO offers (title, company, compatibility_pct) VALUES (?, ?, ?)",
                    (f"Role {i}", f"Company {i}", i),
                )
            conn.commit()
        finally:
            conn.close()

    def test_get_jobs_returns_every_row_with_no_pagination(self, client, tmp_db):
        self._seed_offers(tmp_db, 37)
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) == 37

    def test_job_detail_never_recomputes_compatibility_pct(self, client, tmp_db):
        """Deliberately store a compatibility_pct that is inconsistent with
        the topic scores (as if it were overridden or scored under
        different weights). The read API must mirror the stored value
        verbatim, never recompute it from the topics it also returns."""
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, compatibility_pct) VALUES ('Dev', 'Acme', 42)"
            )
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score, detail, confidence) "
                "VALUES (1, 'tech_stack', 100, 'perfect', 'high')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/jobs/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["compatibility_pct"] == 42, (
            "UI backend appears to have recomputed compatibility_pct from "
            "topic scores instead of mirroring the stored value"
        )

    def test_job_detail_404_uses_the_standard_error_shape(self, client):
        resp = client.get("/api/jobs/999")
        assert resp.status_code == 404
        body = resp.json()
        assert body == {
            "error": True,
            "code": "not_found",
            "message": "No offer with id 999",
        }
