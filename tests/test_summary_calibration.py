"""`summary` shows the all-time score calibration, identical to `stats` (audit Phase 5.3)."""

import json


def _run(run_cli, capsys, args: list[str]):
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


def _add(run_cli, capsys, title: str, score: int, status: str) -> None:
    payload = {"title": title, "company": f"Company {title}", "status": status,
               "topics": {"tech_stack": {"score": score, "detail": "x"}}}
    _, err, code = _run(run_cli, capsys, ["add", json.dumps(payload), "--json"])
    assert code == 0, err


def test_summary_json_matches_stats_calibration(run_cli, capsys, tmp_db):
    for i in range(6):
        _add(run_cli, capsys, f"Strong {i}", 90, "rejected" if i < 2 else "applied")
    _add(run_cli, capsys, "Weak", 30, "applied")

    summary, _, code = _run(run_cli, capsys, ["summary", "--json"])
    stats, _, _ = _run(run_cli, capsys, ["stats", "--json"])
    summary, stats = json.loads(summary), json.loads(stats)

    assert code == 0
    assert summary["score_calibration"] == stats["score_calibration"]
    assert summary["score_calibration"]["apply"]["total"] == 6
    assert summary["score_calibration"]["apply"]["responded"] == 2
    assert summary["calibration_min_sample"] == 5
    assert summary["score_calibration_excluded_unknown_weights"] == 0


def test_summary_text_hides_rates_below_min_sample(run_cli, capsys, tmp_db):
    for i in range(6):
        _add(run_cli, capsys, f"Strong {i}", 90, "applied")
    _add(run_cli, capsys, "Weak", 30, "applied")

    out, _, code = _run(run_cli, capsys, ["summary"])
    assert code == 0
    assert "Score Calibration — all time" in out
    assert "6 applied" in out and "responded" in out
    assert "1 applied — not enough data yet (need 5+)" in out


def test_summary_without_outcomes_prints_no_calibration(run_cli, capsys, tmp_db):
    _add(run_cli, capsys, "Pending", 90, "pending")
    out, _, code = _run(run_cli, capsys, ["summary"])
    assert code == 0
    assert "Score Calibration" not in out
