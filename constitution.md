# Project Constitution — applyr

Version: 1.0.0

## Tech Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11+ | Use `X | Y` union syntax, not `Optional[X]` |
| Database | SQLite | Schema in `db.py`, migrations via versioned system |
| CLI | argparse | Entry point in `cli.py`, routing in `commands/` |
| CV Render | Chrome headless | PDF via `cv.py`, HTML via `md_render.py` |
| Testing | pytest | 329+ tests, ~3s |
| Linting | pylint | Score 9.50+, fail-under=7.0 |

## Architecture Principles

- **Storage layer, not AI service** — applyr never calls LLM APIs. The agent is the brain.
- **Agent-native** — all commands output `--json`, errors to stderr, stable error codes.
- **No global state** — config loaded per-call via `load_config()`.
- **No DB access outside `db.py`** — commands call `get_conn()`, never open SQLite directly.
- **Constants in `constants.py`** — no magic numbers in business logic.

## Naming Conventions

- Files: snake_case (`cv_master.py`)
- Variables/functions: snake_case
- Classes: PascalCase
- DB columns: snake_case
- CLI commands: kebab-case (`cv generate`)
- Error codes: snake_case (`chrome_failed`)

## Security Constraints

- No LLM API calls (ADR 003)
- No secrets in logs or code
- SQLite opened only via `get_conn()` with `PRAGMA foreign_keys`
- No user input interpolated in SQL (parameterized queries only)

## Banned Patterns

- Never modify `templates/AGENT_INSTRUCTIONS.md` without human approval
- Never edit `db.py` SCHEMA_SQL in place — use migration system
- Never change `scoring.py` formula without ADR
- Never change `constants.py` DEFAULT_WEIGHTS without ADR
- Never rename/remove CLI commands or aliases
- Never rename/remove `--json` output keys
- Never remove values from `VALID_*` enums
- Never add LLM API calls
- Never open SQLite outside `db.py`

## Error Handling

- All errors go to stderr via `error()`/`warn()`/`die()` from `errors.py`
- Every failure ends in `die()` — bare `return` after error exits 0 and lies
- Give errors a `code` — agents branch on it; message wording is not a contract

## Testing Requirements

- Every new command needs tests
- Pure function tests in their own file
- Command tests if I/O needed
- Tests and code in same commit
- PR budget: 400 lines max
- Coverage gate: `fail_under = 75` in `pyproject.toml`'s `[tool.coverage.report]` — CI already
  ran `pytest --cov` without enforcing it; a PR that drops total coverage below 75% now fails.
  Raise deliberately as coverage grows; never lower it to make a red build green.

## CV Pipeline Rules

- `cv generate` creates skeleton — agent fills placeholders
- `cv review` generates prompt — agent executes
- `cv pdf` generates PDF via Chrome headless
- CV headings per language via `CV_HEADINGS` dict
- Tailoring via `<!-- TAILOR: ... -->` comments
