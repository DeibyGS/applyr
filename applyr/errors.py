"""Error output — everything here goes to stderr, never stdout.

stdout carries data (tables, JSON) and is what agents parse. Mixing error text
into it turns a --json payload into a parse error. See docs/adr/006-errors-to-stderr.md
"""

import sys
from typing import NoReturn


def error(message: str) -> None:
    """Print an error message to stderr without exiting."""
    print(message, file=sys.stderr)


def warn(message: str) -> None:
    """Print a warning to stderr. Warnings are not data — they never go to stdout."""
    error(message)


def die(message: str, code: int = 1) -> NoReturn:
    """Print an error message to stderr and exit with the given code."""
    error(message)
    sys.exit(code)
