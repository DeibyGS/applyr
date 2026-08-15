"""Configuration management — loads/creates applyr.toml with defaults."""

import os
import tomllib
from pathlib import Path

from applyr.constants import DEFAULT_WEIGHTS, DEFAULT_THRESHOLD, DEFAULT_THRESHOLD_APPLY, DEFAULT_THRESHOLD_MAYBE, DEFAULT_FOLLOWUP_DAYS, DEFAULT_LIST_LIMIT

APPLYR_DIR = Path(os.environ.get("APPLYR_HOME", Path.home() / ".applyr"))

# Generated CVs are deliverables the user has to find and attach elsewhere
# (a form, an email, LinkedIn) — unlike APPLYR_DIR's config/db/cv-master.md,
# they default outside the dotfile so a normal file browser shows them.
CV_HOME = Path(os.environ.get("APPLYR_CV_HOME", Path.home() / "Documents" / "applyr"))

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
tech_stack = 35
experience = 35
projects = 15
education = 5
english = 5
cultural_fit = 5

[cv]
# cv_master  — the profile applyr reads to fill generated CVs. Fill it before
#              running 'cv generate'; a stub file produces an empty CV.
# output_dir — where generated CVs are written. Defaults outside the applyr
#              config directory so they show up in a file browser without
#              unhiding dotfiles.
# Both accept any path, e.g. a private repo you already version. If you point
# them at a repo, make sure it is gitignored — CVs contain personal data.
# language   — the language generated CVs are written in when an offer does not
#              declare its own. Set it to the market you apply in most; an offer
#              in another language overrides it via "language" in 'applyr add'.
#              Supported: en, es.
cv_master = "__APPLYR_DIR__/cv-master.md"
output_dir = "__CV_HOME__/cv"
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
            "output_dir": str(CV_HOME / "cv"),
            "language": "en",
        },
    }


def load_config() -> dict:
    """Load config from ~/.applyr/applyr.toml, falling back to defaults."""
    defaults = _build_defaults()

    config_path = APPLYR_DIR / "applyr.toml"
    user_config: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                user_config = tomllib.load(f)
        except Exception as e:
            print(f"Warning: could not parse {config_path}: {e}")
            print("Using default configuration.")
            user_config = {}

    config = _deep_merge(defaults, user_config)

    # Backward compatibility: a config that only sets the legacy `threshold`
    # key derives threshold_apply/threshold_maybe from it. This must check
    # the RAW user config, not the merged one: defaults always populate
    # threshold_apply/threshold_maybe, so a legacy-only file would never
    # look "incomplete" once merged, and its custom threshold would be
    # silently ignored in favor of the 80/60 defaults.
    user_general = user_config.get("general", {})
    if "threshold_apply" not in user_general and "threshold" in user_general:
        threshold = user_general["threshold"]
        config["general"]["threshold_apply"] = threshold
        config["general"]["threshold_maybe"] = max(0, threshold - 20)
    elif "threshold_apply" in user_general and "threshold_maybe" not in user_general:
        config["general"]["threshold_maybe"] = max(0, config["general"]["threshold_apply"] - 20)

    # Normalize weights to decimals for calculate_score(), but keep the raw
    # relative-integer dict too — that's the shape weights_used snapshots
    # (matching how the TOML itself stores them, never fractions).
    config["weights_raw"] = dict(config["weights"])
    config["weights"] = _normalize_weights(config["weights"])
    return config


def create_default_config():
    """Create ~/.applyr/ directory and default applyr.toml if not present."""
    APPLYR_DIR.mkdir(parents=True, exist_ok=True)

    config_path = APPLYR_DIR / "applyr.toml"
    if not config_path.exists():
        # The template ships placeholders rather than literal paths so that an
        # APPLYR_HOME/APPLYR_CV_HOME install does not write paths pointing
        # outside them.
        config_path.write_text(
            TOML_TEMPLATE.replace("__APPLYR_DIR__", str(APPLYR_DIR)).replace("__CV_HOME__", str(CV_HOME))
        )
        print(f"  Created {config_path}")

    cv_dir = CV_HOME / "cv"
    cv_dir.mkdir(parents=True, exist_ok=True)
