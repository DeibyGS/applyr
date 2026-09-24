"""Markdown to ATS-safe HTML converter.

A narrow converter that handles exactly the subset the CV template produces:
headings, paragraphs, unordered lists, bold, italic, links, and horizontal
rules. Unsupported syntax causes die() with a stable error code.

See docs/adr/008-md-first-cv-pipeline.md for the rationale.
"""

import html
import re
from pathlib import Path

from applyr.errors import die, read_text_or_die


# Supported HTML tags (ATS-safe: no tables, no flexbox, no images)
_INLINE_TAGS = {
    "strong": "strong",
    "em": "em",
    "a": "a",
}

# Regex patterns for inline markdown
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"\*(.+?)\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_FRONTMATTER_RE = re.compile(r"---\r?\n.*?\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_INLINE_RE = re.compile(
    r"(?P<strong>\*\*(.+?)\*\*)"
    r"|(?P<em>\*(.+?)\*)"
    r"|(?P<link>\[([^\]]+)\]\(([^)]+)\))"
)


def _escape_text(value: str) -> str:
    """Escape CV text for HTML: "List<T>", "R&D" or a stray "<br>" used to
    reach Chrome as markup — dropped text or broken layout in the PDF."""
    return html.escape(value, quote=False)


def _convert_inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links) to HTML."""
    result = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        # Add text before match
        result.append(_escape_text(text[pos:m.start()]))

        if m.group("strong"):
            result.append(f"<strong>{_escape_text(m.group(2))}</strong>")
        elif m.group("em"):
            result.append(f"<em>{_escape_text(m.group(4))}</em>")
        elif m.group("link"):
            result.append(f'<a href="{html.escape(m.group(7))}">{_escape_text(m.group(6))}</a>')

        pos = m.end()

    result.append(_escape_text(text[pos:]))
    return "".join(result)


def _check_unsupported(line: str, line_num: int) -> None:
    """Check for unsupported markdown syntax and die if found."""
    # Tables (pipe-separated columns with alignment)
    if re.match(r"^\|.*\|$", line.strip()):
        die(
            f"Unsupported markdown syntax on line {line_num}: tables are not allowed (ATS-hostile)",
            code="unsupported_markdown",
            details={"line": line_num, "syntax": "table", "content": line.strip()},
        )

    # Images
    if re.match(r"!\[.*\]\(.*\)", line.strip()):
        die(
            f"Unsupported markdown syntax on line {line_num}: images are not allowed",
            code="unsupported_markdown",
            details={"line": line_num, "syntax": "image", "content": line.strip()},
        )

    # Headings with ATX closing (e.g., "## Title ##")
    if re.match(r"^#{1,6}\s+.*\s+#+\s*$", line.strip()):
        die(
            f"Unsupported markdown syntax on line {line_num}: closing ATX headings are not supported",
            code="unsupported_markdown",
            details={"line": line_num, "syntax": "atx_closing", "content": line.strip()},
        )


def render_markdown_to_html(md: str) -> str:
    """Convert markdown to ATS-safe HTML.

    Supports exactly: h1-h6, paragraphs, ul, bold, italic, links, hr.
    Unsupported syntax causes die().

    Args:
        md: Markdown content (without YAML frontmatter).

    Returns:
        HTML string safe for ATS parsing.
    """
    lines = md.split("\n")
    html_parts = []
    i = 0

    while i < len(lines):
        line = lines[i]
        line_num = i + 1

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Check for unsupported syntax
        _check_unsupported(line, line_num)

        # Horizontal rule (---, ***, ___)
        if re.match(r"^[-*_]{3,}\s*$", line.strip()):
            html_parts.append("<hr>")
            i += 1
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2)
            html_parts.append(f"<h{level}>{_convert_inline(content)}</h{level}>")
            i += 1
            continue

        # Unordered list items
        ul_match = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
        if ul_match:
            html_parts.append(f"<li>{_convert_inline(ul_match.group(2))}</li>")
            i += 1
            continue

        # Regular paragraph (collect consecutive non-special lines)
        para_lines = []
        while i < len(lines):
            current = lines[i]
            if (
                not current.strip()
                or re.match(r"^#{1,6}\s+", current)
                or re.match(r"^[-*_]{3,}\s*$", current.strip())
                or re.match(r"^(\s*)[-*+]\s+", current)
            ):
                break
            _check_unsupported(current, i + 1)
            para_lines.append(current)
            i += 1

        if para_lines:
            para_text = " ".join(para_lines)
            html_parts.append(f"<p>{_convert_inline(para_text)}</p>")
            continue

        i += 1

    # Wrap list items in <ul>
    result = "\n".join(html_parts)
    result = re.sub(r"(<li>.*?</li>(?:\n<li>.*?</li>)*)", r"<ul>\1</ul>", result, flags=re.DOTALL)

    return result


def render_markdown_file_to_html(md_path: str) -> str:
    """Read a markdown file and convert to HTML.

    Strips YAML frontmatter if present.

    Args:
        md_path: Path to markdown file.

    Returns:
        HTML string.
    """
    content = read_text_or_die(Path(md_path))

    # Strip YAML frontmatter. The closing fence is a line of its own —
    # `find("---", 3)` stopped at a "---" inside a frontmatter value.
    frontmatter = _FRONTMATTER_RE.match(content)
    if frontmatter:
        content = content[frontmatter.end():].lstrip("\n")

    # `cv generate`'s TAILOR/LANGUAGE scaffold comments are not CV content.
    # They used to pass through as raw HTML comments; now that text is
    # escaped they would print as visible text, so they go before rendering.
    content = _HTML_COMMENT_RE.sub("", content)

    return render_markdown_to_html(content)
