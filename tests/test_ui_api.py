"""Tests for applyr/ui/api.py — the Visual UI backend's HTTP routes."""

import asyncio
import json

import pytest

pytest.importorskip("fastapi", reason="requires the optional applyr[ui] extra")
from fastapi.testclient import TestClient

from applyr.db import get_conn
from applyr.intake import mark_intake_promoted
from applyr.ui.server import create_app


@pytest.fixture
def client(tmp_db):
    return TestClient(create_app())


@pytest.mark.unit
class TestHealth:

    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.unit
class TestConfig:

    def test_returns_default_thresholds(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"threshold_apply", "threshold_maybe"}
        assert isinstance(body["threshold_apply"], int)
        assert isinstance(body["threshold_maybe"], int)

    def test_returns_the_users_actual_configured_thresholds(self, client, tmp_applyr):
        (tmp_applyr / "applyr.toml").write_text(
            "[general]\nthreshold_apply = 65\nthreshold_maybe = 55\n"
        )
        resp = client.get("/api/config")
        assert resp.status_code == 200
        assert resp.json() == {"threshold_apply": 65, "threshold_maybe": 55}

    def test_never_exposes_the_full_config_file(self, client, tmp_applyr):
        (tmp_applyr / "applyr.toml").write_text(
            "[general]\nthreshold_apply = 65\nthreshold_maybe = 55\n"
            'chrome_path = "/some/local/marker/value"\n'
        )
        resp = client.get("/api/config")
        assert "chrome_path" not in resp.text
        assert "/some/local/marker/value" not in resp.text


@pytest.mark.unit
class TestSettingsEndpoint:

    def test_returns_thresholds_and_raw_weights(self, client, tmp_applyr):
        (tmp_applyr / "cv-master.md").write_text("# CV Master\n\n" + "Real experience. " * 50)
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["threshold_apply"] == 80
        assert body["threshold_maybe"] == 60
        assert body["weights"]["tech_stack"] == 35
        assert body["cv_master_status"] == "ok"

    def test_warning_status_when_cv_master_missing(self, client, tmp_applyr):
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cv_master_status"] == "warning"

    def test_warning_status_when_cv_master_too_thin(self, client, tmp_applyr):
        (tmp_applyr / "cv-master.md").write_text("# CV Master\n\nDeveloper.\n")
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        assert resp.json()["cv_master_status"] == "warning"

    def test_never_exposes_a_filesystem_path(self, client, tmp_applyr):
        (tmp_applyr / "cv-master.md").write_text("# CV Master\n\n" + "Real experience. " * 50)
        resp = client.get("/api/settings")
        assert str(tmp_applyr) not in resp.text
        assert "cv-master.md" not in resp.text

    def test_never_exposes_a_filesystem_path_when_cv_master_is_missing(self, client, tmp_applyr):
        # Exercises the "NOT FOUND" branch specifically — the sibling test
        # above only ever writes a filled cv-master.md, so it exercises the
        # "ok" .replace() branch and never actually proves this one strips
        # the path too.
        resp = client.get("/api/settings")
        assert resp.json()["cv_master_status"] == "warning"
        assert str(tmp_applyr) not in resp.text
        assert "cv-master.md" not in resp.text

    def test_never_exposes_the_full_config_file(self, client, tmp_applyr):
        (tmp_applyr / "applyr.toml").write_text(
            "[general]\nthreshold_apply = 65\nthreshold_maybe = 55\n"
            'chrome_path = "/some/local/marker/value"\n'
        )
        resp = client.get("/api/settings")
        assert "chrome_path" not in resp.text
        assert "/some/local/marker/value" not in resp.text


