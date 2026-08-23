"""Tests for applyr/ui/api.py — the Visual UI backend's HTTP routes."""

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
class TestCors:

    def test_allows_the_vite_dev_origin(self, client):
        resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
