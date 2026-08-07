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
DEFAULT_FOLLOWUP_DAYS = 10
DEFAULT_LIST_LIMIT = 50
FOLLOWUP_UPCOMING_DAYS = 5
HIGH_PRIORITY_FREQ_THRESHOLD = 3
TREND_HISTORY_LIMIT = 12
CV_MASTER_MIN_SIZE = 100

# CV performance table
CV_STATS_NAME_WIDTH = 28

# Priority score thresholds (plan command)
PRIORITY_CRITICAL_SCORE = 200
PRIORITY_HIGH_SCORE = 100
PRIORITY_MEDIUM_SCORE = 40

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

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
VALID_SALARY_PERIODS = ("annual", "monthly", "hourly")

# ---------------------------------------------------------------------------
# Default config weights (used in config.py and TOML template)
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "tech_stack": 30,
    "education": 15,
    "english": 10,
    "experience": 15,
    "projects": 20,
    "cultural_fit": 10,
}

# ---------------------------------------------------------------------------
# JSON error snippet context (chars before/after parse error)
# ---------------------------------------------------------------------------
JSON_ERROR_CONTEXT = 20
