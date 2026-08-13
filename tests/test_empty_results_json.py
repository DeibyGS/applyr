"""--json must stay parseable even when there is nothing to report.

Found while auditing applyr end to end: every list-shaped command printed a
human sentence ("No offers found.", "No skill gaps recorded yet.", ...) on
an empty result set regardless of --json, breaking the one contract
AGENT_INSTRUCTIONS.md promises agent callers ("--json en todos los
comandos"). cmd_gaps_list already did this right (`{"total": 0, "gaps": []}`
even when empty); the rest are brought in line with it here.
"""

import json

import pytest

from applyr.commands import (
    cmd_gaps,
    cmd_list,
    cmd_pipeline,
    cmd_plan,
    cmd_salary,
    cmd_search,
    cmd_trends,
)


@pytest.mark.unit
class TestEmptyResultsStayJson:

    def test_list(self, tmp_db, tmp_applyr, capsys):
        cmd_list(as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_search(self, tmp_db, tmp_applyr, capsys):
        cmd_search("nothing-matches-this", as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_search_company(self, tmp_db, tmp_applyr, capsys):
        cmd_search("", company="Nobody Inc", as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_pipeline(self, tmp_db, tmp_applyr, capsys):
        cmd_pipeline(as_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, dict)
        assert all(v == [] for v in payload.values())

    def test_gaps(self, tmp_db, tmp_applyr, capsys):
        cmd_gaps(as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_trends(self, tmp_db, tmp_applyr, capsys):
        cmd_trends(as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_plan(self, tmp_db, tmp_applyr, capsys):
        cmd_plan(as_json=True)
        assert json.loads(capsys.readouterr().out) == []

    def test_salary(self, tmp_db, tmp_applyr, capsys):
        cmd_salary(as_json=True)
        assert json.loads(capsys.readouterr().out) == {"by_seniority": [], "by_category": []}
