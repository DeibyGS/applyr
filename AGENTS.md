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
├── db.py               # SQLite schema (offers: 31 columns), enums, migrations
├── scoring.py          # Weighted compatibility calculation (reads config for weights)
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
                         └── Scoring (scoring.py) — no DB access, but
                             calls load_config() for weights
```

> **Testing note:** `calculate_score()` is deterministic given a config, but it
> is not I/O-free — it reads `~/.applyr/applyr.toml` via `load_config()`. Tests
> must set `APPLYR_HOME` to a temp dir or patch `load_config`.

## Conventions

- **Python 3.12+** — use `X | Y` union syntax, not `Optional[X]`
- **Type hints** — all function signatures
- **No global state** — config loaded per-call via `load_config()`
- **No LLM calls** — applyr is a storage layer, not an AI service
- **English** — all CLI output, commit messages, docs
- **No DB access outside db.py** — commands call `get_conn()`, never open SQLite directly
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

## Forbidden Changes

Never do any of these without an explicit request from a human maintainer and
an ADR in `docs/adr/`:

| Change | Why |
|--------|-----|
| Modify `templates/AGENT_INSTRUCTIONS.md` | End-user contract — external agents load it at runtime |
| Edit `db.py` SCHEMA_SQL in place | Existing local databases would break — use the migration system |
| Change the `scoring.py` formula | Historical scores become incomparable with new ones |
| Change `constants.py` DEFAULT_WEIGHTS | Silently alters scoring for every user |
| Rename or remove a CLI command or alias | Breaks user scripts and agent workflows |
| Rename or remove a `--json` output key | Breaks machine consumers |
| Remove a value from a `VALID_*` enum | Orphans existing rows — enums are stored as text |
| Add an LLM API call | Applyr is a storage layer by design — see `docs/adr/003-no-llm-calls.md` |
| Open SQLite outside `db.py` | Bypasses `PRAGMA foreign_keys` and the migration check |

Full rules, invariants and safe extension points: **[`docs/contracts.md`](docs/contracts.md)**.

## Running Tests

```bash
pytest                    # Run all 54 tests
pytest tests/test_scoring.py  # Just scoring tests
```

## Linting

CI enforces pylint on Python 3.12 and 3.13. Run it before opening a PR — the
exact command CI uses:

```bash
pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801 --fail-under=7.0
```

No formatter, type checker or coverage gate is configured.

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
