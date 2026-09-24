"""One recommendation definition exposed everywhere, and config values that
cannot silently break scoring (2026-09 audit, Phase 2)."""

import json

import pytest


def _run(run_cli, capsys, args: list[str]):
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


def _add(run_cli, capsys, title: str, score: int) -> int:
    payload = {"title": title, "company": "Acme", "topics": {"tech_stack": {"score": score, "detail": "x"}}}
    out, err, code = _run(run_cli, capsys, ["add", json.dumps(payload), "--json"])
    assert code == 0, err
    return json.loads(out)["id"]


def _write_config(tmp_applyr, body: str) -> None:
    import applyr.config as cfg
    cfg._WARNED.clear()
    (tmp_applyr / "applyr.toml").write_text(body)


@pytest.fixture
def offers(run_cli, capsys, tmp_db):
    return {
        "apply": _add(run_cli, capsys, "Strong", 90),
        "maybe": _add(run_cli, capsys, "Middle", 70),
        "low_match": _add(run_cli, capsys, "Weak", 30),
    }


class TestRecommendationInEveryJsonOutput:
    def test_show(self, run_cli, capsys, offers):
        for expected, offer_id in offers.items():
            out, _, _ = _run(run_cli, capsys, ["show", str(offer_id), "--json"])
            assert json.loads(out)["recommendation"] == expected

    @pytest.mark.parametrize("args", [["list"], ["search", "Acme"]])
    def test_list_and_search(self, run_cli, capsys, offers, args):
        out, _, _ = _run(run_cli, capsys, args + ["--json"])
        by_title = {r["title"]: r["recommendation"] for r in json.loads(out)}
        assert by_title == {"Strong": "apply", "Middle": "maybe", "Weak": "low_match"}

    def test_pipeline(self, run_cli, capsys, offers):
        out, _, _ = _run(run_cli, capsys, ["pipeline", "--json"])
        pending = json.loads(out)["pending"]
        assert {i["title"]: i["recommendation"] for i in pending}["Strong"] == "apply"

    def test_rescore(self, run_cli, capsys, offers):
        out, _, _ = _run(run_cli, capsys, ["rescore", str(offers["maybe"]), "--json"])
        assert json.loads(out)["recommendation"] == "maybe"

    def test_follows_configured_thresholds(self, run_cli, capsys, offers, tmp_applyr):
        _write_config(tmp_applyr, "[general]\nthreshold_apply = 65\nthreshold_maybe = 20\n")
        out, _, _ = _run(run_cli, capsys, ["show", str(offers["maybe"]), "--json"])
        assert json.loads(out)["recommendation"] == "apply"


class TestConfigSanitizing:
    def test_maybe_above_apply_is_clamped(self, tmp_applyr, capsys):
        from applyr.config import load_config
        _write_config(tmp_applyr, "[general]\nthreshold_apply = 70\nthreshold_maybe = 90\n")
        general = load_config()["general"]
        assert general["threshold_maybe"] == 70
        assert "threshold_maybe" in capsys.readouterr().err

    def test_out_of_range_threshold_falls_back(self, tmp_applyr):
        from applyr.config import load_config
        _write_config(tmp_applyr, '[general]\nthreshold_apply = 150\nthreshold_maybe = "high"\n')
        general = load_config()["general"]
        assert (general["threshold_apply"], general["threshold_maybe"]) == (80, 60)

    def test_bad_weights_cannot_break_scoring(self, tmp_applyr):
        from applyr.scoring import calculate_score
        _write_config(tmp_applyr, '[weights]\ntech_stack = -50\nexperience = "lots"\n')
        score = calculate_score({"tech_stack": {"score": 100}, "experience": {"score": 100}})
        assert 0 <= score <= 100

    def test_warning_is_printed_once_per_process(self, tmp_applyr, capsys):
        from applyr.config import load_config
        _write_config(tmp_applyr, "[weights]\ntech_stack = -1\n")
        load_config()
        load_config()
        assert capsys.readouterr().err.count("tech_stack") == 1


class TestCustomTopics:
    CONFIG = "[weights]\ntech_stack = 50\nleadership = 50\n"

    def test_add_does_not_warn_about_a_weighted_custom_topic(self, run_cli, capsys, tmp_db, tmp_applyr):
        _write_config(tmp_applyr, self.CONFIG)
        payload = {"title": "Lead", "company": "Acme",
                   "topics": {"leadership": {"score": 70, "detail": "x"}}}
        _, err, code = _run(run_cli, capsys, ["add", json.dumps(payload)])
        assert code == 0
        assert "not in config" not in err

    def test_gaps_save_accepts_a_weighted_custom_topic(self, run_cli, capsys, tmp_db, tmp_applyr):
        _write_config(tmp_applyr, self.CONFIG)
        offer_id = _add(run_cli, capsys, "Lead", 70)
        gaps = {"gaps": [{"topic": "leadership", "gap_detail": "No team lead yet", "severity": "medium"}]}
        _, err, code = _run(run_cli, capsys, ["gaps", "save", str(offer_id), json.dumps(gaps)])
        assert code == 0, err


def test_gaps_save_rejects_a_bare_list_cleanly(run_cli, capsys, tmp_db):
    offer_id = _add(run_cli, capsys, "Dev", 70)
    _, err, code = _run(run_cli, capsys, ["gaps", "save", str(offer_id), '[{"topic": "tech_stack"}]', "--json"])
    assert code != 0
    assert json.loads(err)["error"]["code"] == "invalid_value"


@pytest.mark.parametrize("body", ['[general]\nthreshold_apply = "85"\n', '[general]\nthreshold = "70"\n'])
def test_quoted_threshold_does_not_crash_load_config(tmp_applyr, body):
    from applyr.config import load_config
    _write_config(tmp_applyr, body)
    general = load_config()["general"]
    assert general["threshold_apply"] == 80


def test_doctor_still_reports_values_it_had_to_replace(run_cli, capsys, tmp_db, tmp_applyr):
    _write_config(tmp_applyr, "[weights]\ntech_stack = -5\n")
    out, _, code = _run(run_cli, capsys, ["doctor", "--json"])
    report = json.loads(out)
    assert code == 1
    assert any(c["name"] == "Config values" and c["status"] != "ok" for c in report["checks"])


def test_add_prints_the_cli_state_names(run_cli, capsys, tmp_db):
    payload = {"title": "Weak", "company": "Acme", "topics": {"tech_stack": {"score": 10, "detail": "x"}}}
    out, _, _ = _run(run_cli, capsys, ["add", json.dumps(payload)])
    assert "LOW MATCH" in out
    assert "SKIP" not in out
