"""Best-effort notification to the Visual UI backend of a real pipeline-stage
transition (ADR-013).

This is the one shared call site every CLI command in
specs/visual-ui-applyr-world-phase2/spec.md's AC-02 goes through. It must
never affect the calling command's success, exit code, or output — see
docs/adr/013-applyr-world-movement-and-push-transport.md's non-negotiable
constraint: the CLI's stability and agent-operability outrank this
visualization feature. Uses the standard library only (urllib), matching
ADR-005's "single CLI on stdlib, one dependency" — this is not a case that
justifies adding `requests`.
"""

import json
import urllib.error
import urllib.request

from applyr.db import VALID_PIPELINE_STAGES

# Matches `applyr ui`'s default port. No port-discovery mechanism — a UI
# backend running on a non-default port simply never receives these events.
# Accepted limitation, not a bug (spec's "Out of scope").
DEFAULT_UI_PORT = 8000

# Bounds each notification attempt so a hung or slow UI backend can never
# meaningfully delay the CLI command that triggered it.
TIMEOUT_SECONDS = 0.2


def notify_stage(offer_id: int, stage: str, port: int | None = None) -> None:
    """Best-effort, non-blocking notification that `offer_id` entered `stage`.

    Never raises. Any failure — UI backend not running (the common case),
    connection refused, timeout, or a malformed response — is swallowed
    silently. Printing a warning on every CLI invocation would be noise: the
    common case (no UI backend running) is not an error condition for CLI
    usage, only for this optional visualization.

    `port` defaults to the module-level DEFAULT_UI_PORT, looked up here
    rather than bound as the parameter's default value — a default value is
    evaluated once at import time, which would make DEFAULT_UI_PORT
    unpatchable by tests for the 5 real call sites (core.py, cv.py) that
    never pass `port` explicitly.
    """
    if stage not in VALID_PIPELINE_STAGES:
        return
    if port is None:
        port = DEFAULT_UI_PORT

    body = json.dumps({"offer_id": offer_id, "stage": stage}).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/internal/pipeline-stage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
    except Exception:
        # Deliberately broad: any transport-layer failure (connection
        # refused, timeout, DNS, malformed response) must be swallowed the
        # same way — this function's entire contract is "never raise".
        # `Exception` (not `BaseException`) still lets KeyboardInterrupt /
        # SystemExit propagate, which is correct.
        pass
