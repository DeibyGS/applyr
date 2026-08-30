"""Adversarial-informed fixes for the async intake pipeline (ADR-014),
following /code-review medium findings on PR #116:

1. `run_worker`'s loop must survive a single job raising — the old code had
   no try/except, so one bad job silently killed the entire in-process
   worker until `applyr ui` was restarted.
2. Crash-recovery must also reclaim `deduping`, not just `queued`/
   `structuring` — a worker killed mid-dedupe-query orphaned that job.
3. `create_intake`'s idempotency guard (SELECT-then-INSERT) was not atomic
   under real concurrency — two connections could both see "nothing
   pending" before either committed.
4. Any `die()` inside `cmd_add --intake-id`, not just the intake-linkage
   failure, must notify the paired job as `failed` — otherwise it's stuck
   at `pending_agent` forever with no retry path.
"""

import sqlite3
import threading

import pytest

from applyr.db import get_conn
from applyr.intake import create_intake
from applyr.ui import jobs as pipeline_jobs
from applyr.ui.pipeline_worker import process_pending_jobs


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
class TestWorkerSurvivesAJobFailure:

    def test_one_bad_job_does_not_stop_the_batch(self, tmp_db, monkeypatch):
        good_intake, _ = _make_intake_and_job(tmp_db, "Empresa: Good Co\nPuesto: Dev")
        bad_intake, _ = _make_intake_and_job(tmp_db, "Empresa: Bad Co\nPuesto: Dev")

        import applyr.ui.pipeline_worker as worker_mod

        real_extract = worker_mod.extract_structured_data
        call_count = {"n": 0}

        def flaky_extract(raw_text):
            call_count["n"] += 1
            if "Bad Co" in raw_text:
                raise RuntimeError("boom — simulated extraction crash")
            return real_extract(raw_text)

        monkeypatch.setattr(worker_mod, "extract_structured_data", flaky_extract)

        processed = process_pending_jobs(db_path=tmp_db)

        assert processed == 2
        good_job = pipeline_jobs.get_job_by_intake(good_intake["id"], db_path=tmp_db)
        bad_job = pipeline_jobs.get_job_by_intake(bad_intake["id"], db_path=tmp_db)
        assert good_job["state"] == "pending_agent"
        assert bad_job["state"] == "failed"
        assert bad_job["failed_step"] == "structuring"
        assert "boom" in bad_job["error_message"]

    def test_failed_job_from_a_crash_is_not_reclaimed_again(self, tmp_db, monkeypatch):
        intake_row, _ = _make_intake_and_job(tmp_db)
        import applyr.ui.pipeline_worker as worker_mod

        def always_raises(raw_text):
            raise RuntimeError("permanent failure")

        monkeypatch.setattr(worker_mod, "extract_structured_data", always_raises)
        process_pending_jobs(db_path=tmp_db)
        monkeypatch.undo()

        # A second sweep, extraction now working again, must not silently
        # retry the failed job — retries are manual-only (ADR-014).
        processed_again = process_pending_jobs(db_path=tmp_db)
        assert processed_again == 0
        assert pipeline_jobs.get_job_by_intake(intake_row["id"], db_path=tmp_db)["state"] == "failed"


@pytest.mark.unit
class TestDedupingCrashRecovery:

    def test_a_job_stuck_in_deduping_is_reclaimed(self, tmp_db):
        intake_row, _ = _make_intake_and_job(tmp_db)
        # Simulate a worker killed after writing 'deduping' but before the
        # terminal duplicate/pending_agent transition.
        pipeline_jobs.update_job_state(
            intake_row["id"], "deduping",
            structured_data={"company": "Acme", "title": "Backend Dev"},
            extraction_method="labeled",
            db_path=tmp_db,
        )

        processed = process_pending_jobs(db_path=tmp_db)

        assert processed == 1
        assert pipeline_jobs.get_job_by_intake(intake_row["id"], db_path=tmp_db)["state"] == "pending_agent"


@pytest.mark.unit
class TestIntakeIdempotencyUnderConcurrency:

    def test_two_concurrent_submissions_of_identical_text_create_one_row(self, tmp_db):
        results: list[dict] = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            try:
                row = create_intake("racy identical paste", db_path=tmp_db)
                results.append(row)
            except sqlite3.OperationalError as exc:
                # A locked-database error surfacing as an unhandled
                # exception would itself be a defect worth flagging.
                results.append({"error": str(exc)})

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 2
        assert all("error" not in r for r in results), results
        assert results[0]["id"] == results[1]["id"], (
            f"expected both submissions to resolve to the same row, got {results}"
        )

        conn = get_conn(tmp_db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM ui_intake WHERE raw_text = ?",
                ("racy identical paste",),
            ).fetchone()["n"]
        finally:
            conn.close()
        assert count == 1, "the race created more than one intake row"


@pytest.mark.unit
class TestCliNotifiesJobFailureOnAnyDieOnAddIntakeId:
    """`notify_job_state()` is an out-of-process, best-effort HTTP call
    (applyr/ui_events.py) — it silently no-ops without a live `applyr ui`
    server, by design (ADR-013's non-blocking rule). These tests verify
    cli.py's wrapper *calls* it correctly on every path, not the HTTP
    transport itself (already covered by tests/test_ui_jobs.py's
    TestInternalJobStateEndpoint and tests/test_pipeline_stage_instrumentation.py)."""

    def test_missing_title_notifies_failed(self, tmp_db, run_cli, capsys, monkeypatch):
        intake_row, _ = _make_intake_and_job(tmp_db)
        calls = []
        monkeypatch.setattr(
            "applyr.cli.notify_job_state",
            lambda intake_id, state, **kwargs: calls.append((intake_id, state, kwargs)),
        )

        with pytest.raises(SystemExit):
            run_cli(["add", '{"company": "Acme"}', "--intake-id", str(intake_row["id"])])
        capsys.readouterr()

        assert len(calls) == 1
        called_intake_id, called_state, kwargs = calls[0]
        assert called_intake_id == intake_row["id"]
        assert called_state == "failed"
        assert kwargs.get("error_message")

    def test_success_path_does_not_notify_failed(self, tmp_db, run_cli, capsys, monkeypatch):
        intake_row, _ = _make_intake_and_job(tmp_db)
        calls = []
        monkeypatch.setattr(
            "applyr.cli.notify_job_state",
            lambda intake_id, state, **kwargs: calls.append((intake_id, state, kwargs)),
        )

        run_cli([
            "add",
            '{"title": "Dev", "company": "Acme", "topics": {"tech_stack": {"score": 80}}}',
            "--intake-id", str(intake_row["id"]),
        ])
        capsys.readouterr()

        # cmd_add's own success-path notify_job_state("ready") lives in
        # applyr.commands.core, a separate import binding from the
        # applyr.cli one this test patches — so the wrapper's failure-only
        # notify (the thing under test here) must not have fired.
        assert calls == []

    def test_add_without_intake_id_never_calls_notify(self, tmp_db, run_cli, capsys, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "applyr.cli.notify_job_state",
            lambda intake_id, state, **kwargs: calls.append((intake_id, state, kwargs)),
        )

        with pytest.raises(SystemExit) as exc_info:
            run_cli(["add", '{"company": "Acme"}'])
        capsys.readouterr()

        assert exc_info.value.code == 1
        assert calls == []
