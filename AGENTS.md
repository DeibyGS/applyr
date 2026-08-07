# AGENTS.md — Applyr

> Guide for AI coding agents working on the applyr codebase.

## What is Applyr?

A CLI job application tracker for AI coding agents. Python 3.12+, SQLite, zero heavy dependencies. Installable via `pip install applyr`.

**Key insight:** Applyr works **WITH** AI agents, not **THROUGH** them. It has no LLM API calls — the agent reads `AGENT_INSTRUCTIONS.md` and calls the CLI.

## Architecture

```
applyr/
├── cli.py              # Entry point — argparse, command routing, --json/--no-color
├── config.py           # ~/.applyr/applyr.toml, TOPIC_WEIGHTS, auto-normalize
├── db.py               # SQLite schema (28 columns), migrations
├── scoring.py          # Weighted compatibility calculation (pure function)
├── cv.py               # ATS HTML skeleton + Chrome PDF + recruiter review
├── colors.py           # Colorama wrapper, NO_COLOR support
├── constants.py        # All magic numbers, thresholds, column widths
├── commands/
│   ├── core.py         # CRUD: init, setup-agent, add, list, show, update, delete, search
│   ├── analytics.py    # Stats: pipeline, stats, gaps, followups, trends, summary, compare, plan, salary
│   ├── workflow.py     # Export: export, doctor
│   └── _helpers.py     # Shared: _bar(), _today(), _truncate()
├── templates/
│   ├── AGENT_INSTRUCTIONS.md   # End-user agent guide (DO NOT MODIFY)
│   ├── cv-ats.html             # ATS CV template
│   └── cv-master-template.md   # User profile template
└── tests/
    ├── test_scoring.py
    ├── test_config.py
    ├── test_db.py
    └── test_validators.py
```

## Data Flow

```
User → CLI (cli.py) → Command (commands/*.py) → DB (db.py) → Output
                         ↑
                         └── Scoring (scoring.py) — pure function, no I/O
```

## Conventions

- **Python 3.12+** — use `X | Y` union syntax, not `Optional[X]`
- **Type hints** — all function signatures
- **No global state** — config loaded per-call via `load_config()`
- **No LLM calls** — applyr is a storage layer, not an AI service
- **English** — all CLI output, commit messages, docs
- **Pure functions** — scoring logic has zero I/O, stays testable
- **Constants in constants.py** — no magic numbers in business logic

## How to Add a New Command

1. **Choose the right file:**
   - CRUD operations → `commands/core.py`
   - Analytics/reporting → `commands/analytics.py`
   - Export/system → `commands/workflow.py`

2. **Follow the pattern:**
   ```python
   def cmd_my_command(arg1: str, arg2: int = 0, as_json: bool = False) -> None:
       """One-line docstring."""
       conn = get_conn()
       try:
           # business logic
           pass
       finally:
           conn.close()
   ```

3. **Export it** in `commands/__init__.py`

4. **Add routing** in `cli.py` — follow the existing `elif cmd == ...` pattern

5. **Add tests** in `tests/` — pure function tests in their own file, command tests if I/O needed

## How to Add a New Scoring Topic

1. Add the topic key to `TOPIC_LABELS` in `config.py`
2. Add default weight to `DEFAULT_WEIGHTS` in `constants.py`
3. Add the TOML template entry in `config.py`
4. Tests in `tests/test_scoring.py`

## What NOT to Modify

| File | Why |
|------|-----|
| `templates/AGENT_INSTRUCTIONS.md` | End-user contract — agents depend on it |
| `db.py` SCHEMA_SQL | Existing data would break on schema change |
| `scoring.py` formula | Users rely on consistent scoring |
| `constants.py` DEFAULT_WEIGHTS | Changes alter scoring for all users |

## Running Tests

```bash
pytest                    # Run all 54 tests
pytest tests/test_scoring.py  # Just scoring tests
```

## Building

```bash
python -m build           # Creates dist/*.whl and dist/*.tar.gz
twine upload dist/*       # Publish to PyPI
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CHROME_BIN` | No | Path to Chrome/Chromium for PDF generation |
| `APPLYR_HOME` | No | Override `~/.applyr/` directory location |
| `NO_COLOR` | No | Disable colored output (also: `--no-color` flag) |
