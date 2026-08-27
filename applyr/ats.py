"""ATS compatibility checking and keyword matching for CVs."""

import json
import re
from pathlib import Path
from typing import NamedTuple

from applyr.errors import error

# Punctuation that wraps a title word rather than being part of it — parens,
# brackets, quotes (straight and curly). Deliberately NOT string.punctuation:
# that also includes "+", "#", "-", "/", which are meaningful inside a term
# ("C++", "C#", "CI/CD") and must survive stripping, not be reduced to a
# single letter that then fails the length filter below. Found by
# /code-review: a title like "Senior C++ Developer" — word "C++" — stripped
# to "c" under string.punctuation, dropped by the len > 2 gate, and silently
# lost the keyword entirely.
_TITLE_WRAPPING_PUNCTUATION = "()[]{}\"'“”‘’«»"


class ATSIssue(NamedTuple):
    """Single ATS compatibility issue."""
    category: str
    severity: str  # critical, warning, info
    message: str
    fix: str


class ATSReport(NamedTuple):
    """Full ATS compatibility report."""
    score: int
    issues: list[ATSIssue]
    format_ok: bool
    headers_ok: bool
    content_ok: bool


class KeywordMatch(NamedTuple):
    """Keyword matching result."""
    keyword: str
    found: bool
    context: str  # where found or suggestion


class KeywordReport(NamedTuple):
    """Full keyword matching report."""
    matched: list[KeywordMatch]
    missing: list[KeywordMatch]
    extra: list[str]
    match_rate: float


_RULES_PATH = Path(__file__).parent / "templates" / "ats_rules.json"


def _load_rules() -> dict:
    """Load ATS validation rules from JSON."""
    with open(_RULES_PATH) as f:
        return json.load(f)


def validate_ats_format(cv_content: str) -> ATSReport:
    """Validate CV content against ATS compatibility rules.

    Checks:
    - Single column layout (no tables, columns)
    - Standard section headers
    - No images, graphics, text boxes
    - Contact info not in headers/footers
    - Consistent date format
    - No complex formatting

    Args:
        cv_content: Raw markdown content of the CV

    Returns:
        ATSReport with score (0-100) and list of issues
    """
    rules = _load_rules()
    issues: list[ATSIssue] = []

    # Check for tables (markdown table syntax). A real markdown table has a pipe
    # at the start of each row (or a separator row like |---|---|). Plain text
    # CVs legitimately use pipes as inline separators (e.g. "email | phone"),
    # so only flag lines that *begin* with a pipe.
    table_pattern = r'^\s*\|.*\|'
    if re.search(table_pattern, cv_content, re.MULTILINE):
        issues.append(ATSIssue(
            category="format",
            severity="critical",
            message="Tables detected — ATS cannot parse table layouts",
            fix="Convert tables to bullet-point lists"
        ))

    # Check for multiple columns (common patterns)
    column_indicators = [r'^\s{4,}\S', r'^\t\t']
    for pattern in column_indicators:
        if re.search(pattern, cv_content, re.MULTILINE):
            issues.append(ATSIssue(
                category="format",
                severity="critical",
                message="Multiple columns detected — ATS requires single column",
                fix="Reformat to single-column layout"
            ))
            break

    # Check section headers
    standard_headers = rules["standard_headers"]
    found_headers = []
    for line in cv_content.split('\n'):
        line_stripped = line.strip()
        if line_stripped.startswith('## '):
            header = line_stripped[3:].strip()
            found_headers.append(header)

    non_standard = [h for h in found_headers if h not in standard_headers and h not in rules.get("allowed_headers", [])]
    if non_standard:
        issues.append(ATSIssue(
            category="headers",
            severity="warning",
            message=f"Non-standard headers: {', '.join(non_standard[:3])}",
            fix="Use standard headers: Professional Summary, Work Experience, Education, Skills"
        ))

    # Check for images/graphics
    image_patterns = [r'!\[.*\]\(.*\)', r'<img\s', r'<svg\s', r'<div.*style.*background']
    for pattern in image_patterns:
        if re.search(pattern, cv_content, re.IGNORECASE):
            issues.append(ATSIssue(
                category="format",
                severity="critical",
                message="Images/graphics detected — ATS cannot parse visual elements",
                fix="Remove all images, logos, and decorative graphics"
            ))
            break

    # Check for contact info in footers (text after last section)
    lines = cv_content.split('\n')
    last_section_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('## '):
            last_section_idx = i

    if last_section_idx > 0:
        footer_text = '\n'.join(lines[last_section_idx + 1:])
        contact_patterns = [r'@\w+\.\w+', r'\+\d{9,}', r'linkedin\.com/in/\w+']
        for pattern in contact_patterns:
            if re.search(pattern, footer_text):
                issues.append(ATSIssue(
                    category="contact",
                    severity="warning",
                    message="Contact info found after last section — 25% of ATS fail to parse",
                    fix="Move contact info to top of CV (first 5 lines)"
                ))
                break

    # Check date format consistency
    date_patterns = [
        r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',  # 1 Jan 2024
    ]
    found_formats = []
    for pattern in date_patterns:
        if re.search(pattern, cv_content):
            found_formats.append(pattern)

    if len(found_formats) > 1:
        issues.append(ATSIssue(
            category="dates",
            severity="warning",
            message="Multiple date formats detected — may confuse ATS parsing",
            fix="Use consistent format: MM/YYYY throughout"
        ))

    # Calculate score
    critical_count = sum(1 for i in issues if i.severity == "critical")
    warning_count = sum(1 for i in issues if i.severity == "warning")

    score = 100
    score -= critical_count * 25
    score -= warning_count * 10
    score = max(0, score)

    return ATSReport(
        score=score,
        issues=issues,
        format_ok=critical_count == 0,
        headers_ok=not any(i.category == "headers" for i in issues),
        content_ok=score >= 70
    )


