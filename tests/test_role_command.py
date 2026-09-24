"""`applyr role` serves the packaged role files — the paths the instructions used
to cite (`applyr/templates/agents/*.md`) do not exist for a pip-installed user."""

import json
import re
from pathlib import Path

import pytest

import applyr

ROLES = ["architect", "fact-checker", "matcher", "recruiter", "writer"]


def _run(run_cli, capsys, args):
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


def test_lists_every_role(run_cli, capsys, tmp_db):
    out, _, code = _run(run_cli, capsys, ["role", "--json"])
    assert code == 0
    assert json.loads(out)["roles"] == ROLES


@pytest.mark.parametrize("role", ROLES)
def test_prints_each_role(run_cli, capsys, tmp_db, role):
    out, _, code = _run(run_cli, capsys, ["role", role])
    assert code == 0
    assert out.startswith("# ")


def test_unknown_role_fails_with_the_valid_names(run_cli, capsys, tmp_db):
    _, err, code = _run(run_cli, capsys, ["role", "ceo", "--json"])
    assert code != 0
    assert json.loads(err)["error"]["details"]["valid"] == ROLES


@pytest.mark.parametrize("name", ["../AGENT_INSTRUCTIONS", "Matcher", "fact_checker"])
def test_only_listed_role_names_resolve(name):
    from applyr.agent_instructions import role_instructions
    assert role_instructions(name) is None


def test_instructions_only_reference_roles_that_exist():
    text = (Path(applyr.__file__).parent / "templates" / "AGENT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "templates/agents/" not in text
    cited = set(re.findall(r"applyr role ([a-z-]+)", text))
    assert cited and cited <= set(ROLES)


def test_instructions_use_the_cli_recommendation_states():
    text = (Path(applyr.__file__).parent / "templates" / "AGENT_INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "APPLY | SKIP" not in text
    assert "RECOMMENDATION: APPLY | MAYBE | LOW MATCH" in text
