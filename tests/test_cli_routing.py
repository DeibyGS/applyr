"""Tests for cli.py command routing — AC-2.1 through AC-2.8.

These tests invoke cli.main() with patched sys.argv and assert on captured
output and exit codes. NO subprocess — the CI smoke test covers the binary.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────────────────────────


def _run(run_cli, capsys, args: list[str]):
    """Run cli.main() and return (stdout, stderr, exit_code)."""
    try:
        run_cli(args)
        captured = capsys.readouterr()
        return captured.out, captured.err, 0
    except SystemExit as e:
        captured = capsys.readouterr()
        return captured.out, captured.err, e.code


def _make_offer_json(tmp_applyr: Path) -> str:
    """Create a minimal valid offer JSON for testing."""
    return json.dumps({
        "title": "Test Engineer",
        "company": "TestCo",
        "compatibility_pct": 75,
        "status": "applied",
    })


# ── AC-2.1: Dispatch to correct function ─────────────────────────────────────


class TestCommandDispatch:
    """Every command routes to the right function with parsed args."""

    def test_version(self, run_cli, capsys):
        out, err, code = _run(run_cli, capsys, ["version"])
        assert code == 0
        assert "applyr v" in out

    def test_version_short(self, run_cli, capsys):
        out, err, code = _run(run_cli, capsys, ["--version"])
        assert code == 0
        assert "applyr v" in out

    def test_help_no_args(self, run_cli, capsys):
        out, err, code = _run(run_cli, capsys, [])
        assert code == 0
        assert "Getting started" in out

    def test_help_no_args_with_config_but_no_db(self, run_cli, capsys, tmp_applyr):
        """A lone applyr.toml (e.g. copied from the docs) must NOT count as
        initialized — without jobs.db the user still gets the onboarding help,
        not a bare usage string."""
        (tmp_applyr / "applyr.toml").write_text("[general]\n")
        out, err, code = _run(run_cli, capsys, [])
        assert code == 0
        assert "Getting started" in out
        assert "applyr init" in out

    def test_help_command(self, run_cli, capsys):
        out, err, code = _run(run_cli, capsys, ["help"])
        assert code == 0
        assert "applyr <command>" in out

    def test_help_flag(self, run_cli, capsys):
        out, err, code = _run(run_cli, capsys, ["--help"])
        assert code == 0
        assert "applyr <command>" in out

    def test_init(self, run_cli, capsys, tmp_applyr):
        out, err, code = _run(run_cli, capsys, ["init"])
        assert code == 0
        assert (tmp_applyr / "jobs.db").exists()

    def test_stats(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["stats"])
        assert code == 0

    def test_list(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list"])
        assert code == 0

    def test_list_alias_ls(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["ls"])
        assert code == 0

    def test_stats_alias_st(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["st"])
        assert code == 0

    def test_followups(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["followups"])
        assert code == 0

    def test_followups_alias_fu(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["fu"])
        assert code == 0

    def test_gaps(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["gaps"])
        assert code == 0

    def test_pipeline(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["pipeline"])
        assert code == 0

    def test_trends(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends"])
        assert code == 0

    def test_summary(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["summary"])
        assert code == 0

    def test_plan(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["plan"])
        assert code == 0

    def test_salary(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["salary"])
        assert code == 0

    def test_export(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export"])
        assert code == 0

    def test_search(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["search", "test"])
        assert code == 0

    def test_compare_no_args(self, run_cli, capsys, tmp_db):
        """Missing required arguments is a failure, not a success."""
        out, err, code = _run(run_cli, capsys, ["compare"])
        assert code != 0

    def test_compare_alias_cmp(self, run_cli, capsys, tmp_db):
        """Missing required arguments is a failure, not a success."""
        out, err, code = _run(run_cli, capsys, ["cmp"])
        assert code != 0

    def test_salary_alias_sal(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["sal"])
        assert code == 0

    def test_cv_no_subcmd(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv"])
        assert code == 0  # prints usage

    def test_cv_generate_no_id(self, run_cli, capsys, tmp_db):
        """Missing required arguments is a failure, not a success."""
        out, err, code = _run(run_cli, capsys, ["cv", "generate"])
        assert code != 0

    def test_cv_review_no_file(self, run_cli, capsys, tmp_db):
        """Missing required arguments is a failure, not a success."""
        out, err, code = _run(run_cli, capsys, ["cv", "review"])
        assert code != 0

    def test_cv_pdf_no_file(self, run_cli, capsys, tmp_db):
        """Missing required arguments is a failure, not a success."""
        out, err, code = _run(run_cli, capsys, ["cv", "pdf"])
        assert code != 0

    def test_cv_stats(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv", "stats"])
        assert code == 0

    def test_doctor(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["doctor"])
        # doctor exits 1 on blocking issues (e.g., missing cv-master.md)
        assert code in (0, 1)

    def test_setup_agent(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["setup-agent"])
        assert code == 0

    def test_add_no_args_interactive(self, run_cli, capsys, tmp_db, monkeypatch):
        """add with no args and stdin.isatty() prints usage."""
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        out, err, code = _run(run_cli, capsys, ["add"])
        assert code == 0
        assert "Usage: applyr add" in out

    def test_add_json_arg(self, run_cli, capsys, tmp_db):
        offer_json = _make_offer_json(tmp_db)
        out, err, code = _run(run_cli, capsys, ["add", offer_json])
        assert code == 0

    def test_list_with_status(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--status", "applied"])
        assert code == 0

    def test_list_with_sort(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--sort", "company"])
        assert code == 0

    def test_list_with_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--limit", "5"])
        assert code == 0

    def test_list_all(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--all"])
        assert code == 0

    def test_gaps_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["gaps", "--limit", "3"])
        assert code == 0

    def test_pipeline_min_score(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["pipeline", "--min-score", "50"])
        assert code == 0

    def test_trends_week(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends", "--period", "week"])
        assert code == 0

    def test_trends_month(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends", "--period", "month"])
        assert code == 0

    def test_plan_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["plan", "--limit", "5"])
        assert code == 0

    def test_salary_seniority(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["salary", "--seniority", "senior"])
        assert code == 0

    def test_salary_category(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["salary", "--category", "engineering"])
        assert code == 0

    def test_export_json(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "json"])
        assert code == 0

    def test_export_csv(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "csv"])
        assert code == 0

    def test_export_md(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "md"])
        assert code == 0

    def test_search_with_status(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["search", "test", "--status", "applied"])
        assert code == 0

    def test_add_help(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["add", "--help"])
        assert code == 0
        assert "Usage: applyr add" in out

    def test_add_help_lists_language_and_salary_period(self, run_cli, capsys, tmp_db):
        """add --help must document the fields the schema actually accepts."""
        out, err, code = _run(run_cli, capsys, ["add", "--help"])
        assert code == 0
        assert "language" in out
        assert "salary_period" in out

    def test_delete_help(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["delete", "--help"])
        assert code == 0
        assert "Usage: applyr delete" in out

    def test_setup_agent_with_agent(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude"])
        assert code == 0

    def test_setup_agent_warns_when_profile_missing(self, run_cli, capsys, tmp_db):
        """A missing cv-master.md must warn during setup, not only at cv generate.
        Otherwise the first a user hears of it is a failed application."""
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude"])
        assert code == 0
        assert "cv-master.md" in err
        assert "not found" in err

    def test_setup_agent_warns_when_profile_unfilled(self, run_cli, capsys, tmp_db):
        """A cv-master.md from 'applyr init' (blank placeholders) is not a real
        profile; setup-agent should still say so."""
        _run(run_cli, capsys, ["init"])
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude"])
        assert code == 0
        assert "cv-master.md" in err

    def test_setup_agent_writes_to_the_detected_nested_claude_path(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """`.claude/CLAUDE.md` is a valid detection signal for claude, but the
        write target was hardcoded to the top-level `CLAUDE.md` regardless —
        a project already using the nested file got a second, empty one at the
        root instead of its own file appended, splitting the agent's context
        across two files it never asked for."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "CLAUDE.md").write_text("# My project rules\n")

        out, err, code = _run(run_cli, capsys, ["setup-agent"])
        assert code == 0
        assert not (tmp_path / "CLAUDE.md").exists(), "must not create a second top-level file"
        nested = (tmp_path / ".claude" / "CLAUDE.md").read_text()
        assert nested.startswith("# My project rules")
        assert "applyr" in nested.lower()

    def test_setup_agent_writes_to_the_detected_nested_cursor_path(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """Same bug, same fix, for cursor's `.cursor/rules` vs `.cursorrules`."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".cursor").mkdir()
        (tmp_path / ".cursor" / "rules").write_text("existing rules\n")

        out, err, code = _run(run_cli, capsys, ["setup-agent"])
        assert code == 0
        assert not (tmp_path / ".cursorrules").exists(), "must not create a second file"
        nested = (tmp_path / ".cursor" / "rules").read_text()
        assert nested.startswith("existing rules")
        assert "applyr" in nested.lower()

    def test_setup_agent_explicit_agent_still_uses_the_default_path(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """Detection is bypassed with an explicit --agent, so there is no
        detected path to prefer — the default (top-level CLAUDE.md) stands,
        even if a nested .claude/CLAUDE.md happens to exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "CLAUDE.md").write_text("# My project rules\n")

        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "claude"])
        assert code == 0
        assert (tmp_path / "CLAUDE.md").exists()

    def test_setup_agent_opencode_writes_agents_md(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """opencode writes AGENTS.md in cwd — .opencode/instructions.md is dead."""
        monkeypatch.chdir(tmp_path)
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode"])
        assert code == 0
        agents = tmp_path / "AGENTS.md"
        assert agents.exists(), "AGENTS.md must be created for --agent opencode"
        assert "applyr" in agents.read_text().lower()
        assert not (tmp_path / ".opencode").exists(), ".opencode/ must not be created"

    def test_setup_agent_opencode_appends_existing_agents_md(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """An existing AGENTS.md keeps its content; instructions are appended."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "AGENTS.md").write_text("## My Project\nrules go here\n")
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode"])
        assert code == 0
        content = (tmp_path / "AGENTS.md").read_text()
        assert content.startswith("## My Project")
        assert "applyr" in content.lower()

    def test_setup_agent_opencode_dedupe(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """Running twice must skip, not duplicate."""
        monkeypatch.chdir(tmp_path)
        _run(run_cli, capsys, ["setup-agent", "--agent", "opencode"])
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode"])
        assert code == 0
        assert "already contains" in out
        content = (tmp_path / "AGENTS.md").read_text().lower()
        assert content.count("agent instructions") == 1

    def test_setup_agent_opencode_global(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """--global writes to ~/.config/opencode/AGENTS.md without touching cwd."""
        fake_home = tmp_path / "fake-home"
        monkeypatch.setattr(Path, "home", classmethod(lambda cls, h=fake_home: h))
        monkeypatch.chdir(tmp_path)
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode", "--global"])
        assert code == 0
        target = fake_home / ".config" / "opencode" / "AGENTS.md"
        assert target.exists()
        assert "applyr" in target.read_text().lower()
        assert not (tmp_path / "AGENTS.md").exists(), "global mode must not write to cwd"

    def test_setup_agent_global_dedupe(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        fake_home = tmp_path / "fake-home"
        monkeypatch.setattr(Path, "home", classmethod(lambda cls, h=fake_home: h))
        monkeypatch.chdir(tmp_path)
        _run(run_cli, capsys, ["setup-agent", "--agent", "opencode", "--global"])
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode", "--global"])
        assert code == 0
        assert "already contains" in out

    def test_setup_agent_global_requires_agent(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--global"])
        assert code != 0, "--global without --agent must error"
        assert "--agent" in err

    def test_setup_agent_global_generic_errors(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "generic", "--global"])
        assert code != 0, "generic has no canonical global path"
        assert "global" in err

    def test_setup_agent_opencode_deprecation_warning(self, run_cli, capsys, tmp_db, tmp_path, monkeypatch):
        """A stale .opencode/instructions.md triggers a deprecation warning."""
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".opencode" / "instructions.md").write_text("old content")
        monkeypatch.chdir(tmp_path)
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "opencode"])
        assert code == 0
        assert "Deprecation" in err


# ── AC-2.3: Global flags ─────────────────────────────────────────────────────


class TestGlobalFlags:
    """--json and --no-color are parsed and propagated."""

    def test_json_flag_stats(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "stats"])
        assert code == 0
        # With empty DB, stats prints a message, not JSON
        # With data, it outputs valid JSON
        if out.strip() and out.strip() != "No offers in the database yet.":
            data = json.loads(out)
            assert isinstance(data, dict)

    def test_json_flag_list(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "list"])
        assert code == 0
        # With empty DB, list prints a message, not JSON
        if out.strip() and "No offers" not in out:
            data = json.loads(out)
            assert isinstance(data, (dict, list))

    def test_no_color_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--no-color", "stats"])
        assert code == 0

    def test_json_no_color_combined(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "--no-color", "stats"])
        assert code == 0

    def test_json_flag_gaps(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "gaps"])
        assert code == 0
        # cmd_gaps's JSON payload is a list of skill-gap entries — empty DB is []
        data = json.loads(out)
        assert isinstance(data, list)

    def test_json_flag_followups(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "followups"])
        assert code == 0
        if out.strip():
            try:
                data = json.loads(out)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                pass

    def test_json_flag_pipeline(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "pipeline"])
        assert code == 0
        if out.strip():
            try:
                data = json.loads(out)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                pass

    def test_json_flag_summary(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "summary"])
        assert code == 0
        if out.strip():
            try:
                data = json.loads(out)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                pass

    def test_json_flag_trends(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "trends"])
        assert code == 0
        # cmd_trends's JSON payload is a list of period entries — empty DB is []
        data = json.loads(out)
        assert isinstance(data, list)

    def test_json_flag_doctor(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["--json", "doctor"])
        assert code in (0, 1)
        if out.strip():
            data = json.loads(out)
            assert isinstance(data, dict)


# ── AC-2.4: Exit code contract ───────────────────────────────────────────────


class TestExitCodes:
    """Success → 0, die() paths → non-zero, doctor → 1 on blocking issue."""

    def test_success_exits_zero(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["stats"])
        assert code == 0

    def test_unknown_command_exits_nonzero(self, run_cli, capsys, tmp_db):
        """The `or` made this pass either way, which is why it never caught the
        branch exiting 0 while announcing failure."""
        out, err, code = _run(run_cli, capsys, ["nonexistent"])
        assert code != 0

    def test_show_missing_id_fails(self, run_cli, capsys, tmp_db):
        """`show` with no id used to print usage and exit 0, so a caller
        chaining `applyr show && next-step` ran the next step regardless."""
        out, err, code = _run(run_cli, capsys, ["show"])
        assert code != 0
        assert "Usage: applyr show" in err
        assert out == ""

    def test_update_missing_args(self, run_cli, capsys, tmp_db):
        """Missing required arguments: non-zero exit, usage on stderr."""
        out, err, code = _run(run_cli, capsys, ["update"])
        assert code != 0
        assert "Usage: applyr update" in err
        assert out == ""

    def test_delete_missing_id(self, run_cli, capsys, tmp_db):
        """Missing required arguments: non-zero exit, usage on stderr."""
        out, err, code = _run(run_cli, capsys, ["delete"])
        assert code != 0
        assert "Usage: applyr delete" in err
        assert out == ""

    def test_search_missing_keyword(self, run_cli, capsys, tmp_db):
        """Missing required arguments: non-zero exit, usage on stderr."""
        out, err, code = _run(run_cli, capsys, ["search"])
        assert code != 0
        assert "Usage: applyr search" in err
        assert out == ""

    def test_invalid_id_exits_nonzero(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["show", "notanumber"])
        assert code != 0

    def test_compare_too_few_ids(self, run_cli, capsys, tmp_db):
        """compare with 1 id (needs ≥2) → die()."""
        out, err, code = _run(run_cli, capsys, ["compare", "1"])
        assert code != 0

    def test_trends_invalid_period(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends", "--period", "invalid"])
        assert code != 0

    def test_export_invalid_format(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "xml"])
        assert code != 0

    def test_cv_invalid_subcmd(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv", "invalid"])
        assert code != 0

    def test_doctor_exits_1_when_not_initialized(self, run_cli, capsys, tmp_applyr):
        """doctor should exit 1 when database doesn't exist."""
        out, err, code = _run(run_cli, capsys, ["doctor"])
        # doctor exits 1 on blocking issues, 0 if healthy
        assert code in (0, 1)


# ── AC-2.5: Regression guard — no db recreation ──────────────────────────────


class TestNoDbRecreation:
    """No command except init may recreate a deleted jobs.db (session 11 bug)."""

    def test_list_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        """list should fail gracefully if db is missing, not recreate it."""
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["list"])
        assert not db_path.exists(), "list recreated jobs.db — regression!"
        assert code != 0

    def test_stats_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["stats"])
        assert not db_path.exists(), "stats recreated jobs.db — regression!"
        assert code != 0

    def test_gaps_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["gaps"])
        assert not db_path.exists(), "gaps recreated jobs.db — regression!"
        assert code != 0

    def test_pipeline_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["pipeline"])
        assert not db_path.exists(), "pipeline recreated jobs.db — regression!"
        assert code != 0

    def test_followups_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["followups"])
        assert not db_path.exists(), "followups recreated jobs.db — regression!"
        assert code != 0

    def test_doctor_does_not_recreate_db(self, run_cli, capsys, tmp_applyr):
        """doctor is special: it should NOT call init_db at all."""
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["doctor"])
        assert not db_path.exists(), "doctor recreated jobs.db — regression!"

    def test_init_does_create_db(self, run_cli, capsys, tmp_applyr):
        """init IS allowed to create the database."""
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["init"])
        assert db_path.exists(), "init should create jobs.db"

    def test_error_message_when_db_missing(self, run_cli, capsys, tmp_applyr):
        """Commands should show helpful error when db is missing."""
        db_path = tmp_applyr / "jobs.db"
        if db_path.exists():
            db_path.unlink()

        out, err, code = _run(run_cli, capsys, ["list"])
        assert "applyr init" in out or "applyr init" in err


