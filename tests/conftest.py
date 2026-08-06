"""Shared fixtures for applyr tests."""

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
