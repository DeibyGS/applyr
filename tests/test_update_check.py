"""Tests for the opt-in PyPI update check — see ADR-010.

`check_for_update` is the only network-call code path in applyr. It must
never raise, must respect the 24h cache, and must never surprise a user who
never opted in — that last property is covered by test_doctor.py instead,
since it depends on config wiring, not this module alone.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from applyr.update_check import check_for_update, _as_tuple


@pytest.fixture
def cache_file(tmp_applyr):
    return tmp_applyr / "update_check.json"


def _write_cache(path, latest_version=None, age_hours=1):
    checked_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    entry = {"checked_at": checked_at.isoformat()}
    if latest_version is not None:
        entry["latest_version"] = latest_version
    path.write_text(json.dumps(entry))


class TestVersionComparison:
    def test_parses_dotted_version(self):
        assert _as_tuple("1.9.0") == (1, 9, 0)

    def test_non_numeric_segment_returns_none(self):
        assert _as_tuple("1.9.0rc1") is None


class TestCacheHit:
    def test_fresh_cache_is_used_without_network_call(self, tmp_applyr, cache_file, monkeypatch):
        _write_cache(cache_file, latest_version="9.9.9", age_hours=1)

        def _boom(*a, **k):
            raise AssertionError("network should not be called on a cache hit")

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", _boom)
        assert check_for_update(tmp_applyr, "1.0.0") == "9.9.9"

    def test_cache_hit_with_no_newer_version_returns_none(self, tmp_applyr, cache_file, monkeypatch):
        _write_cache(cache_file, latest_version="1.0.0", age_hours=1)
        monkeypatch.setattr(
            "applyr.update_check.urllib.request.urlopen",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network expected")),
        )
        assert check_for_update(tmp_applyr, "1.0.0") is None


class TestCacheMissOrExpired:
    def test_absent_cache_hits_network(self, tmp_applyr, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"info": {"version": "2.0.0"}}).encode()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        assert check_for_update(tmp_applyr, "1.0.0") == "2.0.0"

    def test_expired_cache_hits_network_again(self, tmp_applyr, cache_file, monkeypatch):
        _write_cache(cache_file, latest_version="1.0.0", age_hours=25)

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"info": {"version": "3.0.0"}}).encode()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        assert check_for_update(tmp_applyr, "1.0.0") == "3.0.0"

    def test_network_result_is_written_back_to_cache(self, tmp_applyr, cache_file, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"info": {"version": "2.0.0"}}).encode()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        check_for_update(tmp_applyr, "1.0.0")
        cached = json.loads(cache_file.read_text())
        assert cached["latest_version"] == "2.0.0"
        assert "checked_at" in cached


class TestFailureIsSilent:
    def test_network_error_returns_none(self, tmp_applyr, monkeypatch):
        from urllib.error import URLError

        def _raise(*a, **k):
            raise URLError("no connection")

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", _raise)
        assert check_for_update(tmp_applyr, "1.0.0") is None

    def test_timeout_returns_none(self, tmp_applyr, monkeypatch):
        def _raise(*a, **k):
            raise TimeoutError()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", _raise)
        assert check_for_update(tmp_applyr, "1.0.0") is None

    def test_malformed_json_returns_none(self, tmp_applyr, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"not json"

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        assert check_for_update(tmp_applyr, "1.0.0") is None

    def test_missing_info_key_returns_none(self, tmp_applyr, monkeypatch):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"unexpected": "shape"}).encode()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        assert check_for_update(tmp_applyr, "1.0.0") is None

    def test_failed_check_still_writes_checked_at(self, tmp_applyr, cache_file, monkeypatch):
        from urllib.error import URLError

        monkeypatch.setattr(
            "applyr.update_check.urllib.request.urlopen",
            lambda *a, **k: (_ for _ in ()).throw(URLError("down")),
        )
        check_for_update(tmp_applyr, "1.0.0")
        cached = json.loads(cache_file.read_text())
        assert "checked_at" in cached
        assert "latest_version" not in cached

    def test_corrupt_cache_file_falls_back_to_network(self, tmp_applyr, cache_file, monkeypatch):
        cache_file.write_text("{not valid json")

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"info": {"version": "2.0.0"}}).encode()

        monkeypatch.setattr("applyr.update_check.urllib.request.urlopen", lambda *a, **k: _Resp())
        assert check_for_update(tmp_applyr, "1.0.0") == "2.0.0"
