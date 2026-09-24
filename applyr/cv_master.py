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

import re
from dataclasses import dataclass

# A section left as `...` is unfilled no matter how much text surrounds it.
PLACEHOLDER_LINES = {"...", "…"}

# Guidance lines cv-master-template.md shipped as plain text up to v1.13.x.
# Users are told to delete them, but a profile filled around them kept them —
# and then they counted as content, and their examples ("Cut API latency by
# 42%", "DevOps") as evidence that let `cv verify` pass a fabricated claim.
# Current templates wrap guidance in HTML comments instead; this set keeps
# profiles created from the old template safe too.
LEGACY_TEMPLATE_GUIDANCE_LINES = frozenset({
    "Your full name, city, country, email, phone, LinkedIn, GitHub and website.",
    "2-3 sentences: who you are, your strongest area, seniority and the roles you target.",
    "For each role: **Job Title — Company** — City — Remote/Hybrid/Onsite — MM/YYYY–MM/YYYY,",
    'then 2-4 bullets with measurable results (e.g. "Cut API latency by 42%").',
    "For each degree: **Degree — Institution** — MM/YYYY–MM/YYYY.",
    "For each project: **Name — Stack** — URL, then what it does and its key technical decisions.",
    "Certifications with issuer and year.",
    "Grouped by area: Languages, Backend, Frontend, Databases, DevOps.",
    "Your languages with proficiency level.",
    "Availability, work preferences and location preferences.",
})

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_template_guidance(text: str) -> str:
    """cv-master.md text minus HTML comments and legacy template guidance lines."""
    text = _HTML_COMMENT_RE.sub("", text)
    return "\n".join(
        line for line in text.splitlines()
        if line.strip() not in LEGACY_TEMPLATE_GUIDANCE_LINES
    )

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

    for raw in strip_template_guidance(text).splitlines():
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
