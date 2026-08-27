"""Centralized constants for applyr — no magic numbers in business logic."""

import os
import shutil
import sys
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Terminal awareness
# ---------------------------------------------------------------------------

MIN_TERMINAL_WIDTH = 60
MAX_TERMINAL_WIDTH = 200
DEFAULT_TERMINAL_WIDTH = 80

PROGRESS_BAR_MIN_WIDTH = 10
PROGRESS_BAR_MAX_WIDTH = 50

TABLE_MIN_COL_WIDTH = 8
TABLE_PADDING = 2
SECTION_SPACING = 1


@dataclass
class TerminalContext:
    """Detected terminal capabilities."""
    width: int
    is_tty: bool
    colors_enabled: bool
    json_mode: bool


# Global state set by cli.py
_terminal_context: TerminalContext | None = None


def set_terminal_context(context: TerminalContext) -> None:
    """Set the global terminal context (called from cli.py)."""
    global _terminal_context
    _terminal_context = context


def get_terminal_context() -> TerminalContext:
    """Get or detect terminal context.

    Does NOT cache globally — each call detects fresh to avoid test pollution.
    cli.py sets the context explicitly after parsing flags.
    """
    try:
        size = shutil.get_terminal_size(fallback=(DEFAULT_TERMINAL_WIDTH, 24))
        width = max(MIN_TERMINAL_WIDTH, min(MAX_TERMINAL_WIDTH, size.columns))
    except Exception:
        width = DEFAULT_TERMINAL_WIDTH

    is_tty = sys.stdout.isatty()
    no_color_env = os.environ.get("NO_COLOR", "")
    colors_enabled = is_tty and not no_color_env

    return TerminalContext(
        width=width,
        is_tty=is_tty,
        colors_enabled=colors_enabled,
        json_mode=False,
    )


def calculate_column_widths(
    total_width: int,
    ratios: list[float],
    min_widths: list[int] | None = None,
) -> list[int]:
    """Calculate column widths from ratios, respecting minimums.

    Args:
        total_width: Available width (terminal width - padding)
        ratios: Proportional ratios for each column (sum ≈ 1.0)
        min_widths: Minimum width per column (default: TABLE_MIN_COL_WIDTH)

    Returns:
        List of integer column widths summing to ≤ total_width
    """
    if min_widths is None:
        min_widths = [TABLE_MIN_COL_WIDTH] * len(ratios)

    # First pass: assign minimums
    widths = list(min_widths)
    remaining = total_width - sum(widths)

    if remaining <= 0:
        return widths

    # Distribute remaining proportionally
    ratio_sum = sum(ratios)
    for i, ratio in enumerate(ratios):
        extra = int(remaining * ratio / ratio_sum)
        widths[i] += extra

    # Distribute any rounding remainder
    leftover = total_width - sum(widths)
    for i in range(leftover):
        widths[i % len(widths)] += 1

    return widths


# ---------------------------------------------------------------------------
# Table display (legacy constants — kept for backward compatibility)
# ---------------------------------------------------------------------------
LIST_COL_WIDTHS = [4, 18, 28, 4, 16, 8, 10]
LIST_HEADERS = ["ID", "COMPANY", "TITLE", "%", "STATUS", "MODE", "DATE"]
COMPARE_LABEL_WIDTH = 12
COMPARE_COL_MIN = 15
COMPARE_COL_MAX = 25
COMPARE_TERMINAL_WIDTH = 80
COMPARE_MAX_OFFERS = 10
COMPARE_MIN_OFFERS = 2
PROGRESS_BAR_WIDTH = 20  # Legacy fallback
TREND_BAR_WIDTH = 15
PIPELINE_COMPANY_WIDTH = 16
PIPELINE_TITLE_WIDTH = 30
TRUNCATE_COMPANY = 18
TRUNCATE_TITLE = 28
FOLLOWUP_COMPANY_WIDTH = 16
FOLLOWUP_TITLE_WIDTH = 28

