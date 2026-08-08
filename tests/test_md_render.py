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
