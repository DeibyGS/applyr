"""`applyr next` state machine and `--record` review history (ADR-015,
specs/cli-enforced-pipeline-gates)."""

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from applyr.pipeline_next import derive_next, read_history

CONFIG = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
CV_MTIME = 1_000_000.0


def _offer(**overrides):
    return {"id": 7, "status": "pending", "compatibility_pct": 75, **overrides}


def _rec(step, score, verdict, at):
    iso = datetime.fromtimestamp(at, timezone.utc).isoformat(timespec="seconds")
    return {"step": step, "score": score, "verdict": verdict, "at": iso}


BLIND = _rec("review_blind", 74, "CLOSE_MATCH", CV_MTIME - 100)
READY = _rec("cv_review", 85, "READY TO SEND", CV_MTIME + 10)
PASS = {"passed": True, "unsupported": []}


def _next(offer=None, topics=3, history=(), cv="cv-x.md", cv_mtime=CV_MTIME,
          pdf_mtime=None, verify=lambda: PASS):
    return derive_next(offer or _offer(), topics, list(history), cv, cv_mtime, pdf_mtime, verify, CONFIG)


def _must_not_verify():
    raise AssertionError("verify ran for a state that does not need it")


# --- derive_next: one test per state ------------------------------------------

@pytest.mark.parametrize("status", ["applied", "waiting", "in_process", "offer", "rejected", "discarded"])
def test_done_statuses(status):
    assert _next(_offer(status=status), verify=_must_not_verify)["state"] == "done"


def test_unscored_offer_needs_score():
    step = _next(_offer(compatibility_pct=0), topics=0, verify=_must_not_verify)
    assert step["state"] == "score"


def test_manual_score_without_topics_counts_as_scored():
    assert _next(_offer(compatibility_pct=70), topics=0, verify=_must_not_verify)["state"] == "decide"


def test_decide_needs_user_and_points_to_recorded_blind_review():
    step = _next(verify=_must_not_verify)
    assert step["state"] == "decide"
    assert step["needs_user_confirmation"] is True
    assert step["command"] == "applyr cv review-blind 7 --record <score>"
    assert step["warnings"] == []


def test_decide_on_low_match_suggests_archiving():
    step = _next(_offer(compatibility_pct=40), verify=_must_not_verify)
    assert "discarded" in step["warnings"][0]


def test_generate_after_blind_review_whatever_the_verdict():
    no_match = _rec("review_blind", 30, "NO_MATCH", CV_MTIME)
    step = _next(history=[no_match], cv=None, cv_mtime=None, verify=_must_not_verify)
    assert step["state"] == "generate"
    assert step["command"] == "applyr cv generate 7"


def test_cv_without_a_review_needs_review():
    step = _next(history=[BLIND], verify=_must_not_verify)
    assert step["state"] == "cv_review"
    assert step["command"] == "applyr cv review cv-x.md --record <score>"


def test_review_older_than_the_last_cv_edit_does_not_count():
    stale = _rec("cv_review", 90, "READY TO SEND", CV_MTIME - 1)
    assert _next(history=[BLIND, stale], verify=_must_not_verify)["state"] == "cv_review"


def test_fresh_non_ready_review_asks_to_edit_before_reviewing_again():
    minor = _rec("cv_review", 70, "NEEDS MINOR EDITS", CV_MTIME + 5)
    step = _next(history=[BLIND, minor], verify=_must_not_verify)
    assert step["state"] == "cv_review"
    assert "Edit the file" in step["reason"]


def test_review_limit_moves_on_to_verify_with_a_warning():
    reviews = [_rec("cv_review", 50, "NEEDS MAJOR REVISION", CV_MTIME + i) for i in range(3)]
    step = _next(history=[BLIND, *reviews], pdf_mtime=None)
    assert step["state"] == "pdf"
    assert "limit" in step["warnings"][0]


def test_failing_verify_lists_the_claims():
    failing = {"passed": False, "unsupported": [{"category": "technology", "claim": "Kubernetes"}]}
    step = _next(history=[BLIND, READY], verify=lambda: failing)
    assert step["state"] == "verify"
    assert step["failing"] == ["[technology] Kubernetes"]


def test_unverifiable_cv_stays_in_verify():
    step = _next(history=[BLIND, READY], verify=lambda: {"offer_id": 7, "unverifiable": "cv_master_missing"})
    assert step["state"] == "verify"
    assert step["failing"] == ["cv_master_missing"]


def test_verified_cv_without_pdf_needs_pdf():
    step = _next(history=[BLIND, READY])
    assert step["state"] == "pdf"
    assert step["command"] == "applyr cv pdf cv-x.md"


def test_pdf_older_than_the_cv_is_treated_as_missing():
    assert _next(history=[BLIND, READY], pdf_mtime=CV_MTIME - 1)["state"] == "pdf"


def test_fresh_pdf_leads_to_apply():
    step = _next(history=[BLIND, READY], pdf_mtime=CV_MTIME + 20)
    assert step["state"] == "apply"
    assert step["command"] == "applyr update 7 applied --canal <channel>"
    assert step["needs_user_confirmation"] is True


# --- history ----------------------------------------------------------------

def test_null_history_is_empty():
    assert read_history(None, 1) == []


@pytest.mark.parametrize("raw", ["{not json", '{"step": "cv_review"}', "[1]", '[{"step": "cv_review"}]'])
def test_corrupt_history_is_a_structured_error(raw, capsys):
    from applyr.errors import set_json_mode
    set_json_mode(True)
    try:
        with pytest.raises(SystemExit):
            read_history(raw, 1)
    finally:
        set_json_mode(False)
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "history_corrupt"


