"""notify_stage must never affect the calling CLI command — see
docs/adr/013-applyr-world-movement-and-push-transport.md and
specs/visual-ui-applyr-world-phase2/spec.md's non-blocking instrumentation
contract. Every test here proves a different way the notification can fail
without notify_stage raising or taking meaningfully long."""

import http.server
import json
import threading
import time

import pytest

from applyr.ui_events import notify_stage, TIMEOUT_SECONDS


class _CapturingHandler(http.server.BaseHTTPRequestHandler):
    """Records the last request body it received, then replies 204."""

    received: list[bytes] = []

    def do_POST(self):  # noqa: N802 (stdlib method name)
        length = int(self.headers.get("Content-Length", 0))
        self.__class__.received.append(self.rfile.read(length))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):  # silence stdlib's default stderr logging
        pass


@pytest.fixture
def capturing_server():
    _CapturingHandler.received = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        thread.join()


class TestNotifyStageSuccess:
    def test_posts_offer_id_and_stage_as_json(self, capturing_server):
        notify_stage(248, "cv", port=capturing_server)
        time.sleep(0.05)  # let the handler thread record the request
        assert len(_CapturingHandler.received) == 1
        assert json.loads(_CapturingHandler.received[0]) == {"offer_id": 248, "stage": "cv"}


class TestNotifyStageNeverRaises:
    def test_connection_refused_is_swallowed(self, free_port):
        notify_stage(248, "matching", port=free_port)  # must not raise

    def test_timeout_is_swallowed_and_bounded(self, hanging_server):
        start = time.monotonic()
        notify_stage(248, "ats", port=hanging_server)  # must not raise
        elapsed = time.monotonic() - start
        # Generous multiplier over TIMEOUT_SECONDS to absorb CI/scheduler
        # jitter without the test becoming meaningless.
        assert elapsed < TIMEOUT_SECONDS * 10

    def test_invalid_stage_is_a_silent_no_op(self, free_port):
        # No server at all needed — an invalid stage must never even attempt
        # a network call.
        notify_stage(248, "not-a-real-stage", port=free_port)


class TestNotifyStagePrintsNothingOnFailure:
    """The spec's own words: 'silent by design, since the common case (UI
    backend not running) is not an error condition for CLI usage.' A
    warning on every CLI invocation without a UI backend running — the
    common case — would be pure noise."""

    def test_connection_refused_prints_nothing(self, free_port, capsys):
        notify_stage(248, "matching", port=free_port)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_timeout_prints_nothing(self, hanging_server, capsys):
        notify_stage(248, "ats", port=hanging_server)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""
