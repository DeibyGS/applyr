"""Tests for applyr.md_render — narrow markdown→ATS-HTML converter."""

import pytest

from applyr.md_render import (
    _check_unsupported,
    _convert_inline,
    render_markdown_file_to_html,
    render_markdown_to_html,
)


class TestConvertInline:
    def test_bold(self):
        assert "<strong>hello</strong>" in _convert_inline("**hello**")

    def test_italic(self):
        assert "<em>hello</em>" in _convert_inline("*hello*")

    def test_link(self):
        assert '<a href="https://example.com">' in _convert_inline("[click](https://example.com)")


class TestCheckUnsupported:
    def test_unsupported_table(self, capsys):
        with pytest.raises(SystemExit):
            _check_unsupported("| a | b |", 1)

    def test_unsupported_image(self, capsys):
        with pytest.raises(SystemExit):
            _check_unsupported("![alt](img.png)", 1)

    def test_supported_line(self):
        _check_unsupported("# Hello", 1)  # Should not raise


class TestRenderMarkdownToHtml:
    def test_returns_string(self):
        html = render_markdown_to_html("# Hello")
        assert isinstance(html, str)
        assert "Hello" in html

    def test_renders_heading(self):
        html = render_markdown_to_html("## Section")
        assert "<h2>Section</h2>" in html

    def test_renders_paragraph(self):
        html = render_markdown_to_html("Hello world")
        assert "<p>Hello world</p>" in html


class TestRenderMarkdownFileToHtml:
    def test_renders_file(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello\n\nWorld")
        html = render_markdown_file_to_html(str(md_file))
        assert "Hello" in html
        assert "World" in html

    def test_strips_frontmatter(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("---\ntitle: Test\n---\n\n# Hello")
        html = render_markdown_file_to_html(str(md_file))
        assert "Hello" in html
        assert "title" not in html

    def test_missing_file_dies_with_a_clear_message_not_a_stack_trace(self, tmp_path):
        missing = tmp_path / "does-not-exist.md"
        with pytest.raises(SystemExit):
            render_markdown_file_to_html(str(missing))

    def test_binary_file_dies_instead_of_raising_unicode_decode_error(self, tmp_path):
        """Reached via `cv pdf <file.md>` when the markdown source is
        mis-encoded — previously an unhandled UnicodeDecodeError."""
        md_file = tmp_path / "cv-broken.md"
        md_file.write_bytes(b"\xff\xfe not valid utf-8")
        with pytest.raises(SystemExit):
            render_markdown_file_to_html(str(md_file))
