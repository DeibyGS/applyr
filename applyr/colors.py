"""Terminal color support via colorama with NO_COLOR / --no-color respect."""

import os

from colorama import Fore, Style, init as colorama_init

_enabled = True


def init_colors(no_color: bool = False) -> None:
    """Initialize colorama. Disable if --no-color flag or NO_COLOR env is set."""
    global _enabled
    _enabled = not no_color and not os.environ.get("NO_COLOR", "")
    colorama_init(autoreset=_enabled, strip=not _enabled)


def color(text: str, style: str) -> str:
    """Apply a named color style to text. Returns plain text if colors disabled."""
    if not _enabled:
        return str(text)
    styles = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "cyan": Fore.CYAN,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "white": Fore.WHITE,
        "dim": Style.DIM,
        "bold": Style.BRIGHT,
        "reset": Style.RESET_ALL,
    }
    prefix = styles.get(style, "")
    return f"{prefix}{text}{Style.RESET_ALL}" if prefix else str(text)


def is_enabled() -> bool:
    """Check if colors are currently enabled."""
    return _enabled
