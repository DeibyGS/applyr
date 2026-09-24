"""Tests for AGENT_INSTRUCTIONS.md distribution.

`setup-agent` copies these instructions into other projects' AI config, so a
stale local copy does not stay local: it propagates outdated guidance into every
project the user runs it in. Before v0.8.3 there was no update path at all —
`init` wrote the file once and `_get_agent_instructions()` preferred it forever.
"""

import pytest

from applyr import __version__
from applyr.agent_instructions import (
    INJECT_SEPARATOR,
    STAMP_PREFIX,
    find_stamped_version,
    is_stale,
    is_stale_version,
    packaged_instructions,
    stamp,
    stamped_version,
    END_MARKER,
    split_stamped_block,
    with_end_marker,
)


@pytest.fixture
def core_home(tmp_applyr, monkeypatch):
    """An applyr home wired into core.py, which binds APPLYR_DIR at import time."""
    monkeypatch.setattr("applyr.commands.core.APPLYR_DIR", tmp_applyr)
    return tmp_applyr


class TestStamp:
    """The stamp is written at copy time, not stored in the template, so a
    release cannot ship a template claiming a version it is not."""

    def test_stamp_precedes_the_content(self):
        stamped = stamp("# Agent Instructions\n")
        assert stamped.startswith(STAMP_PREFIX)
        assert stamped.endswith("# Agent Instructions\n")

    def test_roundtrip_recovers_the_running_version(self):
        assert stamped_version(stamp("body")) == __version__

    def test_packaged_template_ships_with_the_package(self):
        # A missing template would make setup-agent silently fall back to a
        # pointer URL, which is the failure this whole module exists to avoid.
        assert packaged_instructions().strip()

    def test_template_carries_no_hardcoded_stamp(self):
        # If the template itself were stamped, every release would need a third
        # version bump and would eventually ship a lie.
        assert stamped_version(packaged_instructions()) is None


class TestStaleness:

    def test_unstamped_copy_is_stale(self):
        # Every file written before v0.8.3 looks like this.
        assert is_stale("# applyr — Agent Instructions\n")

    def test_older_stamp_is_stale(self):
        assert is_stale(f"{STAMP_PREFIX} 0.1.0 -->\nbody")

    def test_current_stamp_is_not_stale(self):
        assert not is_stale(stamp("body"))

    def test_newer_stamp_is_not_stale(self):
        # The user downgraded. Warning them about the future is noise.
        assert not is_stale(f"{STAMP_PREFIX} 99.0.0 -->\nbody")

    @pytest.mark.parametrize("first_line", [
        f"{STAMP_PREFIX} banana -->",       # not a version
        f"{STAMP_PREFIX}  -->",             # empty
        "<!-- applyr-version 0.8.3 -->",    # missing colon
        f"{STAMP_PREFIX} 0.8.3",            # unterminated comment
    ])
    def test_malformed_stamp_reads_as_stale(self, first_line):
        # Unparseable means unknown, and unknown must not be treated as current.
        assert is_stale(f"{first_line}\nbody")


class TestFindStampedVersion:
    """setup-agent injects instructions after whatever content a target file
    (CLAUDE.md, AGENTS.md, .cursorrules) already has, so the stamp is never on
    line 1 there — unlike the canonical ~/.applyr/AGENT_INSTRUCTIONS.md copy."""

    def test_finds_stamp_after_other_content(self):
        text = f"# My project\n\nsome rules\n\n{stamp('body')}"
        assert find_stamped_version(text) == __version__

    def test_returns_none_when_no_stamp_present(self):
        assert find_stamped_version("# My project\n\nno applyr instructions here\n") is None

    def test_returns_the_last_stamp_when_more_than_one(self):
        text = f"{STAMP_PREFIX} 0.1.0 -->\nold block\n\n---\n\n{STAMP_PREFIX} 9.9.9 -->\nnew block\n"
        assert find_stamped_version(text) == "9.9.9"


