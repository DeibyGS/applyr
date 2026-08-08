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


def _as_tuple(raw: str) -> tuple[int, ...] | None:
    """Parse a dotted version into comparable integers, or None if it is not one."""
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def is_stale(text: str) -> bool:
    """True when these instructions predate the installed package.

    An unstamped file is stale by definition: every copy written before v0.8.3
    lacks the marker. A stamp from a *newer* applyr — the user downgraded —
    counts as current, because warning about the future is noise.
    """
    local = _as_tuple(stamped_version(text) or "")
    if local is None:
        return True
    current = _as_tuple(__version__)
    return current is not None and local < current
