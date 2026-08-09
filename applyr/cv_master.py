"""Deciding whether cv-master.md actually holds a profile.

`applyr init` writes a skeleton whose sections are literal `...` placeholders.
Every claim in a generated CV traces back to this file, so a skeleton that
reaches `cv generate` produces a CV with nothing truthful to fill it from — the
exact failure the agent instructions exist to prevent.

Until v1.0.0 both callers judged the file by its size alone (< 100 bytes meant
"empty"). The shipped skeleton weighs 94, so replacing just the placeholder name
with a real one pushed it over the line and the file read as filled — the first
edit any new user makes was enough to disable the guard.

The check here reads the file instead of weighing it, and is deliberately
language-agnostic: it looks for the placeholders the template ships with and for
the presence of real content, never for particular section names. A profile
written in Spanish is as valid as one written in English.
"""

from dataclasses import dataclass

# A section left as `...` is unfilled no matter how much text surrounds it.
PLACEHOLDER_LINES = {"...", "…"}

# Below this many words of real content, the file cannot describe a career — a
# floor for catching emptiness, not a measure of quality. Words rather than
# lines: a profile written as one long paragraph is as valid as a bulleted one.
MIN_CONTENT_WORDS = 30


@dataclass(frozen=True)
class CvMasterReport:
    """What a read of cv-master.md revealed."""

    filled: bool
    placeholder_sections: tuple[str, ...]
    content_words: int

    @property
    def reason(self) -> str | None:
        """Why the file is not usable, phrased for a human. None when it is."""
        if self.filled:
            return None
        if self.placeholder_sections:
            listed = ", ".join(self.placeholder_sections)
            return f"still the unfilled template — no content under: {listed}"
        return f"too thin to be a profile ({self.content_words} words of content)"


def inspect_cv_master(text: str) -> CvMasterReport:
    """Report whether this cv-master.md text holds a real profile.

    Content is every word on a line that is not blank, not a heading and not one
    of the template's placeholders. Headings are tracked only to name the
    sections left unfilled, so the report can point at what to write rather than
    just refusing.
    """
    placeholder_sections: list[str] = []
    content_words = 0
    current_section = "the document"

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            current_section = line.lstrip("#").strip() or current_section
            continue
        if line in PLACEHOLDER_LINES:
            if current_section not in placeholder_sections:
                placeholder_sections.append(current_section)
            continue
        content_words += len(line.split())

    filled = not placeholder_sections and content_words >= MIN_CONTENT_WORDS
    return CvMasterReport(
        filled=filled,
        placeholder_sections=tuple(placeholder_sections),
        content_words=content_words,
    )
