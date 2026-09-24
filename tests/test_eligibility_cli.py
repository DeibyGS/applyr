"""Eligibility / knockout check through the CLI: add, show, list, search (ADR-017)."""

import json
import sqlite3

import pytest

PROFILE = """\
## LANGUAGES
- English: B1

## ELIGIBILITY
- Relevant experience (years): 2
- Cities: Madrid
- Relocation: no
- Driving license: yes
"""

# 95% on its own — only eligibility can turn it into a LOW MATCH.
STRONG_TOPICS = {"tech_stack": {"score": 95, "detail": "x"}}
BLOCKING = {"languages": [{"language": "english", "level": "C2"}]}


def _run(run_cli, capsys, args: list[str]):
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


@pytest.fixture
def profile(tmp_applyr, monkeypatch):
    path = tmp_applyr / "cv-master-eligibility.md"
    path.write_text(PROFILE, encoding="utf-8")
    import applyr.commands._helpers as helpers
    monkeypatch.setattr(helpers, "get_cv_master_path", lambda: path)
    return path


def _add(run_cli, capsys, title: str, eligibility: dict | None = None, **extra) -> dict:
    payload = {"title": title, "company": "Acme", "work_mode": "onsite", "topics": STRONG_TOPICS, **extra}
    if eligibility is not None:
        payload["eligibility"] = eligibility
    out, err, code = _run(run_cli, capsys, ["add", json.dumps(payload), "--json"])
    assert code == 0, err
    return json.loads(out)


# --- AC-01 / AC-13 / AC-10 / AC-11 -------------------------------------------

def test_blocked_offer_is_low_match_with_score_untouched(run_cli, capsys, tmp_db, profile):
    data = _add(run_cli, capsys, "Blocked", BLOCKING)
    assert data["compatibility_pct"] == 95
    assert data["recommendation"] == "low_match"
    assert data["eligibility"]["blocked"] is True
    assert "language:english" in data["eligibility_block"]


def test_show_json_exposes_requirements_result_and_reason(run_cli, capsys, tmp_db, profile):
    offer_id = _add(run_cli, capsys, "Blocked", BLOCKING)["id"]
    out, _, code = _run(run_cli, capsys, ["show", str(offer_id), "--json"])
    data = json.loads(out)
    assert code == 0
    assert data["recommendation"] == "low_match" and data["compatibility_pct"] == 95
    assert data["eligibility_requirements"] == {"languages": [{"language": "english", "level": "C2"}]}
    assert data["eligibility"]["items"][0]["status"] == "block"
    assert "eligibility_result" not in data


@pytest.mark.parametrize("command", [["list"], ["search", "Blocked"]])
def test_listings_report_blocked_offer_as_low_match(run_cli, capsys, tmp_db, profile, command):
    _add(run_cli, capsys, "Blocked", BLOCKING)
    out, _, code = _run(run_cli, capsys, [*command, "--json"])
    row = json.loads(out)[0]
    assert code == 0
    assert row["recommendation"] == "low_match"
    assert row["eligibility_block"].startswith("language:english")


def test_text_output_shows_block_reason(run_cli, capsys, tmp_db, profile):
    payload = {"title": "Blocked", "company": "Acme", "topics": STRONG_TOPICS, "eligibility": BLOCKING}
    out, _, code = _run(run_cli, capsys, ["add", json.dumps(payload)])
    assert code == 0
    assert "LOW MATCH" in out and "BLOCKED BY: language:english" in out
    out, _, _ = _run(run_cli, capsys, ["show", "1"])
    assert "LOW MATCH" in out and "BLOCKED BY" in out


# --- AC-02 / AC-14 / AC-E3 ---------------------------------------------------

def test_no_block_behaves_as_before(run_cli, capsys, tmp_db, profile):
    data = _add(run_cli, capsys, "Plain")
    assert data["recommendation"] == "apply"
    assert data["eligibility"] is None and data["eligibility_block"] is None


def test_warn_does_not_change_recommendation(run_cli, capsys, tmp_db, profile):
    data = _add(run_cli, capsys, "Near miss", {"min_years": 3})
    assert data["eligibility"]["items"][0]["status"] == "warn"
    assert data["recommendation"] == "apply" and data["eligibility_block"] is None


def test_offer_without_eligibility_columns_set_reads_as_before(run_cli, capsys, tmp_db, profile):
    offer_id = _add(run_cli, capsys, "Legacy")["id"]
    out, _, _ = _run(run_cli, capsys, ["show", str(offer_id), "--json"])
    data = json.loads(out)
    assert data["eligibility"] is None and data["eligibility_requirements"] is None
    assert data["recommendation"] == "apply"


# --- AC-E1 / AC-E2 -----------------------------------------------------------

@pytest.mark.parametrize("block, field", [
    ({"salary": 1}, "salary"),
    ({"min_years": -2}, "min_years"),
    ({"languages": [{"language": "english", "level": "fluent"}]}, "languages"),
    ({"driving_license": "yes"}, "driving_license"),
])
def test_invalid_block_fails_and_stores_nothing(run_cli, capsys, tmp_db, profile, block, field):
    payload = {"title": "Bad", "company": "Acme", "eligibility": block}
    _, err, code = _run(run_cli, capsys, ["add", json.dumps(payload), "--json"])
    assert code != 0
    assert json.loads(err)["error"]["code"] == "invalid_eligibility"
    assert json.loads(err)["error"]["details"]["field"] == field
    assert sqlite3.connect(tmp_db).execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 0


def test_missing_cv_master_stores_offer_with_all_unknown(run_cli, capsys, tmp_db, tmp_applyr, monkeypatch):
    import applyr.commands._helpers as helpers
    monkeypatch.setattr(helpers, "get_cv_master_path", lambda: tmp_applyr / "does-not-exist.md")
    data = _add(run_cli, capsys, "No profile", {"min_years": 9, "city": "Oslo", "driving_license": True})
    assert {i["status"] for i in data["eligibility"]["items"]} == {"unknown"}
    assert data["recommendation"] == "apply"