class TestSplitStampedBlock:
    """Used by --force to replace a stale injected block in place, keeping the
    user's text on both sides of it (ADR-016)."""

    def test_legacy_block_runs_to_end_of_file(self):
        text = f"# My project{INJECT_SEPARATOR}{stamp('old body')}"
        parts = split_stamped_block(text)
        assert (parts.head, parts.tail, parts.legacy) == ("# My project", "", True)

    def test_end_marked_block_keeps_text_after_it(self):
        text = f"# Mine{INJECT_SEPARATOR}{with_end_marker(stamp('old'))}\n\n## After\nkeep me\n"
        parts = split_stamped_block(text)
        assert parts.head == "# Mine"
        assert parts.tail == "\n\n## After\nkeep me\n"
        assert parts.block.endswith(END_MARKER)
        assert parts.legacy is False

    def test_returns_text_unchanged_when_no_stamp_present(self):
        text = "# My project\n\nno applyr instructions here\n"
        assert split_stamped_block(text).head == text

    def test_older_blocks_are_dropped_keeping_text_between_them(self):
        # Built outside the f-string: a backslash inside an f-string expression is a
        # SyntaxError before Python 3.12, and CI still runs 3.11.
        older = with_end_marker(f"{STAMP_PREFIX} 0.1.0 -->\nfirst")
        text = (
            f"# My project{INJECT_SEPARATOR}{older}"
            f"\n\nbetween{INJECT_SEPARATOR}{STAMP_PREFIX} 0.2.0 -->\nsecond"
        )
        assert split_stamped_block(text).head == f"# My project{INJECT_SEPARATOR}between"

    def test_older_legacy_block_is_dropped_entirely(self):
        text = (
            f"# My project{INJECT_SEPARATOR}{STAMP_PREFIX} 0.1.0 -->\nfirst"
            f"{INJECT_SEPARATOR}{STAMP_PREFIX} 0.2.0 -->\nsecond"
        )
        assert split_stamped_block(text).head == "# My project"

    def test_handles_a_stamp_with_no_preceding_content(self):
        assert split_stamped_block(stamp("body")).head == ""


class TestSetupAgentForceKeepsUserText:
    """End to end through cmd_setup_agent (AC-01..AC-05)."""

    @pytest.fixture
    def project(self, tmp_path, monkeypatch, tmp_applyr):
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def _run(self, force=False):
        from applyr.commands.core import cmd_setup_agent
        cmd_setup_agent(agent="claude", force=force)

    def test_new_file_ends_with_the_marker(self, project):
        self._run()
        assert (project / "CLAUDE.md").read_text().rstrip().endswith(END_MARKER)

    def test_force_keeps_text_before_and_after_the_block(self, project):
        before, after = "# Mine\n\nhello", "\n\n## My notes\nkeep me\n"
        stale = with_end_marker(f"{STAMP_PREFIX} 0.1.0 -->\nold body")
        (project / "CLAUDE.md").write_text(f"{before}{INJECT_SEPARATOR}{stale}{after}")
        self._run(force=True)
        text = (project / "CLAUDE.md").read_text()
        assert text.startswith(before + INJECT_SEPARATOR)
        assert text.endswith(END_MARKER + after)
        assert "old body" not in text

    def test_legacy_block_is_replaced_and_foreign_sections_are_warned(self, project, capsys):
        legacy = f"# Mine{INJECT_SEPARATOR}{STAMP_PREFIX} 0.1.0 -->\n## Core Principles\nold\n\n## My own notes\nx\n"
        (project / "CLAUDE.md").write_text(legacy)
        self._run(force=True)
        text = (project / "CLAUDE.md").read_text()
        assert text.startswith("# Mine" + INJECT_SEPARATOR)
        assert text.rstrip().endswith(END_MARKER)
        err = capsys.readouterr().err
        assert "## My own notes" in err
        assert "## Core Principles" not in err

    def test_legacy_block_of_pure_template_does_not_warn(self, project, capsys):
        (project / "CLAUDE.md").write_text(f"# Mine{INJECT_SEPARATOR}{STAMP_PREFIX} 0.1.0 -->\n## Core Principles\nold\n")
        self._run(force=True)
        assert "end marker" not in capsys.readouterr().err

    def test_force_twice_leaves_exactly_one_block(self, project, monkeypatch):
        import applyr.commands.core as core
        monkeypatch.setattr(core, "is_stale_version", lambda _v: True)  # every run really refreshes
        (project / "CLAUDE.md").write_text("# Mine\n")
        self._run()
        self._run(force=True)
        self._run(force=True)
        text = (project / "CLAUDE.md").read_text()
        assert text.count(STAMP_PREFIX) == 1
        assert text.count(END_MARKER) == 1
        assert text.startswith("# Mine" + INJECT_SEPARATOR)


class TestIsStaleVersion:

    def test_none_is_stale(self):
        assert is_stale_version(None)

    def test_older_version_is_stale(self):
        assert is_stale_version("0.1.0")

    def test_current_version_is_not_stale(self):
        assert not is_stale_version(__version__)

    def test_newer_version_is_not_stale(self):
        assert not is_stale_version("99.0.0")


