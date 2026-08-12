"""Shared fixtures for applyr tests."""

import sys
import pytest
from pathlib import Path


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