# --- --record and `applyr next` end to end ----------------------------------

@pytest.fixture
def offer_db(tmp_db, tmp_applyr):
    conn = sqlite3.connect(tmp_db)
    conn.execute("INSERT INTO offers (title, company, compatibility_pct) VALUES ('Dev', 'Acme', 75)")
    conn.commit()
    conn.close()
    return tmp_db


def _history(db):
    conn = sqlite3.connect(db)
    try:
        raw, iteration = conn.execute(
            "SELECT cv_iteration_history, cv_iteration FROM offers WHERE id = 1").fetchone()
    finally:
        conn.close()
    return (json.loads(raw) if raw else []), iteration


def _json_error(capsys, fn):
    from applyr.errors import set_json_mode
    set_json_mode(True)
    try:
        with pytest.raises(SystemExit):
            fn()
    finally:
        set_json_mode(False)
    return json.loads(capsys.readouterr().err.strip().splitlines()[-1])["error"]


def test_record_blind_review_uses_configured_thresholds(offer_db):
    from applyr.cv import cmd_cv_review_blind
    cmd_cv_review_blind(1, record="74")
    history, iteration = _history(offer_db)
    assert [(e["step"], e["score"], e["verdict"]) for e in history] == [("review_blind", 74, "CLOSE_MATCH")]
    assert iteration == 0  # only cv_review records count as iterations


def test_record_cv_review_appends_and_counts(offer_db, tmp_path):
    from applyr.cv import cmd_cv_review
    cv = tmp_path / "cv-acme.md"
    cv.write_text("---\noffer_id: 1\n---\n\n# Ana\n", encoding="utf-8")
    cmd_cv_review(str(cv), record="55")
    cmd_cv_review(str(cv), record="81")
    history, iteration = _history(offer_db)
    assert [e["verdict"] for e in history] == ["NEEDS MAJOR REVISION", "READY TO SEND"]
    assert iteration == 2


@pytest.mark.parametrize("raw", ["abc", "101", "-1"])
def test_invalid_record_value_records_nothing(offer_db, capsys, raw):
    from applyr.cv import cmd_cv_review_blind
    err = _json_error(capsys, lambda: cmd_cv_review_blind(1, record=raw))
    assert err["code"] == "invalid_value"
    assert _history(offer_db) == ([], 0)


def test_record_on_cv_without_offer_id_records_nothing(offer_db, tmp_path, capsys):
    from applyr.cv import cmd_cv_review
    cv = tmp_path / "hand.md"
    cv.write_text("# Ana\n", encoding="utf-8")
    assert _json_error(capsys, lambda: cmd_cv_review(str(cv), record="80"))["code"] == "no_offer_id"
    assert _history(offer_db) == ([], 0)


def test_record_refuses_to_overwrite_a_corrupt_history(offer_db, capsys):
    from applyr.cv import cmd_cv_review_blind
    conn = sqlite3.connect(offer_db)
    conn.execute("UPDATE offers SET cv_iteration_history = 'garbage' WHERE id = 1")
    conn.commit()
    conn.close()
    assert _json_error(capsys, lambda: cmd_cv_review_blind(1, record="80"))["code"] == "history_corrupt"
    conn = sqlite3.connect(offer_db)
    assert conn.execute("SELECT cv_iteration_history FROM offers").fetchone()[0] == "garbage"
    conn.close()


def test_next_json_is_read_only(offer_db, capsys):
    from applyr.commands.workflow import cmd_next
    before = open(offer_db, "rb").read()
    cmd_next(1, as_json=True)
    step = json.loads(capsys.readouterr().out)
    assert step["offer_id"] == 1
    assert step["state"] == "decide"
    assert open(offer_db, "rb").read() == before


def test_next_follows_a_recorded_blind_review(offer_db, capsys):
    from applyr.commands.workflow import cmd_next
    from applyr.cv import cmd_cv_review_blind
    cmd_cv_review_blind(1, record="85")
    capsys.readouterr()
    cmd_next(1, as_json=True)
    assert json.loads(capsys.readouterr().out)["state"] == "generate"


def test_next_on_unknown_offer(offer_db, capsys):
    from applyr.commands.workflow import cmd_next
    assert _json_error(capsys, lambda: cmd_next(99))["code"] == "not_found"


def test_next_on_finished_offer_ignores_a_corrupt_history(offer_db, capsys):
    from applyr.commands.workflow import cmd_next
    conn = sqlite3.connect(offer_db)
    conn.execute("UPDATE offers SET status = 'applied', cv_iteration_history = 'garbage' WHERE id = 1")
    conn.commit()
    conn.close()
    cmd_next(1, as_json=True)
    assert json.loads(capsys.readouterr().out)["state"] == "done"


def test_concurrent_records_lose_nothing(offer_db):
    """Adversarial BUG-002: parallel --record calls must all land (AC-10)."""
    import os
    import subprocess
    import sys
    env = {**os.environ, "APPLYR_HOME": str(offer_db.rsplit("/", 1)[0])}
    procs = [subprocess.Popen([sys.executable, "-m", "applyr.cli", "cv", "review-blind", "1",
                               "--record", str(50 + i)], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             for i in range(8)]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    history, _ = _history(offer_db)
    assert sorted(e["score"] for e in history) == list(range(50, 58))
