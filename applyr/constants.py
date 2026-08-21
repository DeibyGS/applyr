"""Centralized constants for applyr — no magic numbers in business logic."""

# ---------------------------------------------------------------------------
# Table display
# ---------------------------------------------------------------------------
LIST_COL_WIDTHS = [4, 18, 28, 4, 16, 8, 10]
LIST_HEADERS = ["ID", "COMPANY", "TITLE", "%", "STATUS", "MODE", "DATE"]
COMPARE_LABEL_WIDTH = 12
COMPARE_COL_MIN = 15
COMPARE_COL_MAX = 25
COMPARE_TERMINAL_WIDTH = 80
COMPARE_MAX_OFFERS = 10
COMPARE_MIN_OFFERS = 2
PROGRESS_BAR_WIDTH = 20
TREND_BAR_WIDTH = 15
PIPELINE_COMPANY_WIDTH = 16
PIPELINE_TITLE_WIDTH = 30
TRUNCATE_COMPANY = 18
TRUNCATE_TITLE = 28
FOLLOWUP_COMPANY_WIDTH = 16
FOLLOWUP_TITLE_WIDTH = 28

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
# database holds a few hundred offers, which is when the ranking matters most.
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
