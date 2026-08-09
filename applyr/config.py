"""Configuration management — loads/creates applyr.toml with defaults."""

import os
import tomllib
from pathlib import Path

from applyr.constants import DEFAULT_WEIGHTS, DEFAULT_THRESHOLD, DEFAULT_THRESHOLD_APPLY, DEFAULT_THRESHOLD_MAYBE, DEFAULT_FOLLOWUP_DAYS, DEFAULT_LIST_LIMIT

APPLYR_DIR = Path(os.environ.get("APPLYR_HOME", Path.home() / ".applyr"))

# Topic display names — hardcoded, not configurable
TOPIC_LABELS = {
    "tech_stack": "Tech Stack",
    "education": "Education",
    "english": "English",
    "experience": "Experience",
    "projects": "Own Projects",
    "cultural_fit": "Cultural Fit",
}

TOML_TEMPLATE = """\
# applyr configuration
# Docs: https://github.com/DeibyGS/applyr

[general]
threshold = 65          # Minimum compatibility % to recommend applying (legacy, use threshold_apply/maybe)
threshold_apply = 80    # Score >= this → APPLY
threshold_maybe = 60    # Score >= this → MAYBE (below → LOW MATCH)
followup_days = 10      # Days before follow-up reminder

[weights]
# Relative importance of each scoring topic (auto-normalized)
tech_stack = 30
education = 15
experience = 15
projects = 20
english = 10
cultural_fit = 10

[cv]
# cv_master  — the profile applyr reads to fill generated CVs. Fill it before
#              running 'cv generate'; a stub file produces an empty CV.
# output_dir — where generated CVs are written.
# Both accept any path, e.g. a private repo you already version. If you point
# them at a repo, make sure it is gitignored — CVs contain personal data.
# language   — the language generated CVs are written in when an offer does not
#              declare its own. Set it to the market you apply in most; an offer
#              in another language overrides it via "language" in 'applyr add'.
#              Supported: en, es.
cv_master = "__APPLYR_DIR__/cv-master.md"
output_dir = "__APPLYR_DIR__/cv"
language = "en"
"""


def _detect_chrome() -> str:
    """Find Chrome/Chromium binary path. Checks $CHROME_BIN env var first."""
    env_chrome = os.environ.get("CHROME_BIN", "")
    if env_chrome and os.path.isfile(env_chrome):
        return env_chrome
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving nested structure."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_weights(weights: dict) -> dict:
    """Normalize integer weights to decimals that sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: v / total for k, v in weights.items()}


def _build_defaults() -> dict:
    """Build default config dict with runtime values."""
    return {
        "general": {
            "threshold": DEFAULT_THRESHOLD,
            "threshold_apply": DEFAULT_THRESHOLD_APPLY,
            "threshold_maybe": DEFAULT_THRESHOLD_MAYBE,
            "followup_days": DEFAULT_FOLLOWUP_DAYS,
            "db_path": str(APPLYR_DIR / "jobs.db"),
            "list_limit": DEFAULT_LIST_LIMIT,
        },
        "weights": dict(DEFAULT_WEIGHTS),
        "cv": {
            "chrome_path": _detect_chrome(),
            "cv_master": str(APPLYR_DIR / "cv-master.md"),
            "output_dir": str(APPLYR_DIR / "cv"),
            "language": "en",
        },
    }


def load_config() -> dict:
    """Load config from ~/.applyr/applyr.toml, falling back to defaults."""
    defaults = _build_defaults()

    config_path = APPLYR_DIR / "applyr.toml"
    if not config_path.exists():
        config = defaults
    else:
        try:
            with open(config_path, "rb") as f:
                user_config = tomllib.load(f)
            config = _deep_merge(defaults, user_config)
        except Exception as e:
            print(f"Warning: could not parse {config_path}: {e}")
            print("Using default configuration.")
            config = defaults

    # Backward compatibility: if threshold_apply not set, derive from threshold
    general = config.get("general", {})
    if "threshold_apply" not in general:
        threshold = general.get("threshold", DEFAULT_THRESHOLD)
        general["threshold_apply"] = threshold
        general["threshold_maybe"] = max(0, threshold - 20)
    elif "threshold_maybe" not in general:
        general["threshold_maybe"] = max(0, general["threshold_apply"] - 20)

    # Normalize weights to decimals
    config["weights"] = _normalize_weights(config["weights"])
    return config


def create_default_config():
    """Create ~/.applyr/ directory and default applyr.toml if not present."""
    APPLYR_DIR.mkdir(parents=True, exist_ok=True)

    config_path = APPLYR_DIR / "applyr.toml"
    if not config_path.exists():
        # The template ships a placeholder rather than a literal ~/.applyr so
        # that an APPLYR_HOME install does not write paths pointing outside it.
        config_path.write_text(TOML_TEMPLATE.replace("__APPLYR_DIR__", str(APPLYR_DIR)))
        print(f"  Created {config_path}")

    cv_dir = APPLYR_DIR / "cv"
    cv_dir.mkdir(exist_ok=True)
