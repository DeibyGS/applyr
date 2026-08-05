"""Configuration management — loads/creates applyr.toml with defaults."""

import os
import tomllib
from pathlib import Path

APPLYR_DIR = Path(os.environ.get("APPLYR_HOME", Path.home() / ".applyr"))

TOML_TEMPLATE = """\
# applyr configuration
# Docs: https://github.com/DeibyGS/applyr

[general]
threshold = 65          # Minimum compatibility % to recommend applying
followup_days = 10      # Days before follow-up reminder
# db_path = "~/.applyr/jobs.db"
# list_limit = 50       # Default limit for 'list' command

[weights]
# Scoring weights — must sum to 1.0
tech_stack = 0.30
education = 0.15
english = 0.10
experience = 0.15
projects = 0.20
cultural_fit = 0.10

[topics]
# Display names for each scoring topic (add/remove as needed)
tech_stack = "Tech Stack"
education = "Education"
english = "English"
experience = "Experience"
projects = "Own Projects"
cultural_fit = "Cultural Fit"

[cv]
# chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# cv_master = "~/.applyr/cv-master.md"
# output_dir = "~/.applyr/cv"
"""


def _detect_chrome() -> str:
    """Find Chrome/Chromium binary path."""
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


def _build_defaults() -> dict:
    """Build default config dict with runtime values."""
    return {
        "general": {
            "threshold": 65,
            "followup_days": 10,
            "db_path": str(APPLYR_DIR / "jobs.db"),
            "list_limit": 50,
        },
        "weights": {
            "tech_stack": 0.30,
            "education": 0.15,
            "english": 0.10,
            "experience": 0.15,
            "projects": 0.20,
            "cultural_fit": 0.10,
        },
        "topics": {
            "tech_stack": "Tech Stack",
            "education": "Education",
            "english": "English",
            "experience": "Experience",
            "projects": "Own Projects",
            "cultural_fit": "Cultural Fit",
        },
        "cv": {
            "chrome_path": _detect_chrome(),
            "cv_master": str(APPLYR_DIR / "cv-master.md"),
            "output_dir": str(APPLYR_DIR / "cv"),
        },
    }


def load_config() -> dict:
    """Load config from ~/.applyr/applyr.toml, falling back to defaults."""
    defaults = _build_defaults()

    config_path = APPLYR_DIR / "applyr.toml"
    if not config_path.exists():
        return defaults

    try:
        with open(config_path, "rb") as f:
            user_config = tomllib.load(f)
        return _deep_merge(defaults, user_config)
    except Exception as e:
        print(f"Warning: could not parse {config_path}: {e}")
        print("Using default configuration.")
        return defaults


def create_default_config():
    """Create ~/.applyr/ directory and default applyr.toml if not present."""
    APPLYR_DIR.mkdir(parents=True, exist_ok=True)

    config_path = APPLYR_DIR / "applyr.toml"
    if not config_path.exists():
        config_path.write_text(TOML_TEMPLATE)
        print(f"  Created {config_path}")

    cv_dir = APPLYR_DIR / "cv"
    cv_dir.mkdir(exist_ok=True)
