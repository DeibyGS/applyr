"""Shared helpers used across multiple commands modules."""

from datetime import date

from applyr.constants import PROGRESS_BAR_WIDTH


def _today() -> str:
    """Return today's date as ISO string."""
    return date.today().isoformat()


def _bar(score: int, width: int = PROGRESS_BAR_WIDTH) -> str:
    """Render a simple ASCII progress bar for a 0-100 score."""
    filled = round(score * width / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate a string to max_len characters, appending ellipsis if needed."""
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
