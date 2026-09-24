"""Distribution of AGENT_INSTRUCTIONS.md — the file `setup-agent` injects into
other projects' AI config.

The local copy at `~/.applyr/AGENT_INSTRUCTIONS.md` is written once by `init` and
never overwritten, so before v0.8.3 an upgraded package kept serving whatever
instructions the first install happened to ship. A version stamp on the first
line makes that drift visible: a stale copy is bypassed in favour of the packaged
one, and reported by `doctor`. The file on disk is never rewritten behind the
user's back — it is theirs and may carry hand edits.
"""

from pathlib import Path
from typing import NamedTuple

from applyr import __version__

STAMP_PREFIX = "<!-- applyr-version:"
STAMP_SUFFIX = "-->"

# What setup-agent puts between a target file's existing content and the block
# it injects. Shared here so the block can be found and replaced later, not
# just appended after.
INJECT_SEPARATOR = "\n\n---\n\n"

# Closes an injected block (ADR-016). Before it existed the block was assumed to
# run to end of file, so `--force` deleted anything a user wrote after it.
END_MARKER = "<!-- applyr-end -->"

# Written only when the packaged template cannot be found — a pointer, not
# instructions. It carries no stamp, so it reads as stale and gets replaced by
# the real thing as soon as one is available.
FALLBACK = (
    "# applyr — Agent Instructions\n\n"
    "Download the full instructions from:\n"
    "https://github.com/DeibyGS/applyr/blob/main/applyr/templates/AGENT_INSTRUCTIONS.md\n"
)


def packaged_instructions() -> str:
    """Read the AGENT_INSTRUCTIONS.md bundled with the installed package."""
    src = Path(__file__).parent / "templates" / "AGENT_INSTRUCTIONS.md"
    return src.read_text() if src.exists() else ""


def stamp(text: str) -> str:
    """Prefix instructions with the version of applyr writing them.

    The stamp is applied at write time rather than stored in the template, so a
    release can never ship a template claiming the wrong version — there is one
    place to bump, not two.
    """
    return f"{STAMP_PREFIX} {__version__} {STAMP_SUFFIX}\n{text}"


def stamped_version(text: str) -> str | None:
    """Return the version stamped on the first line, or None if absent or malformed."""
    first = text.split("\n", 1)[0].strip()
    if not (first.startswith(STAMP_PREFIX) and first.endswith(STAMP_SUFFIX)):
        return None
    return first[len(STAMP_PREFIX):-len(STAMP_SUFFIX)].strip() or None


def find_stamped_version(text: str) -> str | None:
    """Return the applyr version stamped anywhere in text, or None if none found.

    Unlike stamped_version() (first line only — the contract for the canonical
    `~/.applyr/AGENT_INSTRUCTIONS.md` copy), this scans every line. Instructions
    `setup-agent` injects into a project's own AI config file (CLAUDE.md,
    AGENTS.md, .cursorrules) sit after whatever content already existed there,
    so their stamp is never on line 1. Returns the last match, i.e. the most
    recently injected block, if a file somehow ended up with more than one.
    """
    version = None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(STAMP_PREFIX) and stripped.endswith(STAMP_SUFFIX):
            version = stripped[len(STAMP_PREFIX):-len(STAMP_SUFFIX)].strip() or version
    return version


def with_end_marker(stamped: str) -> str:
    """Close an injected block with END_MARKER so it can be found again later."""
    return f"{stamped.rstrip()}\n{END_MARKER}"


class InjectedBlock(NamedTuple):
    head: str     # user text before the block, without setup-agent's separator
    block: str    # the applyr block itself, stamp through END_MARKER (or EOF)
    tail: str     # user text after END_MARKER, byte for byte
    legacy: bool  # no END_MARKER: written before ADR-016


def split_stamped_block(text: str) -> InjectedBlock:
    """Split text around its last injected applyr block.

    Returns the user's text before the block, the block, the user's text
    after it, and whether the block had no END_MARKER. Blocks from before the marker
    existed are assumed to run to end of file, which is what setup-agent
    always did — but text a user added after such a block cannot be told
    apart from the block itself, so it is lost; the caller warns about that.

    Older applyr blocks left in the head (a file refreshed by a version
    that appended instead of replacing) are removed too, keeping any user
    text between them, so a refresh always leaves exactly one block.
    """
    lines = text.split("\n")
    stamp_index = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(STAMP_PREFIX) and stripped.endswith(STAMP_SUFFIX):
            stamp_index = i
    if stamp_index is None:
        return InjectedBlock(text, "", "", False)

    head = "\n".join(lines[:stamp_index]) + "\n"
    if head.endswith(INJECT_SEPARATOR):
        head = head[:-len(INJECT_SEPARATOR)]
    head = head.rstrip("\n")

    block_and_after = "\n".join(lines[stamp_index:])
    marker_at = block_and_after.find(END_MARKER)
    if marker_at == -1:
        block, tail, legacy = block_and_after, "", True
    else:
        end = marker_at + len(END_MARKER)
        block, tail, legacy = block_and_after[:end], block_and_after[end:], False

    if find_stamped_version(head) is not None:
        older = split_stamped_block(head)
        between = older.tail.strip("\n")
        head = (f"{older.head}{INJECT_SEPARATOR}{between}" if older.head and between
                else older.head or between)
    return InjectedBlock(head, block, tail, legacy)


