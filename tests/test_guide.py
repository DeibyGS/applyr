"""`applyr guide` — one workflow section from the packaged instructions (ADR-016,
specs/compact-agent-instructions)."""

import json
import os
import subprocess
import sys

import pytest

import applyr.agent_instructions as ai
from applyr.agent_instructions import GUIDE_SLUGS, guide_section, packaged_instructions
from applyr.commands.workflow import cmd_guide
from applyr.errors import set_json_mode


@pytest.mark.parametrize("slug", list(GUIDE_SLUGS))
def test_every_slug_resolves_to_a_heading_in_the_packaged_document(slug):
    # A reworded heading must fail here, not in every agent that calls the slug.
    section = guide_section(slug)
    assert section is not None, f"{slug}: heading {GUIDE_SLUGS[slug]!r} not found"
    assert section.splitlines()[0] == GUIDE_SLUGS[slug]


def test_section_stops_at_the_next_heading_of_the_same_level():
    section = guide_section("decide")
    assert "### Step 4" in section
    assert "### Step 5" not in section


def test_section_keeps_its_own_subsections():
    section = guide_section("score")
    assert "#### Scoring rubric" in section
    assert "#### JSON template" in section


def test_hash_lines_inside_code_blocks_are_not_headings(monkeypatch):
    doc = "## Setup\n\n```bash\n# a shell comment\napplyr init\n```\n\nstill setup\n\n## Workflow\nnext\n"
    monkeypatch.setattr(ai, "packaged_instructions", lambda: doc)
    section = guide_section("setup")
    assert "still setup" in section
    assert "## Workflow" not in section


def test_list_as_json(capsys):
    cmd_guide(as_json=True)
    steps = json.loads(capsys.readouterr().out)["steps"]
    assert [s["slug"] for s in steps] == list(GUIDE_SLUGS)
    assert all(s["title"] and not s["title"].startswith("#") for s in steps)


def test_one_step_as_json(capsys):
    cmd_guide("verify", as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["slug"] == "verify"
    assert payload["title"] == "Step 6b — Verify grounding"
    assert payload["content"] == guide_section("verify")


def test_one_step_as_text_is_the_section_verbatim(capsys):
    cmd_guide("ats-rules")
    assert capsys.readouterr().out == guide_section("ats-rules")


def _json_error(capsys, fn):
    set_json_mode(True)
    try:
        with pytest.raises(SystemExit):
            fn()
    finally:
        set_json_mode(False)
    return json.loads(capsys.readouterr().err.strip().splitlines()[-1])["error"]


def test_unknown_slug_lists_the_valid_ones(capsys):
    err = _json_error(capsys, lambda: cmd_guide("nope"))
    assert err["code"] == "invalid_value"
    assert err["details"]["valid"] == list(GUIDE_SLUGS)


def test_broken_install_is_a_structured_not_found(monkeypatch, capsys):
    monkeypatch.setattr(ai, "packaged_instructions", lambda: "")
    assert _json_error(capsys, lambda: cmd_guide("score"))["code"] == "not_found"


def test_guide_works_before_init(tmp_path):
    env = {**os.environ, "APPLYR_HOME": str(tmp_path / "never-initialised")}
    result = subprocess.run([sys.executable, "-m", "applyr.cli", "--json", "guide", "decide"],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["slug"] == "decide"


def test_packaged_document_is_not_empty():
    # Guards the fixture the tests above rely on: the real template ships.
    assert "## Core Principles" in packaged_instructions()