# ---------------------------------------------------------------------------
# Table display (legacy constants — kept for backward compatibility)
# ---------------------------------------------------------------------------
LIST_COL_WIDTHS = [4, 18, 28, 4, 16, 8, 10]
LIST_HEADERS = ["ID", "COMPANY", "TITLE", "%", "STATUS", "MODE", "DATE"]
COMPARE_LABEL_WIDTH = 12
COMPARE_COL_MIN = 15
COMPARE_COL_MAX = 25
COMPARE_TERMINAL_WIDTH = 80
COMPARE_MAX_OFFERS = 10
COMPARE_MIN_OFFERS = 2
PROGRESS_BAR_WIDTH = 20  # Legacy fallback
TREND_BAR_WIDTH = 15
PIPELINE_COMPANY_WIDTH = 16
PIPELINE_TITLE_WIDTH = 30
TRUNCATE_COMPANY = 18
TRUNCATE_TITLE = 28
FOLLOWUP_COMPANY_WIDTH = 16
FOLLOWUP_TITLE_WIDTH = 28

# Column specs for dynamic tables (ratio, min_width, align)
LIST_COL_SPECS = [
    {"key": "id", "ratio": 0.04, "min_width": 4, "align": "right"},
    {"key": "company", "ratio": 0.22, "min_width": 12, "align": "left"},
    {"key": "title", "ratio": 0.35, "min_width": 16, "align": "left"},
    {"key": "pct", "ratio": 0.04, "min_width": 4, "align": "right"},
    {"key": "status", "ratio": 0.18, "min_width": 10, "align": "left"},
    {"key": "mode", "ratio": 0.09, "min_width": 6, "align": "left"},
    {"key": "date", "ratio": 0.08, "min_width": 8, "align": "left"},
]

PIPELINE_COL_SPECS = [
    {"key": "id", "ratio": 0.06, "min_width": 5, "align": "right"},
    {"key": "pct", "ratio": 0.05, "min_width": 4, "align": "right"},
    {"key": "company", "ratio": 0.30, "min_width": 12, "align": "left"},
    {"key": "title", "ratio": 0.59, "min_width": 20, "align": "left"},
]

COMPARE_COL_SPECS = [
    {"key": "label", "ratio": 0.15, "min_width": 10, "align": "left"},
    # Value columns calculated dynamically based on offer count
]

GAPS_COL_SPECS = [
    {"key": "priority", "ratio": 0.10, "min_width": 8, "align": "left"},
    {"key": "label", "ratio": 0.30, "min_width": 16, "align": "left"},
    {"key": "seen", "ratio": 0.10, "min_width": 8, "align": "right"},
    {"key": "avg_gap", "ratio": 0.12, "min_width": 10, "align": "right"},
]

PLAN_COL_SPECS = [
    {"key": "rank", "ratio": 0.05, "min_width": 3, "align": "right"},
    {"key": "label", "ratio": 0.35, "min_width": 18, "align": "left"},
    {"key": "seen", "ratio": 0.10, "min_width": 6, "align": "right"},
    {"key": "avg_gap", "ratio": 0.12, "min_width": 9, "align": "right"},
    {"key": "priority", "ratio": 0.10, "min_width": 8, "align": "left"},
]

TRENDS_COL_SPECS = [
    {"key": "period", "ratio": 0.20, "min_width": 10, "align": "left"},
    {"key": "bar", "ratio": 0.30, "min_width": 15, "align": "left"},
    {"key": "count", "ratio": 0.10, "min_width": 5, "align": "right"},
    {"key": "growth", "ratio": 0.40, "min_width": 18, "align": "left"},
]

SALARY_COL_SPECS = [
    {"key": "seniority", "ratio": 0.20, "min_width": 12, "align": "left"},
    {"key": "count", "ratio": 0.08, "min_width": 5, "align": "right"},
    {"key": "min", "ratio": 0.12, "min_width": 10, "align": "right"},
    {"key": "max", "ratio": 0.12, "min_width": 10, "align": "right"},
    {"key": "avg", "ratio": 0.12, "min_width": 10, "align": "right"},
    {"key": "median", "ratio": 0.12, "min_width": 10, "align": "right"},
    {"key": "period", "ratio": 0.10, "min_width": 8, "align": "left"},
]

CATEGORY_SALARY_COL_SPECS = [
    {"key": "category", "ratio": 0.20, "min_width": 12, "align": "left"},
    {"key": "count", "ratio": 0.08, "min_width": 5, "align": "right"},
    {"key": "min", "ratio": 0.16, "min_width": 10, "align": "right"},
    {"key": "max", "ratio": 0.16, "min_width": 10, "align": "right"},
    {"key": "avg", "ratio": 0.16, "min_width": 10, "align": "right"},
    {"key": "median", "ratio": 0.16, "min_width": 10, "align": "right"},
]

