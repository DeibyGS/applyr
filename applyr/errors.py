"""Error output — everything here goes to stderr, never stdout.

stdout carries data and is what agents parse. Mixing error text into it turns a
--json payload into a parse error. See docs/adr/006-errors-to-stderr.md

In --json mode errors are emitted as a single JSON object on stderr, so agents
can branch on a stable `code` instead of matching English prose. See
docs/adr/007-structured-json-errors.md
"""

import json
import sys
from typing import Any, NoReturn

# Process-wide output mode, set once by cli.py — same pattern as colors.py.
# Threading an as_json flag through 38 call sites is noise, and the 39th
# written later would silently emit text in JSON mode.
_json_mode = False


def set_json_mode(enabled: bool) -> None:
    """Switch error output between human text and JSON objects."""
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    """Whether errors are currently emitted as JSON."""
    return _json_mode


def error(message: str) -> None:
    """Print an error message to stderr without exiting.

    In JSON mode this is suppressed: a partial message is not a valid object,
    and the terminating die() emits the complete one. Callers that print an
    error followed by hint lines therefore stay correct in both modes.
    """
    if _json_mode:
        return
    print(message, file=sys.stderr)


def warn(message: str) -> None:
    """Print a warning to stderr. Warnings are not data — they never go to stdout."""
    error(message)


def die(
    message: str,
    code: str = "error",
    details: dict[str, Any] | None = None,
    text: str | None = None,
    exit_code: int = 1,
) -> NoReturn:
    """Report a fatal error on stderr and exit.

    In JSON mode emits {"error": {"code", "message", "details"}}; otherwise the
    plain message. `code` is a stable identifier and part of the public
    contract — see docs/contracts.md. `message` wording is not.

    `text` overrides what humans see, for call sites where preceding error()
    lines already supplied the context that `message` restates for JSON.
    """
    if _json_mode:
        # "Error: " is redundant next to a `code` field — strip it from the
        # machine-readable message while leaving the human text untouched.
        clean = message.strip()
        if clean.startswith("Error: "):
            clean = clean[len("Error: "):]
        payload: dict[str, Any] = {"code": code, "message": clean}
        if details:
            payload["details"] = details
        print(json.dumps({"error": payload}, ensure_ascii=False), file=sys.stderr)
    elif text != "":
        # An empty `text` means the caller already printed everything a human
        # needs via error(), and only the JSON payload is still missing.
        print(text if text is not None else message, file=sys.stderr)
    sys.exit(exit_code)
