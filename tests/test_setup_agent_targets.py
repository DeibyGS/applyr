"""`setup-agent` native targets (ADR-016, specs/compact-agent-instructions AC-13..AC-18)."""

from pathlib import Path

import pytest

from applyr.agent_instructions import END_MARKER


def _run(run_cli, capsys, args):
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


@pytest.fixture
def project(tmp_path, monkeypatch, tmp_db):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "fake-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls, h=home: h))
    return home


@pytest.mark.parametrize("agent, rel_path", [
    ("gemini", "GEMINI.md"),
    ("copilot", ".github/copilot-instructions.md"),
    ("windsurf", ".windsurfrules"),
    ("cline", ".clinerules"),
])
def test_new_targets_write_their_file(run_cli, capsys, project, agent, rel_path):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", agent])
    assert code == 0, err
    text = (project / rel_path).read_text()  # parent dirs (.github/) created as needed
    assert "applyr next" in text
    assert text.rstrip().endswith(END_MARKER)


def test_cursor_writes_its_own_mdc_rule_with_frontmatter(run_cli, capsys, project):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "cursor"])
    assert code == 0, err
    mdc = (project / ".cursor" / "rules" / "applyr.mdc").read_text()
    assert mdc.startswith("---\n")
    assert "alwaysApply: true" in mdc
    assert not (project / ".cursorrules").exists()


def test_legacy_cursorrules_is_warned_about_and_left_untouched(run_cli, capsys, project):
    (project / ".cursorrules").write_text("my old rules\n")
    out, err, code = _run(run_cli, capsys, ["setup-agent"])  # detected via .cursorrules
    assert code == 0, err
    assert (project / ".cursorrules").read_text() == "my old rules\n"
    assert (project / ".cursor" / "rules" / "applyr.mdc").exists()
    assert ".cursorrules" in err


def test_global_cursor_is_refused_and_never_writes_home_cursorrules(run_cli, capsys, project, fake_home):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "cursor", "--global"])
    assert code != 0
    assert "Cursor's settings" in err
    assert not (fake_home / ".cursorrules").exists()


def test_global_gemini_writes_under_home(run_cli, capsys, project, fake_home):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "gemini", "--global"])
    assert code == 0, err
    assert "applyr next" in (fake_home / ".gemini" / "GEMINI.md").read_text()
    assert not (project / "GEMINI.md").exists()


@pytest.mark.parametrize("agent", ["copilot", "windsurf", "cline", "generic"])
def test_global_is_refused_for_tools_without_a_global_file(run_cli, capsys, project, fake_home, agent):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", agent, "--global"])
    assert code != 0
    for supported in ("claude", "gemini", "opencode"):
        assert supported in err


@pytest.mark.parametrize("rel_path, target", [
    ("GEMINI.md", "GEMINI.md"),
    (".github/copilot-instructions.md", ".github/copilot-instructions.md"),
    (".windsurfrules", ".windsurfrules"),
    (".clinerules", ".clinerules"),
])
def test_auto_detects_new_targets(run_cli, capsys, project, rel_path, target):
    (project / rel_path).parent.mkdir(parents=True, exist_ok=True)
    (project / rel_path).write_text("# existing\n")
    out, err, code = _run(run_cli, capsys, ["setup-agent"])
    assert code == 0, err
    text = (project / target).read_text()
    assert text.startswith("# existing\n")
    assert "applyr next" in text


def test_existing_agents_are_detected_before_new_ones(run_cli, capsys, project):
    (project / "CLAUDE.md").write_text("# claude\n")
    (project / "GEMINI.md").write_text("# gemini\n")
    _run(run_cli, capsys, ["setup-agent"])
    assert "applyr next" in (project / "CLAUDE.md").read_text()
    assert (project / "GEMINI.md").read_text() == "# gemini\n"
