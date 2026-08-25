"""Tests for ui_events.py — granular event emission."""

import json
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from applyr.ui_events import (
    notify_stage,
    notify_event,
    notify_agent_started,
    notify_agent_completed,
    notify_agent_failed,
    notify_agent_output,
    notify_agent_waiting,
    notify_agent_blocked,
    notify_handoff_started,
    notify_handoff_walking,
    notify_handoff_completed,
    DEFAULT_UI_PORT,
    TIMEOUT_SECONDS,
    VALID_EVENT_TYPES,
    VALID_AGENT_IDS,
)


class TestNotifyStage:
    """Legacy notify_stage should still work."""

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_stage_valid(self, mock_urlopen):
        notify_stage(42, "matching")
        mock_urlopen.assert_called_once()
        args, _ = mock_urlopen.call_args
        request = args[0]
        assert request.full_url == f"http://127.0.0.1:{DEFAULT_UI_PORT}/api/internal/pipeline-stage"
        payload = json.loads(request.data.decode())
        assert payload == {"offer_id": 42, "stage": "matching"}

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_stage_invalid_stage_ignored(self, mock_urlopen):
        notify_stage(42, "not-a-real-stage")
        mock_urlopen.assert_not_called()

    @patch("applyr.ui_events.urllib.request.urlopen", side_effect=Exception("connection refused"))
    def test_notify_stage_swallows_errors(self, mock_urlopen):
        # Should not raise
        notify_stage(42, "matching")


class TestNotifyEvent:
    """Granular notify_event with all event types."""

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_event_basic(self, mock_urlopen):
        notify_event("agent.started", "recruiter", offer_id=1, payload={"task": "test"})
        mock_urlopen.assert_called_once()
        args, _ = mock_urlopen.call_args
        request = args[0]
        assert request.full_url == f"http://127.0.0.1:{DEFAULT_UI_PORT}/api/internal/agent-event"
        payload = json.loads(request.data.decode())
        assert payload["type"] == "agent.started"
        assert payload["agent_id"] == "recruiter"
        assert payload["offer_id"] == 1
        assert payload["payload"] == {"task": "test"}
        assert "timestamp" in payload
        assert "correlation_id" in payload

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_event_generates_correlation_id(self, mock_urlopen):
        notify_event("agent.started", "recruiter")
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        # Should be a valid UUID
        import uuid
        uuid.UUID(payload["correlation_id"])

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_event_invalid_type_ignored(self, mock_urlopen):
        notify_event("invalid.type", "recruiter")
        mock_urlopen.assert_not_called()

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_event_invalid_agent_ignored(self, mock_urlopen):
        notify_event("agent.started", "invalid-agent")
        mock_urlopen.assert_not_called()

    @patch("applyr.ui_events.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_notify_event_swallows_errors(self, mock_urlopen):
        notify_event("agent.started", "recruiter")


class TestConvenienceHelpers:
    """Test the convenience helper functions."""

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_started(self, mock_urlopen):
        notify_agent_started("recruiter", "Analyzing offer", command="applyr add", offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.started"
        assert payload["payload"]["task"] == "Analyzing offer"
        assert payload["payload"]["command"] == "applyr add"

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_completed(self, mock_urlopen):
        artifact = {"type": "job_offer", "title": "Dev", "company": "Acme", "offerId": 1}
        notify_agent_completed("recruiter", artifact, "Offer parsed", offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.completed"
        assert payload["payload"]["artifact"] == artifact
        assert payload["payload"]["output_summary"] == "Offer parsed"

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_failed(self, mock_urlopen):
        notify_agent_failed("recruiter", "Connection timeout", recoverable=True, offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.failed"
        assert payload["payload"]["error"] == "Connection timeout"
        assert payload["payload"]["recoverable"] is True

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_output(self, mock_urlopen):
        notify_agent_output("recruiter", "stdout content", stderr="stderr content", offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.output"
        assert payload["payload"]["stdout"] == "stdout content"
        assert payload["payload"]["stderr"] == "stderr content"

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_waiting(self, mock_urlopen):
        notify_agent_waiting("recruiter", "Waiting for upstream", offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.waiting"
        assert payload["payload"]["reason"] == "Waiting for upstream"

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_agent_blocked(self, mock_urlopen):
        notify_agent_blocked("recruiter", "Downstream full", blocked_by="cv", offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "agent.blocked"
        assert payload["payload"]["reason"] == "Downstream full"
        assert payload["payload"]["blocked_by"] == "cv"

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_handoff_started(self, mock_urlopen):
        artifact = {"type": "job_offer", "title": "Dev", "company": "Acme", "offerId": 1}
        notify_handoff_started("recruiter", "matching", artifact, offer_id=1)
        # Should emit two events: handoff.started and agent.receiving
        assert mock_urlopen.call_count == 2

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_handoff_walking(self, mock_urlopen):
        notify_handoff_walking("recruiter", "matching", 0.5, offer_id=1)
        args, _ = mock_urlopen.call_args
        payload = json.loads(args[0].data.decode())
        assert payload["type"] == "handoff.walking"
        assert payload["payload"]["progress"] == 0.5

    @patch("applyr.ui_events.urllib.request.urlopen")
    def test_notify_handoff_completed(self, mock_urlopen):
        artifact = {"type": "job_offer", "title": "Dev", "company": "Acme", "offerId": 1}
        notify_handoff_completed("recruiter", "matching", artifact, offer_id=1)
        # Should emit two events: handoff.completed and agent.completed for receiver
        assert mock_urlopen.call_count == 2


class TestConstants:
    """Verify constants are correct."""

    def test_default_port(self):
        assert DEFAULT_UI_PORT == 8000

    def test_timeout_seconds(self):
        assert TIMEOUT_SECONDS == 0.2

    def test_valid_event_types(self):
        expected = {
            "agent.started", "agent.command", "agent.output", "agent.completed",
            "agent.failed", "agent.waiting", "agent.blocked", "agent.receiving",
            "handoff.started", "handoff.walking", "handoff.completed", "pipeline.stage",
        }
        assert VALID_EVENT_TYPES == expected

    def test_valid_agent_ids(self):
        expected = {"recruiter", "matching", "cv", "ats", "application"}
        assert VALID_AGENT_IDS == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])