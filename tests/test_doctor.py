"""Tests for `applyr doctor` — the health check must gate, observe and not lie.

`doctor` is the first command AGENT_INSTRUCTIONS.md tells an agent to run, so a
wrong verdict here propagates into every CV built afterwards.
"""

import json

import pytest


@pytest.fixture
def doctor_home(tmp_db, tmp_applyr, monkeypatch):
    """An initialized, healthy applyr home wired into every module that reads it.

    `workflow.py` binds APPLYR_DIR at import time, so patching `applyr.config`
    alone leaves the health check looking at the real home directory.
    """
    monkeypatch.setattr("applyr.commands.workflow.APPLYR_DIR", tmp_applyr)
    (tmp_applyr / "AGENT_INSTRUCTIONS.md").write_text("# Agent instructions\n")
    (tmp_applyr / "applyr.toml").write_text("[general]\nthreshold = 65\n")
    (tmp_applyr / "cv-master.md").write_text("# CV Master\n\n" + "Real experience. " * 200)
    return tmp_applyr


def _run(as_json=False):
    """Run doctor, returning its exit code (0 when it does not call sys.exit)."""
    from applyr.commands.workflow import cmd_doctor

    try:
        cmd_doctor(as_json=as_json)
    except SystemExit as e:
        return e.code
    return 0


class TestDoctorExitCode:
    """A health check that always exits 0 cannot gate anything — the whole
    point is that `applyr doctor && applyr cv generate 3` stops when broken."""

    def test_healthy_setup_exits_zero(self, doctor_home):
        assert _run() == 0

    def test_missing_database_exits_one(self, doctor_home):
        (doctor_home / "jobs.db").unlink()
        assert _run() == 1

    def test_unfilled_cv_master_exits_one(self, doctor_home):
        # The block that went unnoticed for nine sessions: a template CV master
        # produces CVs full of invented experience.
        (doctor_home / "cv-master.md").write_text("# CV Master\n")
        assert _run() == 1

    def test_missing_agent_instructions_exits_one(self, doctor_home):
        (doctor_home / "AGENT_INSTRUCTIONS.md").unlink()
        assert _run() == 1


class TestChromeIsNotBlocking:
    """Without Chrome only `cv pdf` breaks. Scoring, tracking and HTML
    generation all still work, so it must not fail the health check."""

    def test_missing_chrome_still_exits_zero(self, doctor_home, monkeypatch):
        monkeypatch.delenv("CHROME_BIN", raising=False)
        monkeypatch.setattr("os.path.isfile", lambda p: False)
        assert _run() == 0


class TestDoctorDoesNotMutate:
    """doctor must observe the environment, not create it. While it ran behind
    the CLI's auto-init the database was recreated before the check, so the
    NOT FOUND branch was unreachable and a missing database reported OK."""

    def test_does_not_recreate_a_missing_database(self, doctor_home):
        db = doctor_home / "jobs.db"
        db.unlink()
        _run()
        assert not db.exists()


class TestDoctorJson:
    """Agents read this, so the report is data on stdout and stays parseable
    even when the verdict is unhealthy."""

    def test_healthy_report_is_valid_json(self, doctor_home, capsys):
        code = _run(as_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["healthy"] is True
        assert payload["issues"] == 0

    def test_unhealthy_report_is_valid_json_and_names_the_check(self, doctor_home, capsys):
        (doctor_home / "jobs.db").unlink()
        code = _run(as_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert code == 1
        assert payload["healthy"] is False
        assert [c["name"] for c in payload["checks"] if c["status"] == "issue"] == ["Database"]
