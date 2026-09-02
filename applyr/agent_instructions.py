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

from applyr import __version__

STAMP_PREFIX = "<!-- applyr-version:"
STAMP_SUFFIX = "-->"

# What setup-agent puts between a target file's existing content and the block
# it injects. Shared here so the block can be found and replaced later, not
# just appended after.
INJECT_SEPARATOR = "\n\n---\n\n"

# Written only when the packaged template cannot be found — a pointer, not
# instructions. It carries no stamp, so it reads as stale and gets replaced by
# the real thing as soon as one is available.
FALLBACK = (
    "# applyr — Agent Instructions\n\n"
    "Download the full instructions from:\n"
    "https://github.com/DeibyGS/applyr/blob/main/templates/AGENT_INSTRUCTIONS.md\n"
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


def strip_stamped_block(text: str) -> str:
    """Return text with its last stamped applyr block, and the separator
    before it, removed — leaving only what came before setup-agent injected
    it.

    setup-agent always appends its block as the very last thing in a target
    file, right after INJECT_SEPARATOR (see cmd_setup_agent), so the last
    stamp line marks exactly where the user's own content ends. Used to
    replace a stale block in place on `--force` instead of leaving it behind
    and appending another copy after it — which would otherwise accumulate
    one stale block per applyr upgrade a user ever ran --force for.
    """
    lines = text.split("\n")
    stamp_index = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(STAMP_PREFIX) and stripped.endswith(STAMP_SUFFIX):
            stamp_index = i
    if stamp_index is None:
        return text
    head = "\n".join(lines[:stamp_index]) + "\n"
    if head.endswith(INJECT_SEPARATOR):
        head = head[:-len(INJECT_SEPARATOR)]
    return head.rstrip("\n")


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