def foreign_headings(block: str, template: str) -> list[str]:
    """Markdown headings in an injected block that the packaged template lacks.

    A legacy block (no END_MARKER) runs to end of file, so a heading here that
    applyr never wrote is most likely the user's own section, about to be lost.
    """
    known = {line.strip() for line in template.split("\n") if line.startswith("#")}
    return [line.strip() for line in block.split("\n")
            if line.startswith("#") and line.strip() not in known]


def _as_tuple(raw: str) -> tuple[int, ...] | None:
    """Parse a dotted version into comparable integers, or None if it is not one."""
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def is_stale_version(version: str | None) -> bool:
    """True when the given version string predates the installed package.

    A missing or unparsable version is stale by definition. A version from a
    *newer* applyr — the user downgraded — counts as current, because warning
    about the future is noise.
    """
    local = _as_tuple(version or "")
    if local is None:
        return True
    current = _as_tuple(__version__)
    return current is not None and local < current


def is_stale(text: str) -> bool:
    """True when these instructions predate the installed package.

    An unstamped file is stale by definition: every copy written before v0.8.3
    lacks the marker.
    """
    return is_stale_version(stamped_version(text))


_ROLES_DIR = Path(__file__).parent / "templates" / "agents"


def role_names() -> list[str]:
    """Roles with a packaged instruction file, e.g. ["architect", "matcher", ...]."""
    return sorted(p.stem.replace("_", "-") for p in _ROLES_DIR.glob("*.md"))


def role_instructions(name: str) -> str | None:
    """A role's instruction file, or None if there is no such role.

    The main instructions used to point agents at `applyr/templates/agents/
    <role>.md` — a path inside this repository. After `pip install` those files
    live somewhere in site-packages that no agent can guess, so `applyr role`
    serves them instead.
    """
    # Only listed names: the raw name must never become a path — "../x"
    # escaped the roles folder, and "Matcher" worked only on case-insensitive
    # filesystems (macOS) while failing on Linux.
    if name not in role_names():
        return None
    return (_ROLES_DIR / f"{name.replace('-', '_')}.md").read_text(encoding="utf-8")



# `applyr guide` slugs → the exact heading they print (ADR-016). A fixed list on
# purpose: agents hard-code these, so a reworded heading has to fail a test here
# rather than silently break every agent that calls the old slug.
GUIDE_SLUGS: dict[str, str] = {
    "principles": "## Core Principles",
    "roles": "## Agent Roles",
    "privacy": "## Privacy",
    "setup": "## Setup",
    "workflow": "## Workflow",
    "health": "### Step 1 — Health check, then read profile",
    "duplicates": "### Step 2 — Check duplicates",
    "score": "### Step 3 — Evaluate and register (Matcher role)",
    "decide": "### Step 4 — Decide",
    "recruiter": "### Step 5 — Recruiter evaluation (blind)",
    "plan": "### Step 5.5 — CV Tailoring Plan (automatic)",
    "architect": "### Step 5.7 — CV Architect (tailoring strategy)",
    "generate": "### Step 6 — Generate and review CV",
    "verify": "### Step 6b — Verify grounding",
    "deliver": "### Step 7 — Deliver",
    "response-format": "## Agent response format",
    "example": "## Example flow",
    "commands": "## Command reference",
    "errors": "## Error recovery",
    "ats-rules": "## ATS CV rules",
}


def packaged_core() -> str:
    """The short core block setup-agent injects (ADR-016), or "" if missing."""
    src = Path(__file__).parent / "templates" / "AGENT_CORE.md"
    return src.read_text(encoding="utf-8") if src.exists() else ""


def _heading_level(line: str) -> int:
    """Markdown heading level of a line (0 when it is not a heading)."""
    for level in range(1, 7):
        if line.startswith("#" * level + " "):
            return level
    return 0


def guide_section(slug: str) -> str | None:
    """The packaged instructions' section for a guide slug, heading included.

    Runs from the slug's heading to the next heading of the same or a higher
    level. Lines inside fenced code blocks are never headings — a `# comment`
    in a bash example must not end a section early. None when the slug is
    unknown or its heading is missing from the installed template.
    """
    heading = GUIDE_SLUGS.get(slug)
    if heading is None:
        return None
    lines = packaged_instructions().split("\n")
    start, level, in_fence = None, _heading_level(heading), False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if start is None:
            if line.strip() == heading:
                start = i
        elif 0 < _heading_level(line) <= level:
            return "\n".join(lines[start:i]).rstrip() + "\n"
    return None if start is None else "\n".join(lines[start:]).rstrip() + "\n"
