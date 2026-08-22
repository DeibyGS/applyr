"""Tests for `applyr ui` — the CLI entry point in cli.py.

Never actually starts uvicorn (it blocks forever): `applyr.ui.server.run` is
monkeypatched in every test here, either to record its call or to simulate
the `[ui]` extra not being installed.
"""

import json

import pytest


@pytest.mark.unit
class TestUiCommand:

    def test_starts_server_on_default_port(self, tmp_db, run_cli, monkeypatch):
        calls = []
        import applyr.ui.server as server_mod
        monkeypatch.setattr(server_mod, "run", lambda **kwargs: calls.append(kwargs))

        run_cli(["ui"])

        assert calls == [{"port": 8000}]

    def test_respects_port_flag(self, tmp_db, run_cli, monkeypatch):
        calls = []
        import applyr.ui.server as server_mod
        monkeypatch.setattr(server_mod, "run", lambda **kwargs: calls.append(kwargs))

        run_cli(["ui", "--port", "9999"])

        assert calls == [{"port": 9999}]

    def test_no_host_override_is_exposed(self, tmp_db, run_cli, monkeypatch):
        """Security NFR: binding beyond loopback would expose an
        unauthenticated API over real personal data. There must be no flag
        for it."""
        calls = []
        import applyr.ui.server as server_mod
        monkeypatch.setattr(server_mod, "run", lambda **kwargs: calls.append(kwargs))

        run_cli(["ui"])

        assert "host" not in calls[0]

    def test_missing_ui_extra_prints_clean_error_not_a_traceback(self, tmp_db, run_cli, monkeypatch, capsys):
        import applyr.ui.server as server_mod

        def _raise_missing_uvicorn(**kwargs):
            raise ImportError("No module named 'uvicorn'")

        monkeypatch.setattr(server_mod, "run", _raise_missing_uvicorn)

        with pytest.raises(SystemExit) as exc_info:
            run_cli(["ui"])

        assert exc_info.value.code != 0
        stderr = capsys.readouterr().err
        assert "pip install applyr[ui]" in stderr
        assert "Traceback" not in stderr

    def test_missing_ui_extra_json_mode_has_structured_error(self, tmp_db, run_cli, monkeypatch, capsys):
        import applyr.ui.server as server_mod
        monkeypatch.setattr(server_mod, "run", lambda **kwargs: (_ for _ in ()).throw(ImportError()))

        with pytest.raises(SystemExit):
            run_cli(["--json", "ui"])

        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "missing_dependency"

    def test_importing_cli_does_not_require_fastapi(self, monkeypatch):
        """The module-level guarantee this whole slice depends on (ADR-005/011):
        `import applyr.cli` must succeed even if fastapi/uvicorn were never
        installed. Simulated by hiding them from sys.modules and forcing a
        fresh import of applyr.cli beneath that block."""
        import sys
        import importlib

        for mod_name in list(sys.modules):
            if mod_name == "fastapi" or mod_name.startswith("fastapi.") or mod_name == "uvicorn":
                monkeypatch.delitem(sys.modules, mod_name, raising=False)
        monkeypatch.setitem(sys.modules, "fastapi", None)
        monkeypatch.setitem(sys.modules, "uvicorn", None)

        import applyr.cli as cli_mod
        importlib.reload(cli_mod)
        importlib.reload(cli_mod)  # must not raise either time