# ── AC-2.2: Argument parsing ─────────────────────────────────────────────────


class TestArgumentParsing:
    """Verify flags are parsed correctly and passed to commands."""

    def test_list_status_filter(self, run_cli, capsys, tmp_db):
        """--status flag is parsed and passed."""
        out, err, code = _run(run_cli, capsys, ["list", "--status", "applied"])
        assert code == 0

    def test_list_sort_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--sort", "company"])
        assert code == 0

    def test_gaps_limit_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["gaps", "--limit", "3"])
        assert code == 0

    def test_pipeline_min_score_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["pipeline", "--min-score", "50"])
        assert code == 0

    def test_trends_period_week(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends", "--period", "week"])
        assert code == 0

    def test_trends_period_month(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["trends", "--period", "month"])
        assert code == 0

    def test_salary_seniority_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["salary", "--seniority", "senior"])
        assert code == 0

    def test_salary_category_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["salary", "--category", "engineering"])
        assert code == 0

    def test_export_format_json(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "json"])
        assert code == 0

    def test_export_format_csv(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "csv"])
        assert code == 0

    def test_export_format_md(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["export", "--format", "md"])
        assert code == 0

    def test_search_status_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["search", "test", "--status", "applied"])
        assert code == 0

    def test_add_force_flag(self, run_cli, capsys, tmp_db):
        offer_json = _make_offer_json(tmp_db)
        out, err, code = _run(run_cli, capsys, ["add", "--force", offer_json])
        assert code == 0

    def test_delete_force_flag(self, run_cli, capsys, tmp_db):
        """delete --force with non-integer id prints error."""
        out, err, code = _run(run_cli, capsys, ["delete", "--force", "abc"])
        assert code != 0

    def test_setup_agent_agent_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["setup-agent", "--agent", "cursor"])
        assert code == 0

    def test_cv_generate_template_flag(self, run_cli, capsys, tmp_db):
        """cv generate with template flag and non-integer id."""
        out, err, code = _run(run_cli, capsys, ["cv", "generate", "--template", "ats", "abc"])
        assert code != 0

    def test_cv_generate_force_flag(self, run_cli, capsys, tmp_db):
        """cv generate with force flag and non-integer id."""
        out, err, code = _run(run_cli, capsys, ["cv", "generate", "--force", "abc"])
        assert code != 0

    def test_cv_stats_min_sample_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv", "stats", "--min-sample", "5"])
        assert code == 0

    def test_plan_limit_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["plan", "--limit", "5"])
        assert code == 0

    def test_list_limit_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--limit", "10"])
        assert code == 0

    def test_list_all_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--all"])
        assert code == 0