def extract_keywords(offer_data: dict) -> list[str]:
    """Extract keywords from offer data.

    Pulls keywords from:
    - tech_stack (comma-separated)
    - title
    - role_category

    Args:
        offer_data: Dict with offer fields from database

    Returns:
        List of normalized keywords
    """
    keywords = set()

    # From tech_stack
    tech_stack = offer_data.get("tech_stack", "")
    if tech_stack:
        for kw in tech_stack.split(","):
            kw = kw.strip().lower()
            if kw:
                keywords.add(kw)

    # From title (extract significant words)
    title = offer_data.get("title", "")
    if title:
        # Common words to skip
        skip_words = {"developer", "engineer", "senior", "junior", "mid", "full", "stack", "the", "and", "or"}
        for word in title.split():
            word_lower = word.lower().strip(_TITLE_WRAPPING_PUNCTUATION)
            if word_lower not in skip_words and len(word_lower) > 2:
                keywords.add(word_lower)

    return sorted(keywords)


def match_keywords(cv_content: str, keywords: list[str]) -> KeywordReport:
    """Match keywords against CV content.

    Args:
        cv_content: Raw markdown content of the CV
        keywords: List of keywords to search for

    Returns:
        KeywordReport with matched, missing, and extra keywords
    """
    cv_lower = cv_content.lower()
    matched = []
    missing = []

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in cv_lower:
            # Find context
            idx = cv_lower.find(kw_lower)
            start = max(0, idx - 30)
            end = min(len(cv_content), idx + len(kw) + 30)
            context = cv_content[start:end].replace('\n', ' ').strip()
            matched.append(KeywordMatch(keyword=kw, found=True, context=f"...{context}..."))
        else:
            missing.append(KeywordMatch(keyword=kw, found=False, context="Not found in CV"))

    match_rate = len(matched) / len(keywords) * 100 if keywords else 0

    return KeywordReport(
        matched=matched,
        missing=missing,
        extra=[],
        match_rate=round(match_rate, 1)
    )
