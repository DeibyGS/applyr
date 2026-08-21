"""Tests for error output — stream routing, JSON mode, and stable error codes."""

import json

import pytest

from applyr import errors


@pytest.fixture(autouse=True)
def reset_json_mode():
    """Error mode is process-wide state — reset it between tests."""
    errors.set_json_mode(False)
    yield
    errors.set_json_mode(False)


class TestStreamRouting:
    def test_error_writes_to_stderr_not_stdout(self, capsys):
        errors.error("Error: something broke")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "something broke" in captured.err

    def test_warn_writes_to_stderr(self, capsys):
        errors.warn("heads up")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "heads up" in captured.err

    def test_die_writes_to_stderr_and_exits_1(self, capsys):
        with pytest.raises(SystemExit) as exc:
            errors.die("Error: fatal")
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "fatal" in captured.err

    def test_die_honors_custom_exit_code(self):
        with pytest.raises(SystemExit) as exc:
            errors.die("nope", exit_code=2)
        assert exc.value.code == 2


class TestTextMode:
    def test_die_prints_message_verbatim(self, capsys):
        with pytest.raises(SystemExit):
            errors.die("Error: invalid status 'nope'")
        assert "Error: invalid status 'nope'" in capsys.readouterr().err

    def test_text_override_replaces_human_message(self, capsys):
        with pytest.raises(SystemExit):
            errors.die("full context for machines", text="  Hint: try again")
        err = capsys.readouterr().err
        assert "Hint: try again" in err
        assert "full context for machines" not in err


class TestJsonMode:
    def test_emits_single_json_object_on_stderr(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("offer #42 not found.", code="not_found")
        captured = capsys.readouterr()
        assert captured.out == ""
        payload = json.loads(captured.err)
        assert payload == {"error": {"code": "not_found", "message": "offer #42 not found."}}

    def test_includes_details_when_given(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("bad", code="invalid_value", details={"field": "status"})
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["details"] == {"field": "status"}

    def test_omits_details_key_when_empty(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("bad", code="x")
        assert "details" not in json.loads(capsys.readouterr().err)["error"]

    def test_strips_redundant_error_prefix(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("Error: invalid status 'nope'", code="invalid_value")
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["message"] == "invalid status 'nope'"

    def test_text_override_is_ignored_in_json_mode(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("machine message", code="x", text="human hint")
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["message"] == "machine message"

    def test_error_is_suppressed_so_output_stays_valid_json(self, capsys):
        """Partial lines would break the object — only die() emits in JSON mode."""
        errors.set_json_mode(True)
        errors.error("Error: context line")
        errors.error("  Hint: a hint")
        with pytest.raises(SystemExit):
            errors.die("the real problem", code="not_found")
        captured = capsys.readouterr()
        assert captured.out == ""
        # Whole stderr must parse as one object, with no stray text around it
        assert json.loads(captured.err)["error"]["code"] == "not_found"

    def test_default_code_is_error(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("something")
        assert json.loads(capsys.readouterr().err)["error"]["code"] == "error"

    def test_non_ascii_is_not_escaped(self, capsys):
        errors.set_json_mode(True)
        with pytest.raises(SystemExit):
            errors.die("Duplicate — 100% match", code="duplicate")
        raw = capsys.readouterr().err
        assert "—" in raw
        assert json.loads(raw)["error"]["message"] == "Duplicate — 100% match"


class TestModeToggle:
    def test_is_json_mode_reflects_setting(self):
        assert errors.is_json_mode() is False
        errors.set_json_mode(True)
        assert errors.is_json_mode() is True


class TestReadTextOrDie:
    """Shared helper behind cv review, cv compare, and cv pdf's .md branch —
    previously each read a user-supplied file path directly, so a missing or
    binary file crashed with an unhandled traceback instead of a clean die()."""

    def test_returns_file_content_on_success(self, tmp_path):
        cv = tmp_path / "cv.md"
        cv.write_text("# CV\n")
        assert errors.read_text_or_die(cv) == "# CV\n"

    def test_missing_file_dies_with_file_not_found_code(self, tmp_path, capsys):
        errors.set_json_mode(True)
        missing = tmp_path / "does-not-exist.md"
        with pytest.raises(SystemExit):
            errors.read_text_or_die(missing)
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "file_not_found"

    def test_binary_file_dies_with_unsupported_format_code(self, tmp_path, capsys):
        errors.set_json_mode(True)
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot valid utf-8: \xff\xfe")
        with pytest.raises(SystemExit):
            errors.read_text_or_die(pdf)
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "unsupported_format"
        assert payload["error"]["details"] == {"path": str(pdf)}

    def test_custom_not_found_code_is_honored(self, tmp_path, capsys):
        errors.set_json_mode(True)
        missing = tmp_path / "does-not-exist.md"
        with pytest.raises(SystemExit):
            errors.read_text_or_die(missing, code_not_found="not_found")
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "not_found"