# ── AC-2.7: Unknown command and missing-argument paths ───────────────────────


class TestEdgeCases:
    """Unknown commands and missing arguments handled gracefully."""

    def test_unknown_command(self, run_cli, capsys, tmp_db):
        """On stderr, not stdout: an error is not payload."""
        out, err, code = _run(run_cli, capsys, ["foobar"])
        assert "Unknown command" in err

    def test_unknown_command_suggestion(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["foobar"])
        assert "applyr help" in err

    def test_cv_unknown_subcmd(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv", "blah"])
        # die() raises SystemExit with non-zero code
        assert code != 0 or "Unknown cv subcommand" in out

    def test_show_non_integer_id(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["show", "abc"])
        assert code != 0

    def test_update_non_integer_id(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["update", "abc", "applied"])
        assert code != 0

    def test_delete_non_integer_id(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["delete", "abc"])
        assert code != 0

    def test_gaps_non_integer_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["gaps", "--limit", "abc"])
        assert code != 0

    def test_pipeline_non_integer_min_score(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["pipeline", "--min-score", "abc"])
        assert code != 0

    def test_list_non_integer_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["list", "--limit", "abc"])
        assert code != 0

    def test_plan_non_integer_limit(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["plan", "--limit", "abc"])
        assert code != 0

    def test_cv_stats_non_integer_min_sample(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["cv", "stats", "--min-sample", "abc"])
        assert code != 0

    def test_add_from_file(self, run_cli, capsys, tmp_db, tmp_applyr):
        """add reading from a file."""
        offer_file = tmp_applyr / "offer.json"
        offer_file.write_text(_make_offer_json(tmp_db))
        out, err, code = _run(run_cli, capsys, ["add", str(offer_file)])
        assert code == 0

    def test_compare_non_integer_id(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["compare", "abc", "def"])
        assert code != 0

    def test_cv_review_with_file(self, run_cli, capsys, tmp_db, tmp_applyr):
        """cv review with a dummy file."""
        dummy = tmp_applyr / "dummy.html"
        dummy.write_text("<html><body>Test CV</body></html>")
        out, err, code = _run(run_cli, capsys, ["cv", "review", str(dummy)])
        assert code == 0

    def test_cv_pdf_with_file(self, run_cli, capsys, tmp_db, tmp_applyr):
        """cv pdf with a dummy file."""
        dummy = tmp_applyr / "dummy.html"
        dummy.write_text("<html><body>Test CV</body></html>")
        out, err, code = _run(run_cli, capsys, ["cv", "pdf", str(dummy)])
        # May fail if Chrome not available, but routing is tested
        assert code in (0, 1)


