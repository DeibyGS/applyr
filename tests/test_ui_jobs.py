"""Tests for the async intake pipeline (ADR-014): the `ui_jobs` table,
`applyr/ui/jobs.py`'s CRUD, `applyr/ui/pipeline_worker.py`'s extraction/
dedupe/state-machine, and the API surface + in-process worker wiring in
`applyr/ui/api.py` / `applyr/ui/server.py`.
"""

import asyncio
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from applyr.db import SCHEMA_VERSION, get_conn
from applyr.intake import create_intake
from applyr.ui import jobs as pipeline_jobs
from applyr.ui.pipeline_worker import extract_structured_data, process_one_job, process_pending_jobs
from applyr.ui.server import create_app


@pytest.fixture
def client(tmp_db):
    return TestClient(create_app())


def _make_intake_and_job(db_path, raw_text="Empresa: Acme\nPuesto: Backend Dev"):
    conn = get_conn(db_path)
    try:
        intake_row = create_intake(raw_text, conn=conn)
        job_row = pipeline_jobs.create_job(intake_row["id"], conn)
        conn.commit()
    finally:
        conn.close()
    return intake_row, job_row


@pytest.mark.unit
class TestMigration:

    def test_schema_version_is_14(self):
        assert SCHEMA_VERSION == 14

    def test_ui_jobs_table_exists_with_expected_defaults(self, tmp_db):
        intake_row, job_row = _make_intake_and_job(tmp_db)
        assert job_row["intake_id"] == intake_row["id"]
        assert job_row["state"] == "queued"
        assert job_row["retry_count"] == 0
        assert job_row["structured_data"] is None

    def test_state_check_constraint_rejects_invalid_value(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        conn = get_conn(tmp_db)
        try:
            with pytest.raises(Exception):  # sqlite3.IntegrityError
                conn.execute(
                    "UPDATE ui_jobs SET state = 'bogus' WHERE intake_id = ?",
                    (intake_row["id"],),
                )
                conn.commit()
        finally:
            conn.close()

    def test_intake_id_is_unique_one_job_per_intake_row(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        conn = get_conn(tmp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                pipeline_jobs.create_job(intake_row["id"], conn)
        finally:
            conn.close()


@pytest.mark.unit
class TestJobsCrud:

    def test_get_job_by_intake_returns_none_when_missing(self, tmp_db):
        assert pipeline_jobs.get_job_by_intake(999, db_path=tmp_db) is None

    def test_update_job_state_rejects_invalid_state(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        with pytest.raises(ValueError):
            pipeline_jobs.update_job_state(intake_row["id"], "bogus", db_path=tmp_db)

    def test_update_job_state_rejects_missing_job(self, tmp_db):
        with pytest.raises(ValueError):
            pipeline_jobs.update_job_state(999, "structuring", db_path=tmp_db)

    def test_structured_data_and_extraction_method_are_sticky(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        pipeline_jobs.update_job_state(
            intake_row["id"], "deduping",
            structured_data={"company": "Acme", "title": "Dev"},
            extraction_method="labeled",
            db_path=tmp_db,
        )
        after = pipeline_jobs.update_job_state(intake_row["id"], "pending_agent", db_path=tmp_db)
        assert after["structured_data"] == {"company": "Acme", "title": "Dev"}
        assert after["extraction_method"] == "labeled"

    def test_failed_step_and_error_message_are_not_sticky(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        pipeline_jobs.update_job_state(
            intake_row["id"], "failed", failed_step="structuring", error_message="boom",
            db_path=tmp_db,
        )
        after = pipeline_jobs.update_job_state(intake_row["id"], "queued", db_path=tmp_db)
        assert after["failed_step"] is None
        assert after["error_message"] is None

    def test_list_jobs_by_state_orders_oldest_first(self, tmp_db):
        i1, _ = _make_intake_and_job(tmp_db, "Empresa: A\nPuesto: X")
        i2, _ = _make_intake_and_job(tmp_db, "Empresa: B\nPuesto: Y")
        rows = pipeline_jobs.list_jobs_by_state("queued", db_path=tmp_db)
        assert [r["intake_id"] for r in rows] == [i1["id"], i2["id"]]

    def test_list_jobs_by_state_empty_args_returns_empty(self, tmp_db):
        assert pipeline_jobs.list_jobs_by_state(db_path=tmp_db) == []

    def test_retry_job_resets_a_failed_job(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        pipeline_jobs.update_job_state(
            intake_row["id"], "failed", failed_step="structuring", error_message="boom",
            db_path=tmp_db,
        )
        retried = pipeline_jobs.retry_job(intake_row["id"], db_path=tmp_db)
        assert retried["state"] == "queued"
        assert retried["retry_count"] == 1
        assert retried["failed_step"] is None
        assert retried["error_message"] is None

    def test_retry_job_rejects_non_failed_state(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        with pytest.raises(ValueError):
            pipeline_jobs.retry_job(intake_row["id"], db_path=tmp_db)

    def test_retry_job_rejects_missing_job(self, tmp_db):
        with pytest.raises(ValueError):
            pipeline_jobs.retry_job(999, db_path=tmp_db)

    def test_retries_are_never_automatic(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        pipeline_jobs.update_job_state(
            intake_row["id"], "failed", failed_step="structuring", error_message="boom",
            db_path=tmp_db,
        )
        processed = process_pending_jobs(db_path=tmp_db)
        assert processed == 0
        assert pipeline_jobs.get_job_by_intake(intake_row["id"], db_path=tmp_db)["state"] == "failed"


@pytest.mark.unit
class TestExtractStructuredData:

    def test_labeled_fields_spanish(self):
        d = extract_structured_data("Empresa: Acme Corp\nPuesto: Backend Dev")
        assert d == {
            "company": "Acme Corp",
            "title": "Backend Dev",
            "tech_stack": None,
            "extraction_method": "labeled",
        }

    def test_labeled_fields_english(self):
        d = extract_structured_data("Company: Acme Corp\nTitle: Backend Dev")
        assert d["company"] == "Acme Corp"
        assert d["title"] == "Backend Dev"
        assert d["extraction_method"] == "labeled"

    def test_labeled_tech_stack_is_captured(self):
        d = extract_structured_data("Empresa: Acme\nPuesto: Dev\nStack: Python, FastAPI")
        assert d["tech_stack"] == "Python, FastAPI"

    def test_heuristic_fallback_when_no_labels(self):
        d = extract_structured_data("Acme Corp\nBackend Dev\nWe are looking for...")
        assert d["company"] == "Acme Corp"
        assert d["title"] == "Backend Dev"
        assert d["extraction_method"] == "heuristic"

    def test_partial_labels_still_marked_heuristic(self):
        # Only "Empresa:" labeled — title falls back to the heuristic, and
        # the whole extraction is honestly marked as not-fully-labeled.
        d = extract_structured_data("Empresa: Acme Corp\nSome unlabeled title line")
        assert d["company"] == "Acme Corp"
        assert d["title"] == "Some unlabeled title line"
        assert d["extraction_method"] == "heuristic"

    def test_empty_text_returns_none_fields(self):
        d = extract_structured_data("   \n   ")
        assert d["company"] is None
        assert d["title"] is None
        assert d["extraction_method"] == "heuristic"

    def test_label_matching_is_case_insensitive(self):
        d = extract_structured_data("EMPRESA: Acme\nPUESTO: Dev")
        assert d["company"] == "Acme"
        assert d["title"] == "Dev"
        assert d["extraction_method"] == "labeled"


@pytest.mark.unit
class TestWorkerProcessing:

    def test_new_offer_reaches_pending_agent(self, tmp_db):
        intake_row, job_row = _make_intake_and_job(tmp_db)
        events = []
        final = process_one_job(job_row, on_event=events.append, db_path=tmp_db)
        assert final["state"] == "pending_agent"
        assert final["structured_data"] == {
            "company": "Acme", "title": "Backend Dev", "tech_stack": None,
            "extraction_method": "labeled",
        }
        assert [e["state"] for e in events] == ["structuring", "deduping", "pending_agent"]
        for e in events:
            assert e["intake_id"] == intake_row["id"]
            assert e["job_id"] == job_row["id"]

    def test_duplicate_offer_stops_at_duplicate_state(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company) VALUES ('Backend Dev', 'Acme')"
            )
            conn.commit()
            existing_offer_id = conn.execute(
                "SELECT id FROM offers WHERE company = 'Acme'"
            ).fetchone()["id"]
        finally:
            conn.close()

        _, job_row = _make_intake_and_job(tmp_db, "Empresa: Acme\nPuesto: Backend Dev\nExtra text")
        events = []
        final = process_one_job(job_row, on_event=events.append, db_path=tmp_db)
        assert final["state"] == "duplicate"
        assert final["duplicate_of_offer_id"] == existing_offer_id
        assert [e["state"] for e in events] == ["structuring", "deduping", "duplicate"]

    def test_process_pending_jobs_claims_queued_and_structuring(self, tmp_db):
        _, job_a = _make_intake_and_job(tmp_db, "Empresa: A\nPuesto: X")
        intake_b, job_b = _make_intake_and_job(tmp_db, "Empresa: B\nPuesto: Y")
        # Simulate a worker interrupted mid-step on job_b (crash-recovery case).
        pipeline_jobs.update_job_state(intake_b["id"], "structuring", db_path=tmp_db)

        processed = process_pending_jobs(db_path=tmp_db)

        assert processed == 2
        assert pipeline_jobs.get_job_by_intake(job_a["intake_id"], db_path=tmp_db)["state"] == "pending_agent"
        assert pipeline_jobs.get_job_by_intake(intake_b["id"], db_path=tmp_db)["state"] == "pending_agent"

    def test_process_pending_jobs_ignores_pending_agent_jobs(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        pipeline_jobs.update_job_state(intake_row["id"], "pending_agent", db_path=tmp_db)

        processed = process_pending_jobs(db_path=tmp_db)

        assert processed == 0
        assert pipeline_jobs.get_job_by_intake(intake_row["id"], db_path=tmp_db)["state"] == "pending_agent"

    def test_process_pending_jobs_is_a_noop_with_nothing_claimable(self, tmp_db):
        assert process_pending_jobs(db_path=tmp_db) == 0


@pytest.mark.unit
class TestPostIntakeCreatesPairedJob:

    def test_creates_intake_and_queued_job(self, client):
        resp = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["job"]["state"] == "queued"
        assert body["job"]["intake_id"] == body["id"]

    def test_double_submit_within_window_is_idempotent(self, client):
        r1 = client.post("/api/intake", json={"raw_text": "same paste"})
        r2 = client.post("/api/intake", json={"raw_text": "same paste"})
        assert r1.json()["id"] == r2.json()["id"]
        assert r1.json()["job"]["id"] == r2.json()["job"]["id"]

    def test_different_text_creates_separate_jobs(self, client):
        r1 = client.post("/api/intake", json={"raw_text": "first paste"})
        r2 = client.post("/api/intake", json={"raw_text": "second paste"})
        assert r1.json()["id"] != r2.json()["id"]

    def test_get_intake_list_includes_job(self, client):
        client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"})
        rows = client.get("/api/intake").json()
        assert rows[0]["job"] is not None
        assert rows[0]["job"]["state"] == "queued"

    def test_get_intake_one_includes_job(self, client):
        created = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}).json()
        row = client.get(f"/api/intake/{created['id']}").json()
        assert row["job"]["state"] == "queued"


@pytest.mark.unit
class TestRetryEndpoint:

    def test_retry_missing_job_is_404(self, client):
        resp = client.post("/api/intake/9999/retry")
        assert resp.status_code == 404

    def test_retry_non_failed_job_is_409(self, client):
        created = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}).json()
        resp = client.post(f"/api/intake/{created['id']}/retry")
        assert resp.status_code == 409

    def test_retry_failed_job_resets_to_queued(self, client, tmp_db):
        created = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}).json()
        pipeline_jobs.update_job_state(
            created["id"], "failed", failed_step="structuring", error_message="boom", db_path=tmp_db
        )
        resp = client.post(f"/api/intake/{created['id']}/retry")
        assert resp.status_code == 200
        assert resp.json()["state"] == "queued"
        assert resp.json()["retry_count"] == 1


@pytest.mark.unit
class TestInternalJobStateEndpoint:

    def test_rejects_invalid_state(self, client):
        resp = client.post("/api/internal/job-state", json={"intake_id": 1, "state": "bogus"})
        assert resp.status_code == 422

    def test_missing_job_is_404(self, client):
        resp = client.post("/api/internal/job-state", json={"intake_id": 9999, "state": "ready"})
        assert resp.status_code == 404

    def test_ready_updates_job_state(self, client, tmp_db):
        created = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}).json()
        resp = client.post(
            "/api/internal/job-state", json={"intake_id": created["id"], "state": "ready"}
        )
        assert resp.status_code == 204
        assert pipeline_jobs.get_job_by_intake(created["id"], db_path=tmp_db)["state"] == "ready"

    def test_failed_records_the_error_message(self, client, tmp_db):
        created = client.post("/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}).json()
        client.post(
            "/api/internal/job-state",
            json={"intake_id": created["id"], "state": "failed", "error_message": "add failed"},
        )
        job = pipeline_jobs.get_job_by_intake(created["id"], db_path=tmp_db)
        assert job["state"] == "failed"
        assert job["failed_step"] == "pending_agent"
        assert job["error_message"] == "add failed"

    def test_fans_out_to_a_subscribed_queue(self, tmp_db):
        from applyr.ui.api import _enriched_event_subscribers, post_job_state, JobStateEvent

        intake_row, _ = _make_intake_and_job(tmp_db)

        async def run():
            queue: asyncio.Queue = asyncio.Queue()
            _enriched_event_subscribers.add(queue)
            try:
                await post_job_state(JobStateEvent(intake_id=intake_row["id"], state="ready"))
                event = await asyncio.wait_for(queue.get(), timeout=1)
                assert event["type"] == "job.state_changed"
                assert event["intake_id"] == intake_row["id"]
                assert event["state"] == "ready"
            finally:
                _enriched_event_subscribers.discard(queue)

        asyncio.run(run())


@pytest.mark.unit
class TestWorkerLifecycle:

    def test_worker_starts_with_the_app_and_processes_a_submitted_job(self, tmp_db):
        with TestClient(create_app()) as client:
            created = client.post(
                "/api/intake", json={"raw_text": "Empresa: Acme\nPuesto: Dev"}
            ).json()

            state = None
            for _ in range(20):
                state = client.get(f"/api/intake/{created['id']}").json()["job"]["state"]
                if state == "pending_agent":
                    break
                time.sleep(0.1)

            assert state == "pending_agent"