# ---------------------------------------------------------------------------
# Business logic thresholds
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLD = 65
DEFAULT_THRESHOLD_APPLY = 80
DEFAULT_THRESHOLD_MAYBE = 60
DEFAULT_FOLLOWUP_DAYS = 10
DEFAULT_LIST_LIMIT = 50
# Opt-in only — ADR-010 narrows ADR-001's "no network call" clause for this
# single, auditable case. Off by default: a fresh `applyr init` never calls out.
DEFAULT_CHECK_UPDATES = False
FOLLOWUP_UPCOMING_DAYS = 5
# Skill-gap priority, as a share of the worst gap rather than a count of
# sightings: an absolute recurrence threshold marks every topic HIGH once a
# database holds a couple of hundred offers, which is when the ranking matters most.
GAP_PRIORITY_HIGH_SHARE = 0.5
GAP_PRIORITY_MEDIUM_SHARE = 0.2
TREND_HISTORY_LIMIT = 12
# Below this many applied offers in a score band, `stats` shows the count
# instead of a rate — a rate from 1-2 offers reads as more predictive than it is.
CALIBRATION_MIN_SAMPLE = 5

# CV performance table
CV_STATS_NAME_WIDTH = 28

# `plan` used absolute score thresholds (200/100/40) that stopped discriminating
# once a database held a couple of hundred offers — every topic cleared 200, so
# every topic read CRITICAL. It now shares `_gap_priority` with `gaps`, which is
# relative to the worst gap, so both commands agree and both scale.

# Scoring
DEFAULT_TOPIC_WEIGHT = 0.10

# Duplicate detection — minimum title similarity (0.0-1.0) to treat two offers
# at the same company as the same role. Below this they are separate offers.
DUPLICATE_SIMILARITY_THRESHOLD = 0.85
DUPLICATE_COMPANY_HISTORY_LIMIT = 5

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
CHROME_TIMEOUT_SECONDS = 30
# Chrome's stderr can be very long; only the head is useful for diagnosis.
CHROME_STDERR_SNIPPET = 200
UPDATE_CHECK_TIMEOUT_SECONDS = 3

# ---------------------------------------------------------------------------
# PyPI update check (opt-in, see ADR-010 and specs/pypi-update-check/spec.md)
# ---------------------------------------------------------------------------
PYPI_UPDATE_CHECK_URL = "https://pypi.org/pypi/applyr/json"
UPDATE_CHECK_CACHE_TTL_HOURS = 24

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
VALID_SALARY_PERIODS = ("annual", "monthly", "hourly")
# Enum, not a float — an LLM-reported "0.82" isn't more meaningful than "high",
# and would invite the same two-representations-of-one-concept bug already
# found and fixed once this session for threshold/threshold_apply.
VALID_CONFIDENCE_LEVELS = ("high", "medium", "low")

# ---------------------------------------------------------------------------
# Default config weights (used in config.py and TOML template)
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "tech_stack": 35,
    "education": 5,
    "english": 5,
    "experience": 35,
    "projects": 15,
    "cultural_fit": 5,
}

# ---------------------------------------------------------------------------
# JSON error snippet context (chars before/after parse error)
# ---------------------------------------------------------------------------
JSON_ERROR_CONTEXT = 20

# ---------------------------------------------------------------------------
# Evidence-Based CV Engine (docs/adr/011-evidence-based-cv-engine.md)
# ---------------------------------------------------------------------------
# Curated, deliberately not exhaustive: a term ↔ its equivalent forms, so
# evidence.is_evidenced() can tell "AWS" and "Amazon Web Services" are the same
# claim without fuzzy/semantic matching (ADR-011 rejected that explicitly — a
# fuzzy matcher risks the verifier itself hallucinating support). Extend this
# dict as real gaps show up; each key's own name counts as one of its forms
# implicitly, so only list the *other* spellings here.
PROTECTED_FACT_ALIASES: dict[str, list[str]] = {
    "AWS": ["Amazon Web Services"],
    "GCP": ["Google Cloud Platform"],
    "PostgreSQL": ["Postgres"],
    "JavaScript": ["JS"],
    "TypeScript": ["TS"],
    "Kubernetes": ["K8s"],
    "CI/CD": ["Continuous Integration", "Continuous Deployment", "Continuous Delivery"],
}
