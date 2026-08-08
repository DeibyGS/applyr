# Contributing to applyr

Thanks for your interest in contributing. applyr is a small, focused CLI — contributions that keep it lean, reliable, and agent-friendly are always welcome.

---

## Ways to contribute

- **Bug fix** — something breaks or behaves unexpectedly
- **New command** — extend the CLI with useful functionality
- **Scoring improvement** — refine the weighted scoring engine
- **CV pipeline** — better ATS templates, PDF generation, or recruiter review
- **Documentation** — fix a typo, clarify a step, add an example

If you're unsure whether your idea fits, open an issue first and describe what you want to build.

---

## Setup

**Requirements:** Python 3.11+

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/applyr
cd applyr

# 2. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 3. Run the test suite
pytest
```

Expected output: **54 tests passing** (~0.1s). All tests must pass before opening a PR.

---

## Project structure

```
applyr/
  cli.py                 # Entry point
  config.py              # TOML config
  db.py                  # SQLite schema (offers: 31 columns)
  scoring.py             # Weighted scoring engine
  cv.py                  # ATS CV + Chrome PDF + recruiter review
  commands/
    core.py              # add, list, show, update, delete, search, init, setup-agent
    analytics.py         # stats, gaps, trends, pipeline, compare, plan, salary
    workflow.py          # export, doctor
  templates/
    AGENT_INSTRUCTIONS.md
tests/
  test_scoring.py        # unit tests for the scoring engine
  test_config.py
  test_db.py
  test_validators.py
```

---

## Making changes

### Branch naming

```
fix/description-of-bug
feat/name-of-feature
docs/what-you-changed
refactor/what-you-simplified
```

### Code style

- Python 3.11+, typed signatures
- Keep functions small and focused — follow the `commands/` package split
- No new dependencies without a clear justification
- CLI labels and messages in English

### Keep business logic free of database access

Scoring and validation must not touch SQLite — that lives in `db.py`, reached
through `get_conn()`. Keeping them separate is what makes them easy to test.

Note that `calculate_score()` is not fully I/O-free: it reads the user config
through `load_config()` to get topic weights. Tests must point `APPLYR_HOME` at
a temp directory or patch `load_config`.

---

## Tests

The suite covers scoring, config, DB, and validators:

```bash
pytest
```

If you change `scoring.py`, add a test in `tests/test_scoring.py` covering at least: the happy path, an edge case (e.g. empty weights), and boundary values around the apply threshold.

---

## Opening a PR

1. Make sure `pytest` passes locally
2. Open a PR against the `main` branch
3. Include in the PR description:
   - **What** changed
   - **Why** it was needed
   - **How** to test it manually (if not fully covered by automated tests)

Keep PRs focused. One feature or fix per PR — easier to review and merge.

---

## Reporting a bug

Open an issue and include:

- Python version (`python --version`)
- `applyr doctor` output
- OS and version
- Steps to reproduce
- What you expected vs what happened

---

## Questions

Ask in GitHub Discussions — no question is too small.