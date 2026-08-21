"""Opt-in PyPI update check — see ADR-010 and specs/pypi-update-check/spec.md.

Every public function here is wrapped so no exception escapes: a bug in this
module must never break `applyr doctor`, which is the only caller.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from applyr.constants import (
    PYPI_UPDATE_CHECK_URL,
    UPDATE_CHECK_CACHE_TTL_HOURS,
    UPDATE_CHECK_TIMEOUT_SECONDS,
)


def _as_tuple(raw: str) -> tuple[int, ...] | None:
    """Parse a dotted version into comparable integers, or None if it is not one."""
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return None


def _cache_path(applyr_dir: Path) -> Path:
    return applyr_dir / "update_check.json"


def _read_cache(applyr_dir: Path) -> dict | None:
    """Return the cached entry if present and younger than the TTL, else None."""
    try:
        raw = _cache_path(applyr_dir).read_text()
        cached = json.loads(raw)
        checked_at = datetime.fromisoformat(cached["checked_at"])
        age_hours = (datetime.now(timezone.utc) - checked_at).total_seconds() / 3600
        if age_hours >= UPDATE_CHECK_CACHE_TTL_HOURS:
            return None
        return cached
    except Exception:
        return None


def _write_cache(applyr_dir: Path, latest_version: str | None) -> None:
    entry = {"checked_at": datetime.now(timezone.utc).isoformat()}
    if latest_version is not None:
        entry["latest_version"] = latest_version
    try:
        _cache_path(applyr_dir).write_text(json.dumps(entry))
    except Exception:
        pass


def _fetch_latest_version() -> str | None:
    """One GET to PyPI's public JSON API. Returns None on any failure."""
    try:
        with urllib.request.urlopen(
            PYPI_UPDATE_CHECK_URL, timeout=UPDATE_CHECK_TIMEOUT_SECONDS
        ) as response:
            data = json.loads(response.read())
        return data["info"]["version"]
    except (URLError, TimeoutError, ValueError, KeyError, OSError):
        return None


def check_for_update(applyr_dir: Path, installed_version: str) -> str | None:
    """Return the latest version string if newer than installed, else None.

    Reads the 24h cache first; only hits the network on a miss/expiry. Never
    raises — any failure (network, cache, parse) silently yields None.
    """
    try:
        cached = _read_cache(applyr_dir)
        if cached is not None:
            latest = cached.get("latest_version")
        else:
            latest = _fetch_latest_version()
            _write_cache(applyr_dir, latest)

        if latest is None:
            return None

        installed_tuple = _as_tuple(installed_version)
        latest_tuple = _as_tuple(latest)
        if installed_tuple is None or latest_tuple is None:
            return None
        return latest if installed_tuple < latest_tuple else None
    except Exception:
        return None
