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


def _classify_topic(score: int) -> str:
    """Classify a topic score into Strong/Partial/Missing.

    Returns:
        "strong" if score >= 80, "partial" if 50-79, "missing" if < 50
    """
    if score >= 80:
        return "strong"
    elif score >= 50:
        return "partial"
    else:
        return "missing"


def _classify_icon(classification: str) -> str:
    """Get icon for classification."""
    icons = {
        "strong": "✓",
        "partial": "△",
        "missing": "✕",
    }
    return icons.get(classification, "?")
