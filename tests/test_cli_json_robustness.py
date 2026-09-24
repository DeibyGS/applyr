"""Regression tests for agent-facing robustness: malformed input must fail
before any write, and `--json` stdout must always be parseable JSON."""

import json
import sqlite3

import pytest


def _run(run_cli, capsys, args: list[str]):
    """Run cli.main() and return (stdout, stderr, exit_code)."""
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


def _offer_count(tmp_db) -> int:
    conn = sqlite3.connect(tmp_db)
    try:
        return conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
    finally:
        conn.close()


def _row(tmp_db, offer_id: int) -> dict:
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    try:
        return dict(conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone())
    finally:
        conn.close()


def _add(run_cli, capsys, **extra) -> int:
    payload = {"title": "Backend Dev", "company": "Acme"} | extra
    out, err, code = _run(run_cli, capsys, ["add", json.dumps(payload), "--json"])
    assert code == 0, err
    return json.loads(out)["id"]


class TestAddRejectsMalformedTopicsBeforeInsert:
    """A bad topic used to crash *after* the commit: the retry then hit `duplicate`."""

    @pytest.mark.parametrize("topics", [
        {"tech_stack": {"score": "80", "detail": "x"}},
        {"tech_stack": {"score": None, "detail": "x"}},
        {"tech_stack": {"detail": "no score"}},
        {"tech_stack": {"score": True, "detail": "x"}},
        {"tech_stack": 80},
        ["tech_stack"],
    ])
    def test_malformed_topics_fail_without_writing(self, run_cli, capsys, tmp_db, topics):
        payload = json.dumps({"title": "Backend Dev", "company": "Acme", "topics": topics})
        out, err, code = _run(run_cli, capsys, ["add", payload, "--json"])
        assert code != 0
        assert json.loads(err)["error"]["code"] == "invalid_value"
        assert _offer_count(tmp_db) == 0

    def test_retry_after_fix_is_not_a_duplicate(self, run_cli, capsys, tmp_db):
        bad = json.dumps({"title": "Backend Dev", "company": "Acme",
                          "topics": {"tech_stack": {"score": "80"}}})
        _run(run_cli, capsys, ["add", bad, "--json"])
        offer_id = _add(run_cli, capsys, topics={"tech_stack": {"score": 80, "detail": "x"}})
        assert offer_id == 1

    def test_invalid_confidence_fails_without_writing(self, run_cli, capsys, tmp_db):
        payload = json.dumps({"title": "Backend Dev", "company": "Acme",
                              "topics": {"tech_stack": {"score": 80, "confidence": "0.9"}}})
        out, err, code = _run(run_cli, capsys, ["add", payload, "--json"])
        assert code != 0
        assert _offer_count(tmp_db) == 0

    def test_out_of_range_score_is_still_only_a_warning(self, run_cli, capsys, tmp_db):
        offer_id = _add(run_cli, capsys, topics={"tech_stack": {"score": 150, "detail": "x"},
                                                 "english": {"score": 70, "detail": "y"}})
        assert _row(tmp_db, offer_id)["compatibility_pct"] == 70


@pytest.mark.parametrize("legacy_score", ["high", None])
def test_show_survives_legacy_non_numeric_score(run_cli, capsys, tmp_db, legacy_score):
    """Rows stored before validation existed can hold a string or NULL score."""
    offer_id = _add(run_cli, capsys, topics={"tech_stack": {"score": 80, "detail": "x"}})
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE offer_topics SET score = ? WHERE offer_id = ?", (legacy_score, offer_id))
    conn.commit()
    conn.close()
    out, err, code = _run(run_cli, capsys, ["show", str(offer_id)])
    assert code == 0, err


def test_add_date_warning_goes_to_stderr(run_cli, capsys, tmp_db):
    payload = json.dumps({"title": "Backend Dev", "company": "Acme", "date_applied": "yesterday"})
    out, err, code = _run(run_cli, capsys, ["add", payload, "--json"])
    assert code == 0
    json.loads(out)  # stdout must stay pure JSON (warnings are muted in JSON mode)
    payload = json.dumps({"title": "Frontend Dev", "company": "Acme", "date_applied": "yesterday"})
    out, err, code = _run(run_cli, capsys, ["add", payload])
    assert "date_applied" in err
    assert "date_applied" not in out


