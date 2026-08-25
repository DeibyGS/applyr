"""Integration-level proof that ADR-013's 5 instrumentation call sites never
affect the calling CLI command, even when the UI backend is stuck (not just
absent). notify_stage() itself is already exhaustively unit-tested in
tests/test_ui_events.py — these tests instead exercise the real command
functions (cmd_add, cmd_update, cmd_cv_generate, cmd_cv_review) against a
hanging local server, proving the wiring in commands/core.py and cv.py
doesn't introduce a blocking path of its own.

cmd_cv_pdf is deliberately not called here: no test in this suite invokes
real Chrome (see tests/test_cv.py, which only imports cv.py's pure
helpers). Its instrumentation call site uses the exact same
`_mark_pipeline_stage` helper cmd_cv_review uses, so testing that helper
directly against the hanging server gives equivalent coverage without a
Chrome dependency.
"""

import json
import time

import pytest

from applyr.commands.core import cmd_add, cmd_update
from applyr.cv import _mark_pipeline_stage, cmd_cv_generate, cmd_cv_review
from applyr.db import get_conn
from applyr.ui_events import TIMEOUT_SECONDS

# Generous multiplier over TIMEOUT_SECONDS to absorb CI/scheduler jitter
# without the assertion becoming meaningless — matches test_ui_events.py.
BOUND = TIMEOUT_SECONDS * 10


@pytest.fixture
def redirect_to_hanging_server(hanging_server, monkeypatch):
    """Points every notify_stage() call at the hanging server, for every
    fixture and test body in a test — a real, unrelated `applyr ui` the
    developer happens to have running locally on the default port must
    never receive test traffic."""
    import applyr.ui_events as ui_events_mod

    monkeypatch.setattr(ui_events_mod, "DEFAULT_UI_PORT", hanging_server)
    return hanging_server


@pytest.fixture
def offer_id(tmp_db, tmp_applyr, redirect_to_hanging_server):
    """Register one scored offer and a usable cv-master. Depends on
    redirect_to_hanging_server directly (not just parameter order) so this
    fixture's own cmd_add() call never reaches a real port either."""
    (tmp_applyr / "cv-master.md").write_text(
        "# CV Master\n\n## Summary\n" + "Fullstack developer. " * 20
    )
    cmd_add(json.dumps({
        "title": "Full Stack (JS)",
        "company": "Fusuma",
        "topics": {"experience": {"score": 20, "detail": "no professional experience"}},
    }))
    return 1


def _pipeline_stage(tmp_db, target_offer_id: int) -> str | None:
    conn = get_conn(tmp_db)
    try:
        row = conn.execute(
            "SELECT pipeline_stage FROM offers WHERE id = ?", (target_offer_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["pipeline_stage"] if row else None


class TestAddIsNeverBlockedByAStuckUiBackend:
    def test_completes_within_the_timeout_bound(self, tmp_db, tmp_applyr, redirect_to_hanging_server):
        start = time.monotonic()
        cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme"}))
        elapsed = time.monotonic() - start
        assert elapsed < BOUND

    def test_still_writes_pipeline_stage_and_prints_normally(
        self, tmp_db, tmp_applyr, redirect_to_hanging_server, capsys
    ):
        cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme"}))
        assert _pipeline_stage(tmp_db, 1) == "matching"
        assert "Offer added successfully." in capsys.readouterr().out


class TestUpdateIsNeverBlockedByAStuckUiBackend:
    def test_completes_within_the_timeout_bound(self, offer_id, tmp_db, redirect_to_hanging_server):
        start = time.monotonic()
        cmd_update(offer_id, "applied")
        elapsed = time.monotonic() - start
        assert elapsed < BOUND

    def test_still_writes_pipeline_stage_and_prints_normally(
        self, offer_id, tmp_db, redirect_to_hanging_server, capsys
    ):
        cmd_update(offer_id, "applied")
        assert _pipeline_stage(tmp_db, offer_id) == "application"
        assert f"Offer #{offer_id} updated." in capsys.readouterr().out


class TestCvGenerateIsNeverBlockedByAStuckUiBackend:
    def test_completes_within_the_timeout_bound(self, offer_id, tmp_db, redirect_to_hanging_server):
        start = time.monotonic()
        cmd_cv_generate(offer_id)
        elapsed = time.monotonic() - start
        assert elapsed < BOUND

    def test_still_writes_pipeline_stage_and_the_cv_file(
        self, offer_id, tmp_db, tmp_applyr, redirect_to_hanging_server
    ):
        cmd_cv_generate(offer_id)
        assert _pipeline_stage(tmp_db, offer_id) == "cv"
        assert list((tmp_applyr / "cv").glob("*.md"))


class TestCvReviewIsNeverBlockedByAStuckUiBackend:
    def test_completes_within_the_timeout_bound(self, offer_id, tmp_db, tmp_applyr, redirect_to_hanging_server):
        cmd_cv_generate(offer_id)
        cv_file = next((tmp_applyr / "cv").glob("*.md"))

        start = time.monotonic()
        cmd_cv_review(str(cv_file))
        elapsed = time.monotonic() - start
        assert elapsed < BOUND

    def test_still_writes_pipeline_stage_and_prints_the_prompt(
        self, offer_id, tmp_db, tmp_applyr, redirect_to_hanging_server, capsys
    ):
        cmd_cv_generate(offer_id)
        cv_file = next((tmp_applyr / "cv").glob("*.md"))
        capsys.readouterr()  # discard cv_generate's own output

        cmd_cv_review(str(cv_file))

        assert _pipeline_stage(tmp_db, offer_id) == "ats"
        assert "senior technical recruiter" in capsys.readouterr().out


class TestCvPdfsInstrumentationIsNeverBlockedByAStuckUiBackend:
    """cmd_cv_pdf itself is not called (see module docstring) — this tests
    `_mark_pipeline_stage`, the exact helper its instrumentation call site
    uses, which is what actually talks to notify_stage()."""

    def test_completes_within_the_timeout_bound(self, offer_id, tmp_db, redirect_to_hanging_server):
        start = time.monotonic()
        _mark_pipeline_stage(offer_id, "application")
        elapsed = time.monotonic() - start
        assert elapsed < BOUND

    def test_still_writes_pipeline_stage(self, offer_id, tmp_db, redirect_to_hanging_server):
        _mark_pipeline_stage(offer_id, "application")
        assert _pipeline_stage(tmp_db, offer_id) == "application"
