"""Shared fixtures for applyr tests."""

import http.server
import socket
import sys
import threading
import time
import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def tmp_applyr(tmp_path, monkeypatch):
    """Set up an isolated ~/.applyr/ environment for testing.

    Returns the applyr home directory path.
    """
    applyr_home = tmp_path / ".applyr"
    applyr_home.mkdir()
    monkeypatch.setenv("APPLYR_HOME", str(applyr_home))

    # Force config module to use the tmp path
    import applyr.config as cfg
    monkeypatch.setattr(cfg, "APPLYR_DIR", applyr_home)
    # CV_HOME defaults outside APPLYR_DIR in production; tests keep it inside
    # the same sandbox so nothing escapes tmp_path.
    monkeypatch.setattr(cfg, "CV_HOME", applyr_home)

    return applyr_home


@pytest.fixture
def tmp_db(tmp_applyr):
    """Create an initialized database in the tmp applyr home.

    Returns the database file path as string.
    """
    from applyr.db import init_db
    db_path = str(tmp_applyr / "jobs.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def run_cli(tmp_applyr, monkeypatch):
    """Run cli.main() with patched sys.argv and isolated APPLYR_HOME.

    Returns a callable: run_cli(["command", "arg1", ...]) -> None
    Raises SystemExit on die() calls.
    """
    import applyr.commands.core as core_mod
    import applyr.commands.workflow as workflow_mod
    import applyr.cv as cv_mod

    # Patch APPLYR_DIR in modules that have it
    for mod in (core_mod, workflow_mod, cv_mod):
        monkeypatch.setattr(mod, "APPLYR_DIR", tmp_applyr)

    def _run(args: list[str]):
        monkeypatch.setattr(sys, "argv", ["applyr"] + args)
        from applyr.cli import main
        main()

    return _run


def _free_port() -> int:
    """Ask the OS for a port, then release it immediately — good enough for
    a 'nothing is listening here' target in a connection-refused test."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def free_port() -> int:
    return _free_port()


class _HangingHandler(http.server.BaseHTTPRequestHandler):
    """Accepts the connection, then never responds — simulates a stuck UI
    backend. 1s comfortably clears notify_stage's 0.2s client-side timeout
    (proving the client doesn't wait for the server) without making every
    test that uses this fixture pay for a longer sleep: HTTPServer.shutdown()
    can't interrupt an in-flight handler, so teardown blocks for however
    long this sleep runs."""

    def do_POST(self):  # noqa: N802 (stdlib method name)
        time.sleep(1)

    def log_message(self, *args):  # silence stdlib's default stderr logging
        pass


@pytest.fixture
def hanging_server():
    """A local HTTP server that accepts connections but never replies —
    used by both tests/test_ui_events.py (notify_stage's own timeout
    contract) and tests/test_pipeline_stage_instrumentation.py (the 5 CLI
    commands built on top of it) to prove neither ever blocks on a stuck UI
    backend (ADR-013)."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _HangingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture(autouse=True)
def reset_json_mode():
    """Keep `applyr.errors._json_mode` from leaking between tests.

    `cli.py` flips that module-level flag on every `--json` invocation and
    nothing turns it back off. In JSON mode `error()` suppresses output by
    design, so a single test running a `--json` command silenced stderr for
    every test that ran after it — and the suite's result depended on
    collection order. Reset around each test.
    """
    from applyr import errors

    errors.set_json_mode(False)
    yield
    errors.set_json_mode(False)


@pytest.fixture(autouse=True)
def mock_tty():
    """Mock TTY for color tests - enables colors in test environment."""
    with patch.object(sys.stdout, 'isatty', return_value=True):
        with patch('shutil.get_terminal_size', return_value=(80, 24)):
            yield