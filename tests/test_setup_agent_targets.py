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


# --- claude-skill (AC-19..AC-21) --------------------------------------------

SKILL = Path(".claude/skills/applyr/SKILL.md")


def test_claude_skill_has_frontmatter_and_the_stamped_core(run_cli, capsys, project):
    from applyr.agent_instructions import find_stamped_version, packaged_core
    from applyr import __version__
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude-skill"])
    assert code == 0, err
    text = (project / SKILL).read_text()
    assert text.startswith("---\nname: applyr\ndescription: ")
    assert "job offer" in text.split("---")[1] and "CV" in text.split("---")[1]
    assert packaged_core().strip() in text
    assert find_stamped_version(text) == __version__
    assert END_MARKER not in text  # the whole file is applyr's: no block to delimit


def test_claude_skill_global_writes_under_home(run_cli, capsys, project, fake_home):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude-skill", "--global"])
    assert code == 0, err
    assert (fake_home / SKILL).exists()
    assert not (project / SKILL).exists()


def test_claude_skill_is_never_auto_detected(run_cli, capsys, project):
    (project / SKILL).parent.mkdir(parents=True)
    (project / SKILL).write_text("---\nname: other\n---\nmine\n")
    out, err, code = _run(run_cli, capsys, ["setup-agent"])
    assert "No AI agent config detected" in out
    assert (project / SKILL).read_text() == "---\nname: other\n---\nmine\n"


def _stale_skill(project):
    from applyr.agent_instructions import STAMP_PREFIX
    (project / SKILL).parent.mkdir(parents=True)
    (project / SKILL).write_text(f"---\nname: applyr\n---\n\n{STAMP_PREFIX} 0.1.0 -->\nold core\n")


def test_stale_claude_skill_needs_force_and_is_then_rewritten_whole(run_cli, capsys, project):
    _stale_skill(project)
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude-skill"])
    assert "old core" in (project / SKILL).read_text()
    assert "--force" in err
    _run(run_cli, capsys, ["setup-agent", "--agent", "claude-skill", "--force"])
    text = (project / SKILL).read_text()
    assert "old core" not in text
    assert text.count("name: applyr") == 1


def test_foreign_skill_file_is_never_overwritten_without_force(run_cli, capsys, project):
    (project / SKILL).parent.mkdir(parents=True)
    (project / SKILL).write_text("my own skill\n")
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude-skill"])
    assert (project / SKILL).read_text() == "my own skill\n"
    assert "not written by applyr" in err


def test_global_supports_exactly_the_documented_four(run_cli, capsys, project, fake_home):
    out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "windsurf", "--global"])
    assert code != 0
    assert "claude, gemini, opencode, claude-skill" in err