def test_broken_config_warning_does_not_pollute_json(run_cli, capsys, tmp_db, tmp_applyr):
    (tmp_applyr / "applyr.toml").write_text("this is [not toml")
    out, err, code = _run(run_cli, capsys, ["list", "--json"])
    assert code == 0
    json.loads(out)
    assert "could not parse" in err


def test_stats_json_on_empty_database(run_cli, capsys, tmp_db):
    out, err, code = _run(run_cli, capsys, ["stats", "--json"])
    assert code == 0
    data = json.loads(out)
    assert data["total"] == 0
    assert data["funnel"]["applied"] == 0


class TestSetupAgentCursorRulesDirectory:
    def test_writes_mdc_inside_rules_directory(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """Modern Cursor: `.cursor/rules/` is a directory of .mdc files."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cursor" / "rules").mkdir(parents=True)
        out, err, code = _run(run_cli, capsys, ["setup-agent"])
        assert code == 0, err
        mdc = (tmp_path / ".cursor" / "rules" / "applyr.mdc").read_text()
        assert mdc.startswith("---\n")
        assert "alwaysApply: true" in mdc
        assert "applyr" in mdc.lower()

    def test_second_run_is_skipped_as_up_to_date(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cursor" / "rules").mkdir(parents=True)
        _run(run_cli, capsys, ["setup-agent"])
        out, err, code = _run(run_cli, capsys, ["setup-agent"])
        assert code == 0
        assert "up-to-date" in out


def test_setup_agent_points_at_the_real_cv_master_path(run_cli, capsys, tmp_db, tmp_path, monkeypatch):
    from applyr.cv import get_cv_master_path
    monkeypatch.chdir(tmp_path)
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude"])
    assert code == 0
    assert str(get_cv_master_path()) in out


class TestUpdateKeepsReplyDataConsistent:
    def test_correcting_rejected_back_to_applied_clears_reply(self, run_cli, capsys, tmp_db):
        offer_id = _add(run_cli, capsys)
        _run(run_cli, capsys, ["update", str(offer_id), "rejected"])
        assert _row(tmp_db, offer_id)["response_status"] == "rejected"
        _run(run_cli, capsys, ["update", str(offer_id), "applied"])
        row = _row(tmp_db, offer_id)
        assert row["response_status"] == "no_response"
        assert row["date_responded"] is None

    def test_discarded_keeps_reply_history(self, run_cli, capsys, tmp_db):
        offer_id = _add(run_cli, capsys)
        _run(run_cli, capsys, ["update", str(offer_id), "in_process"])
        _run(run_cli, capsys, ["update", str(offer_id), "discarded"])
        assert _row(tmp_db, offer_id)["response_status"] == "in_process"

    def test_repeating_applied_does_not_push_follow_up(self, run_cli, capsys, tmp_db):
        offer_id = _add(run_cli, capsys)
        _run(run_cli, capsys, ["update", str(offer_id), "applied"])
        conn = sqlite3.connect(tmp_db)
        conn.execute("UPDATE offers SET follow_up_date = '2000-01-01' WHERE id = ?", (offer_id,))
        conn.commit()
        conn.close()
        _run(run_cli, capsys, ["update", str(offer_id), "applied"])
        assert _row(tmp_db, offer_id)["follow_up_date"] == "2000-01-01"

    def test_new_follow_up_rearms_done_flag(self, run_cli, capsys, tmp_db):
        offer_id = _add(run_cli, capsys)
        conn = sqlite3.connect(tmp_db)
        conn.execute("UPDATE offers SET follow_up_done = 1 WHERE id = ?", (offer_id,))
        conn.commit()
        conn.close()
        _run(run_cli, capsys, ["update", str(offer_id), "applied"])
        assert _row(tmp_db, offer_id)["follow_up_done"] == 0
