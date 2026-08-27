"""Terminal color support via colorama with NO_COLOR / --no-color respect."""

import os
from dataclasses import dataclass

from colorama import Fore, Style, init as colorama_init

_enabled = True


@dataclass
class StatusDisplay:
    """Unified status display configuration."""
    key: str
    label: str
    color_key: str
    icon: str


# Semantic color palette — single source of truth for all colored output
SEMANTIC_COLORS = {
    "primary": Fore.CYAN,
    "secondary": Fore.BLUE,
    "success": Fore.GREEN,
    "warning": Fore.YELLOW,
    "error": Fore.RED,
    "info": Fore.CYAN,
    "muted": Style.DIM + Fore.WHITE,
    "dim": Style.DIM,
    "bold": Style.BRIGHT,
    "reset": Style.RESET_ALL,
}

# Status display mapping — single source of truth for all status rendering
STATUS_DISPLAYS = {
    "pending": StatusDisplay("pending", "Pending", "muted", "○"),
    "applied": StatusDisplay("applied", "Applied", "info", "→"),
    "waiting": StatusDisplay("waiting", "Waiting", "warning", "⏳"),
    "in_process": StatusDisplay("in_process", "In Process", "info", "▶"),
    "offer": StatusDisplay("offer", "Offer", "success", "★"),
    "rejected": StatusDisplay("rejected", "Rejected", "error", "✕"),
    "discarded": StatusDisplay("discarded", "Discarded", "dim", "⟳"),
}


def init_colors(no_color: bool = False) -> None:
    """Initialize colorama. Disable if --no-color flag or NO_COLOR env is set."""
    global _enabled
    _enabled = not no_color and not os.environ.get("NO_COLOR", "")
    colorama_init(autoreset=_enabled, strip=not _enabled)


def is_enabled() -> bool:
    """Check if colors are currently enabled."""
    return _enabled


def color(text: str, style: str) -> str:
    """Apply a named color style to text. Returns plain text if colors disabled."""
    if not _enabled:
        return str(text)
    prefix = SEMANTIC_COLORS.get(style, "")
    return f"{prefix}{text}{Style.RESET_ALL}" if prefix else str(text)


def get_semantic_color(key: str) -> str:
    """Get color prefix for semantic color key. Returns empty string if disabled."""
    if not _enabled:
        return ""
    return SEMANTIC_COLORS.get(key, "")


def get_status_display(status_key: str) -> StatusDisplay:
    """Get StatusDisplay for a status key. Falls back to generic."""
    return STATUS_DISPLAYS.get(status_key, StatusDisplay(status_key, status_key.title(), "muted", "?"))


def get_status_color(status_key: str) -> str:
    """Get color prefix for a status key. Returns empty string if disabled."""
    display = get_status_display(status_key)
    return get_semantic_color(display.color_key)


def get_status_label(status_key: str) -> str:
    """Get human-readable label for a status key."""
    return get_status_display(status_key).label


def get_status_icon(status_key: str) -> str:
    """Get icon for a status key."""
    return get_status_display(status_key).icon


def colorize_status(status_key: str) -> str:
    """Return colored status label (or plain if colors disabled)."""
    display = get_status_display(status_key)
    if not _enabled:
        return display.label
    color_prefix = get_semantic_color(display.color_key)
    return f"{color_prefix}{display.label}{Style.RESET_ALL}"