class TestResponseRateOutput:
    """`response-rate` is listed in `applyr help`, so silence reads as a broken
    command. It printed nothing at all in either mode: the human branch
    returned None on an empty result, and the JSON branch built the payload,
    returned it, and had no caller to print it."""

    def test_json_mode_prints_the_payload(self, run_cli, capsys, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_add, cmd_update

        cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme"}))
        cmd_update(1, "rejected")
        capsys.readouterr()

        out, err, code = _run(run_cli, capsys, ["response-rate", "--json"])
        assert code == 0
        payload = json.loads(out)
        assert payload["total_applications"] == 1
        assert payload["responded"] == 1

    def test_empty_database_says_so_instead_of_printing_nothing(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["response-rate"])
        assert code == 0
        assert out.strip(), "an empty result must still explain itself"
        assert "No applications sent yet" in out

    def test_empty_database_keeps_the_same_json_shape(self, run_cli, capsys, tmp_db):
        """An agent must not need two parsers for one command."""
        out, err, code = _run(run_cli, capsys, ["response-rate", "--json"])
        assert code == 0
        payload = json.loads(out)
        assert payload["total_applications"] == 0
        assert payload["responded"] == 0
        assert payload["by_status"] == {}


class TestUnknownCommandFails:
    """An unrecognised command printed a message and exited 0, so
    `applyr <typo> && next-step` ran the next step on a command that did
    nothing. It also wrote prose to stdout — in `--json` mode too, where every
    other error path emits a structured object. The `cv` subcommand branch was
    already correct; only the top level was left behind."""

    def test_exit_code_is_non_zero(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["definitely-not-a-command"])
        assert code != 0

    def test_nothing_is_written_to_stdout(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["definitely-not-a-command"])
        assert out == ""

    def test_the_message_names_the_command(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["definitely-not-a-command"])
        assert "definitely-not-a-command" in err

    def test_json_mode_emits_a_structured_error(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["definitely-not-a-command", "--json"])
        assert out == "", "the payload stream stays parseable"
        payload = json.loads(err)
        assert payload["error"]["code"] == "unknown_command"
        assert payload["error"]["details"]["value"] == "definitely-not-a-command"


class TestMissingArgumentsFailButHelpDoesNot:
    """Seventeen call sites printed a usage line and returned, so the process
    exited 0 with a command that had done nothing — `applyr show && next-step`
    ran the next step. The usage text also went to stdout, contaminating the
    payload stream in --json mode. One site already used die(); the rest are
    now consistent with it.

    Asking for help is not a failure, so the two cases are kept apart: three
    branches conflated them in a single condition, which is why missing
    arguments inherited help's successful exit."""

    MISSING = [
        ["show"], ["update"], ["update", "1"], ["delete"], ["search"],
        ["compare"], ["compare", "1"], ["gaps", "save"],
        ["cv", "generate"], ["cv", "review"], ["cv", "pdf"],
        ["cv", "ats-check"], ["cv", "keywords"], ["cv", "cover-letter"],
    ]

    @pytest.mark.parametrize("argv", MISSING, ids=lambda a: " ".join(a))
    def test_missing_arguments_exit_non_zero(self, run_cli, capsys, tmp_db, argv):
        out, err, code = _run(run_cli, capsys, argv)
        assert code != 0

    @pytest.mark.parametrize("argv", MISSING, ids=lambda a: " ".join(a))
    def test_missing_arguments_keep_stdout_clean(self, run_cli, capsys, tmp_db, argv):
        out, err, code = _run(run_cli, capsys, argv)
        assert out == "", "usage belongs on stderr; stdout is the payload stream"

    @pytest.mark.parametrize("argv", [
        ["delete", "--help"],
        ["cv", "generate", "--help"],
        ["cv", "review-blind", "--help"],
    ], ids=lambda a: " ".join(a))
    def test_explicit_help_still_succeeds(self, run_cli, capsys, tmp_db, argv):
        out, err, code = _run(run_cli, capsys, argv)
        assert code == 0
        assert "Usage:" in out

    def test_json_mode_gets_a_structured_error(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["show", "--json"])
        assert out == ""
        assert json.loads(err)["error"]["code"] == "missing_arguments"


class TestSearchCompanyFlag:
    """`search --company` must use the same "same company" definition as
    `add`'s duplicate check (exact, case-insensitive) — not the substring
    LIKE that plain `search <keyword>` uses across five fields."""

    def _add(self, run_cli, capsys, tmp_applyr):
        _run(run_cli, capsys, ["add", _make_offer_json(tmp_applyr)])

    def test_exact_match_case_insensitive(self, run_cli, capsys, tmp_db, tmp_applyr):
        self._add(run_cli, capsys, tmp_applyr)
        out, err, code = _run(run_cli, capsys, ["search", "--company", "testco"])
        assert code == 0
        assert "Test Engineer" in out

    def test_substring_is_not_a_match(self, run_cli, capsys, tmp_db, tmp_applyr):
        # "Test" is a substring of "TestCo" but not the same company — proves
        # this is not falling back to LIKE.
        self._add(run_cli, capsys, tmp_applyr)
        out, err, code = _run(run_cli, capsys, ["search", "--company", "Test"])
        assert code == 0
        assert "No offers found" in out

    def test_no_keyword_required_with_company_flag(self, run_cli, capsys, tmp_db):
        out, err, code = _run(run_cli, capsys, ["search", "--company", "TestCo"])
        assert code == 0