class TestInit:

    def test_writes_stamped_packaged_instructions(self, core_home):
        from applyr.commands.core import cmd_init

        cmd_init()

        written = (core_home / "AGENT_INSTRUCTIONS.md").read_text()
        assert stamped_version(written) == __version__
        assert not is_stale(written)

    def test_does_not_overwrite_an_existing_file(self, core_home):
        from applyr.commands.core import cmd_init

        local = core_home / "AGENT_INSTRUCTIONS.md"
        local.write_text("# My own edited instructions\n")
        cmd_init()

        assert local.read_text() == "# My own edited instructions\n"


class TestGetAgentInstructions:
    """What `setup-agent` actually injects: the stamped core (ADR-016). The
    local-copy rules below apply to the full-document fallback."""

    def test_injects_the_stamped_core_not_the_full_document(self, core_home):
        from applyr.agent_instructions import packaged_core
        from applyr.commands.core import _get_agent_instructions

        (core_home / "AGENT_INSTRUCTIONS.md").write_text(stamp("# Hand-edited full copy\n"))
        result = _get_agent_instructions()

        assert stamped_version(result) == __version__
        assert packaged_core() in result
        assert "Hand-edited full copy" not in result

    def test_core_is_short_and_carries_the_rules_that_must_not_be_skipped(self):
        from applyr.agent_instructions import packaged_core

        core = packaged_core()
        assert len(core.splitlines()) <= 100
        for must in ("applyr next", "applyr guide", "applyr role", "cv verify", "Stop and ask the user",
                     "only source of truth"):
            assert must in core, must

    def test_current_local_copy_wins(self, core_home):
        from applyr.commands.core import _get_full_instructions

        local_text = stamp("# Hand-edited but current\n")
        (core_home / "AGENT_INSTRUCTIONS.md").write_text(local_text)

        assert _get_full_instructions() == local_text

    def test_stale_local_copy_is_bypassed_for_the_packaged_one(self, core_home):
        from applyr.commands.core import _get_full_instructions

        (core_home / "AGENT_INSTRUCTIONS.md").write_text("# Ancient instructions\n")
        result = _get_full_instructions()

        assert stamped_version(result) == __version__
        assert "Ancient instructions" not in result

    def test_stale_copy_warns_on_stderr(self, core_home, capsys):
        from applyr.commands.core import _get_full_instructions

        (core_home / "AGENT_INSTRUCTIONS.md").write_text("# Ancient instructions\n")
        _get_full_instructions()

        captured = capsys.readouterr()
        assert __version__ in captured.err
        assert captured.out == ""  # warnings are not data (ADR 006)

    def test_stale_copy_is_left_untouched_on_disk(self, core_home):
        from applyr.commands.core import _get_full_instructions

        local = core_home / "AGENT_INSTRUCTIONS.md"
        local.write_text("# Ancient instructions\n")
        _get_full_instructions()

        # The file is the user's and may hold hand edits. Bypass it, never rewrite it.
        assert local.read_text() == "# Ancient instructions\n"

    def test_falls_back_to_the_package_when_no_local_copy_exists(self, core_home):
        from applyr.commands.core import _get_full_instructions

        result = _get_full_instructions()

        assert stamped_version(result) == __version__


class TestDoctorReportsDrift:
    """Stale instructions are reported but must not gate: `setup-agent` already
    serves the packaged copy, so the setup still works correctly."""

    @pytest.fixture
    def doctor_home(self, tmp_db, tmp_applyr, monkeypatch):
        monkeypatch.setattr("applyr.commands.workflow.APPLYR_DIR", tmp_applyr)
        (tmp_applyr / "applyr.toml").write_text("[general]\nthreshold = 65\n")
        (tmp_applyr / "cv-master.md").write_text("# CV Master\n\n" + "Real experience. " * 200)
        return tmp_applyr

    def test_stale_copy_is_a_note_not_an_issue(self, doctor_home):
        from applyr.commands.workflow import _check_agent_instructions

        (doctor_home / "AGENT_INSTRUCTIONS.md").write_text("# Ancient\n")

        assert _check_agent_instructions()["status"] == "note"

    def test_current_copy_is_ok(self, doctor_home):
        from applyr.commands.workflow import _check_agent_instructions

        (doctor_home / "AGENT_INSTRUCTIONS.md").write_text(stamp("# Current\n"))

        assert _check_agent_instructions()["status"] == "ok"

    def test_missing_copy_is_still_an_issue(self, doctor_home):
        from applyr.commands.workflow import _check_agent_instructions

        assert _check_agent_instructions()["status"] == "issue"

    def test_stale_copy_does_not_make_doctor_exit_one(self, doctor_home):
        from applyr.commands.workflow import cmd_doctor

        (doctor_home / "AGENT_INSTRUCTIONS.md").write_text("# Ancient\n")

        try:
            cmd_doctor()
        except SystemExit as e:
            pytest.fail(f"a stale copy must not gate — doctor exited {e.code}")