@pytest.mark.unit
class TestIntakeEndpoints:

    def test_create_intake(self, client):
        resp = client.post("/api/intake", json={"raw_text": "Some job posting"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["raw_text"] == "Some job posting"

    def test_create_intake_blank_raw_text_is_422(self, client):
        resp = client.post("/api/intake", json={"raw_text": "   "})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] is True
        assert body["code"] == "invalid_value"

    def test_create_intake_missing_field_is_422(self, client):
        resp = client.post("/api/intake", json={})
        assert resp.status_code == 422
        assert resp.json()["error"] is True

    def test_list_intake_newest_first(self, client):
        client.post("/api/intake", json={"raw_text": "first"})
        client.post("/api/intake", json={"raw_text": "second"})
        resp = client.get("/api/intake")
        assert resp.status_code == 200
        assert [row["raw_text"] for row in resp.json()] == ["second", "first"]

    def test_list_intake_filtered_by_status(self, client, tmp_db):
        created = client.post("/api/intake", json={"raw_text": "job"}).json()
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(created["id"], offer_id=1, conn=conn)
            conn.commit()
        finally:
            conn.close()

        assert client.get("/api/intake", params={"status": "pending"}).json() == []
        promoted = client.get("/api/intake", params={"status": "promoted"}).json()
        assert len(promoted) == 1
        assert promoted[0]["id"] == created["id"]

    def test_get_intake_404(self, client):
        resp = client.get("/api/intake/999")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] is True
        assert body["code"] == "not_found"

    def test_get_intake_found(self, client):
        created = client.post("/api/intake", json={"raw_text": "job"}).json()
        resp = client.get(f"/api/intake/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]


@pytest.mark.unit
class TestJobsEndpoints:

    def _seed_offer(self, tmp_db, title="Backend Dev", company="Acme", compatibility_pct=75):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, compatibility_pct) VALUES (?, ?, ?)",
                (title, company, compatibility_pct),
            )
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score, detail, confidence) "
                "VALUES (1, 'tech_stack', 80, 'solid', 'high')"
            )
            conn.commit()
        finally:
            conn.close()

    def test_list_jobs_empty(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_jobs_core_fields_no_topics(self, client, tmp_db):
        self._seed_offer(tmp_db)
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        jobs = resp.json()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Backend Dev"
        assert jobs[0]["compatibility_pct"] == 75
        assert "topics" not in jobs[0]

    def test_list_jobs_exposes_pipeline_stage_for_the_office_scene(self, client, tmp_db):
        # ADR-013: OfficeScene needs this to place in-flight offers at their
        # real zone on load, without waiting for a live SSE event.
        self._seed_offer(tmp_db)
        conn = get_conn(tmp_db)
        conn.execute("UPDATE offers SET pipeline_stage = 'cv' WHERE id = 1")
        conn.commit()
        conn.close()

        resp = client.get("/api/jobs")
        assert resp.json()[0]["pipeline_stage"] == "cv"

    def test_list_jobs_pipeline_stage_is_null_when_untracked(self, client, tmp_db):
        self._seed_offer(tmp_db)
        resp = client.get("/api/jobs")
        assert resp.json()[0]["pipeline_stage"] is None

    def test_job_detail_404(self, client):
        resp = client.get("/api/jobs/999")
        assert resp.status_code == 404
        assert resp.json()["code"] == "not_found"

    def test_job_detail_includes_full_topic_breakdown(self, client, tmp_db):
        self._seed_offer(tmp_db)
        resp = client.get("/api/jobs/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Backend Dev"
        assert body["topics"] == [
            {"topic": "tech_stack", "score": 80, "detail": "solid", "confidence": "high"}
        ]


@pytest.mark.unit
class TestStatsEndpoint:

    def test_empty_database_returns_total_zero_not_error(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        assert resp.json() == {"total": 0}

    def test_matches_cmd_stats_json_shape(self, client, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, status, compatibility_pct, "
                "weights_used, canal, work_mode, salary_min) "
                "VALUES ('Dev', 'Acme', 'applied', 80, 'v1', 'linkedin_easy', 'remote', 40000)"
            )
            conn.execute(
                "INSERT INTO offers (title, company, status, compatibility_pct, weights_used) "
                "VALUES ('QA', 'Beta', 'offer', 90, 'v1')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["funnel"] == {"applied": 2, "responded": 1, "interview": 0, "offer": 1}
        assert body["funnel_pct"]["applied"] == 100
        assert body["channels"] == {"linkedin_easy": 1}
        assert body["work_modes"] == {"remote": 1}
        assert body["salary"] == {"min": 40000, "max": 40000, "avg": 40000, "median": 40000, "count": 1}


@pytest.mark.unit
class TestTrendsEndpoint:

    def test_no_dated_offers_returns_empty_list(self, client):
        resp = client.get("/api/trends")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_default_period_is_week(self, client, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, date_applied) "
                "VALUES ('Dev', 'Acme', '2026-08-10')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/trends")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["count"] == 1

    def test_invalid_period_is_400(self, client):
        resp = client.get("/api/trends", params={"period": "year"})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] is True

    def test_valid_work_mode_filter_narrows_results_over_http(self, client, tmp_db):
        """End-to-end check that GET /api/trends actually threads its filter
        Query params into _trends_payload — the other trends filter tests
        either call _trends_payload directly (bypassing the route) or only
        exercise the 400 invalid-value path, so a param-name mismatch in the
        route wiring itself would slip through undetected without this."""
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, date_applied, work_mode) "
                "VALUES ('Dev', 'Acme', '2026-08-10', 'remote')"
            )
            conn.execute(
                "INSERT INTO offers (title, company, date_applied, work_mode) "
                "VALUES ('QA', 'Beta', '2026-08-11', 'onsite')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/trends", params={"work_mode": "remote"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["count"] == 1

    def test_month_period(self, client, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, date_applied) "
                "VALUES ('Dev', 'Acme', '2026-08-10')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/trends", params={"period": "month"})
        assert resp.status_code == 200
        assert resp.json()[0]["period"] == "2026-08"


@pytest.mark.unit
class TestAnalyticsFilterValidation:
    """`work_mode`/`canal`/`seniority_level`/`role_category` on /api/stats and
    /api/trends must reject a value outside the existing VALID_* enums in
    db.py with a 400 and the app's structured JSON error shape, not a silent
    no-op filter (spec: analytics-filters-and-fixes)."""

    @pytest.mark.parametrize("param,value", [
        ("work_mode", "flying"),
        ("canal", "carrier_pigeon"),
        ("seniority_level", "wizard"),
        ("role_category", "space"),
    ])
    def test_invalid_value_is_400_on_stats(self, client, param, value):
        resp = client.get("/api/stats", params={param: value})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] is True

    @pytest.mark.parametrize("param,value", [
        ("work_mode", "flying"),
        ("canal", "carrier_pigeon"),
        ("seniority_level", "wizard"),
        ("role_category", "space"),
    ])
    def test_invalid_value_is_400_on_trends(self, client, param, value):
        resp = client.get("/api/trends", params={param: value})
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] is True

    def test_valid_filters_apply_and_return_200(self, client, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, work_mode) VALUES ('Dev', 'Acme', 'remote')"
            )
            conn.execute(
                "INSERT INTO offers (title, company, work_mode) VALUES ('QA', 'Beta', 'onsite')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/stats", params={"work_mode": "remote"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_filter_matching_nothing_is_distinguishable_from_empty_db(self, client, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, work_mode) VALUES ('Dev', 'Acme', 'remote')"
            )
            conn.commit()
        finally:
            conn.close()

        resp = client.get("/api/stats", params={"work_mode": "onsite"})
        assert resp.status_code == 200
        assert resp.json() == {"total": 0, "filtered": True}


@pytest.mark.unit
class TestCors:

    def test_allows_the_vite_dev_origin(self, client):
        resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.unit
class TestPipelineStageEvents:
    """ADR-013: POST /api/internal/pipeline-stage is the CLI's fire-and-forget
    notification target; GET /api/events is the SSE stream the frontend
    subscribes to. The CLI already writes `pipeline_stage` to the database
    itself (see tests/test_ui_events.py) — this endpoint only fans the event
    out to connected clients, so these tests cover the fan-out, not
    persistence.

    The fan-out/streaming tests below drive the route functions directly
    with asyncio rather than through TestClient's HTTP transport: an SSE
    response never terminates on its own, and TestClient's stream() plus a
    second thread issuing the POST deadlocked in practice (both share one
    event loop) — driving the async generator's __anext__() by hand is
    deterministic and avoids that entirely."""

    def test_rejects_a_stage_outside_the_enum(self, client):
        resp = client.post("/api/internal/pipeline-stage", json={"offer_id": 1, "stage": "recruiter"})
        assert resp.status_code == 422

    def test_accepts_every_valid_stage(self, client):
        for stage in ("matching", "cv", "ats", "application"):
            resp = client.post("/api/internal/pipeline-stage", json={"offer_id": 1, "stage": stage})
            assert resp.status_code == 204

    def test_posting_with_no_connected_clients_does_not_error(self, client):
        # The common case: the CLI notifies, nobody has the Office page open.
        resp = client.post("/api/internal/pipeline-stage", json={"offer_id": 1, "stage": "cv"})
        assert resp.status_code == 204

    def test_fans_out_to_a_subscribed_queue(self):
        from applyr.ui.api import PipelineStageEvent, _event_subscribers, post_pipeline_stage

        async def run():
            queue: asyncio.Queue = asyncio.Queue()
            _event_subscribers.add(queue)
            try:
                await post_pipeline_stage(PipelineStageEvent(offer_id=42, stage="ats"))
                event = await asyncio.wait_for(queue.get(), timeout=1)
                assert event["offer_id"] == 42
                assert event["stage"] == "ats"
                assert isinstance(event["pipeline_stage_at"], str) and event["pipeline_stage_at"]
            finally:
                _event_subscribers.discard(queue)

        asyncio.run(run())

    def test_fans_out_to_every_subscribed_queue(self):
        from applyr.ui.api import PipelineStageEvent, _event_subscribers, post_pipeline_stage

        async def run():
            queue_a: asyncio.Queue = asyncio.Queue()
            queue_b: asyncio.Queue = asyncio.Queue()
            _event_subscribers.update({queue_a, queue_b})
            try:
                await post_pipeline_stage(PipelineStageEvent(offer_id=7, stage="matching"))
                event_a = await asyncio.wait_for(queue_a.get(), timeout=1)
                event_b = await asyncio.wait_for(queue_b.get(), timeout=1)
                assert event_a == event_b
                assert event_a["offer_id"] == 7
                assert event_a["stage"] == "matching"
            finally:
                _event_subscribers.difference_update({queue_a, queue_b})

        asyncio.run(run())

    def test_stream_yields_sse_formatted_data_for_a_posted_event(self):
        from applyr.ui.api import PipelineStageEvent, post_pipeline_stage, stream_events

        async def run():
            response = await stream_events()
            agen = response.body_iterator
            pending = asyncio.ensure_future(agen.__anext__())
            await asyncio.sleep(0.05)  # let the generator subscribe before posting
            await post_pipeline_stage(PipelineStageEvent(offer_id=7, stage="matching"))
            chunk = await asyncio.wait_for(pending, timeout=1)
            assert chunk.startswith("data: ") and chunk.endswith("\n\n")
            event = json.loads(chunk[len("data: "):-len("\n\n")])
            assert event["offer_id"] == 7
            assert event["stage"] == "matching"
            assert isinstance(event["pipeline_stage_at"], str) and event["pipeline_stage_at"]
            await agen.aclose()

        asyncio.run(run())

    def test_disconnecting_removes_the_queue_from_subscribers(self):
        from applyr.ui.api import _event_subscribers, stream_events

        async def run():
            before = len(_event_subscribers)
            response = await stream_events()
            agen = response.body_iterator
            pending = asyncio.ensure_future(agen.__anext__())
            await asyncio.sleep(0.05)
            assert len(_event_subscribers) == before + 1
            # Cancelling the in-flight __anext__() is what a real client
            # disconnect looks like from the generator's side — it's
            # suspended on `await queue.get()`, and cancellation propagates
            # in right there, running the `finally` block. Calling aclose()
            # directly instead raises "already running", since the task
            # above still owns the generator's execution.
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert len(_event_subscribers) == before

        asyncio.run(run())
