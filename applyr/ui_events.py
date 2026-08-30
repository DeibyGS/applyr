"""Best-effort notification to the Visual UI backend of real agent events.

This module provides the single shared call site for all CLI commands to emit
granular agent lifecycle events to the Visual UI backend. It must never affect
the calling command's success, exit code, or output — the CLI's stability and
agent-operability outrank this visualization feature. Uses the standard library
only (urllib), matching ADR-005's "single CLI on stdlib, one dependency".
"""

import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from applyr.db import VALID_PIPELINE_STAGES

# Matches `applyr ui`'s default port. No port-discovery mechanism — a UI
# backend running on a non-default port simply never receives these events.
# Accepted limitation, not a bug (spec's "Out of scope").
DEFAULT_UI_PORT = 8000

# Bounds each notification attempt so a hung or slow UI backend can never
# meaningfully delay the CLI command that triggered it.
TIMEOUT_SECONDS = 0.2

# Valid agent IDs for event emission
VALID_AGENT_IDS = {"recruiter", "matching", "cv", "ats", "application"}

# Valid agent visual states
VALID_AGENT_STATES = {
    "idle",
    "receiving",
    "working",
    "handoff",
    "walking",
    "waiting",
    "blocked",
    "completed",
    "error",
}

# Valid event types
VALID_EVENT_TYPES = {
    "agent.started",
    "agent.command",
    "agent.output",
    "agent.completed",
    "agent.failed",
    "agent.waiting",
    "agent.blocked",
    "agent.receiving",
    "handoff.started",
    "handoff.walking",
    "handoff.completed",
    "pipeline.stage",
    "user.response",
}


def _post_event(
    endpoint: str, payload: dict[str, Any], port: int | None = None
) -> None:
    """Internal: POST JSON payload to UI backend endpoint with timeout."""
    if port is None:
        port = DEFAULT_UI_PORT

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{endpoint}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
    except Exception:
        # Deliberately broad: any transport-layer failure must be swallowed.
        # This function's entire contract is "never raise".
        pass


def notify_stage(offer_id: int, stage: str, port: int | None = None) -> None:
    """Best-effort notification that `offer_id` entered `stage` (legacy).

    Kept for backward compatibility with existing call sites.
    """
    if stage not in VALID_PIPELINE_STAGES:
        return
    _post_event(
        "/api/internal/pipeline-stage",
        {"offer_id": offer_id, "stage": stage},
        port,
    )


def notify_event(
    event_type: str,
    agent_id: str,
    *,
    offer_id: int | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    port: int | None = None,
) -> None:
    """Best-effort, non-blocking emission of a granular agent event.

    Args:
        event_type: One of VALID_EVENT_TYPES (e.g., "agent.started", "handoff.completed").
        agent_id: The agent emitting the event (one of VALID_AGENT_IDS).
        offer_id: Optional offer ID this event relates to.
        payload: Event-specific data (command, output, artifact, error, etc.).
        correlation_id: Optional ID linking related events (e.g., handoff chain).
        port: UI backend port (defaults to DEFAULT_UI_PORT).

    Never raises. Any failure is swallowed silently.
    """
    if event_type not in VALID_EVENT_TYPES:
        return
    if agent_id not in VALID_AGENT_IDS:
        return

    event_payload = {
        "type": event_type,
        "agent_id": agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }
    if offer_id is not None:
        event_payload["offer_id"] = offer_id
    if payload is not None:
        event_payload["payload"] = payload

    _post_event("/api/internal/agent-event", event_payload, port)


# Convenience helpers for common event patterns
def notify_agent_started(
    agent_id: str, task: str, command: str | None = None, **kwargs
) -> None:
    notify_event(
        "agent.started",
        agent_id,
        payload={"task": task, "command": command},
        **kwargs,
    )


def notify_agent_command(agent_id: str, command: str, args: list[str], **kwargs) -> None:
    notify_event(
        "agent.command",
        agent_id,
        payload={"command": command, "args": args},
        **kwargs,
    )


def notify_agent_output(
    agent_id: str, stdout: str, stderr: str | None = None, **kwargs
) -> None:
    notify_event(
        "agent.output",
        agent_id,
        payload={"stdout": stdout, "stderr": stderr},
        **kwargs,
    )


def notify_agent_completed(
    agent_id: str,
    artifact: dict[str, Any],
    output_summary: str,
    **kwargs,
) -> None:
    notify_event(
        "agent.completed",
        agent_id,
        payload={"artifact": artifact, "output_summary": output_summary},
        **kwargs,
    )


def notify_agent_failed(agent_id: str, error: str, recoverable: bool = True, **kwargs) -> None:
    notify_event(
        "agent.failed",
        agent_id,
        payload={"error": error, "recoverable": recoverable},
        **kwargs,
    )


def notify_agent_waiting(agent_id: str, reason: str, **kwargs) -> None:
    notify_event("agent.waiting", agent_id, payload={"reason": reason}, **kwargs)


def notify_agent_blocked(
    agent_id: str, reason: str, blocked_by: str | None = None, **kwargs
) -> None:
    notify_event(
        "agent.blocked",
        agent_id,
        payload={"reason": reason, "blocked_by": blocked_by},
        **kwargs,
    )


def notify_handoff_started(
    from_agent: str, to_agent: str, artifact: dict[str, Any], **kwargs
) -> None:
    correlation_id = kwargs.pop("correlation_id", None) or str(uuid.uuid4())
    notify_event(
        "handoff.started",
        from_agent,
        payload={"from_agent": from_agent, "to_agent": to_agent, "artifact": artifact},
        correlation_id=correlation_id,
        **kwargs,
    )
    # Also emit receiving event for target agent
    notify_event(
        "agent.receiving",
        to_agent,
        payload={"artifact": artifact, "from_agent": from_agent},
        correlation_id=correlation_id,
        **kwargs,
    )


def notify_handoff_walking(
    from_agent: str, to_agent: str, progress: float, **kwargs
) -> None:
    notify_event(
        "handoff.walking",
        from_agent,
        payload={"from_agent": from_agent, "to_agent": to_agent, "progress": progress},
        **kwargs,
    )


def notify_handoff_completed(
    from_agent: str, to_agent: str, artifact: dict[str, Any], **kwargs
) -> None:
    correlation_id = kwargs.pop("correlation_id", None)
    notify_event(
        "handoff.completed",
        from_agent,
        payload={"from_agent": from_agent, "to_agent": to_agent, "artifact": artifact},
        correlation_id=correlation_id,
        **kwargs,
    )
    notify_event(
        "agent.completed",
        to_agent,
        payload={"artifact": artifact, "output_summary": f"Received from {from_agent}"},
        correlation_id=correlation_id,
        **kwargs,
    )
