# Changelog

All notable changes to applyr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.6.0] — 2026-08-07

### Changed
- **BREAKING:** all error and warning output now goes to **stderr** instead of stdout. stdout carries data only, so `applyr <cmd> --json` emits either a valid JSON document or nothing. Scripts that captured stdout to read error text must now capture stderr (`2>&1`). See [ADR 006](docs/adr/006-errors-to-stderr.md)
- `applyr add` now blocks on near-identical offers at the same company, not only on exact title matches. `"Backend Engineer (Remote)"` is detected as a variant of `"Backend Engineer"`

### Added
- `--force` flag on `applyr add` to insert despite a detected duplicate — previously an exact duplicate had no escape
- `applyr add` reports previous offers at the same company without blocking, since applying to several roles at one company is normal
- `applyr/errors.py` — `error()`, `warn()`, `die()` helpers
- `applyr/duplicates.py` — title normalization and similarity matching, with work-mode qualifiers (`Remote`, `Hybrid`, `m/f/d`) stripped before comparison
- 23 tests for duplicate detection

### Documentation
- `docs/adr/` — 6 Architecture Decision Records: local-first, SQLite, no LLM calls, weighted scoring, single CLI, errors-to-stderr
- `docs/mental-model.md` — what applyr is and is not, design principles, anti-patterns
- `docs/agent-workflow.md` — reading order, definition of done, common tasks, when to stop and ask
- `docs/contracts.md` — stable contracts, invariants, extension points and the migration procedure
- "Forbidden Changes" section in `AGENTS.md`, expanded with the reason for each rule
- Linting instructions in `AGENTS.md` and `llms.txt` with the exact command CI runs

### Fixed
- `applyr/__init__.py` reported `0.5.0` while `pyproject.toml` declared `0.5.1`, so `applyr version` did not match the installed release. Both are now `0.6.0`
- Documentation stated `offers` had 28 columns and the database 3 tables — it has 31 columns and 4 tables (`offers`, `offer_topics`, `skill_gaps`, `schema_version`)
- Documentation described `scoring.py` as a pure function with no I/O — `calculate_score()` reads user config via `load_config()`, which tests must isolate with `APPLYR_HOME`
- `llms.txt` claimed no linter was configured — CI has run pylint since v0.4.0

## [0.5.1] — 2026-08-07

### Fixed
- Version bump to 0.5.1 (0.5.0 was already published on PyPI)

## [0.5.0] — 2026-08-07

### Changed
- **BREAKING:** Split `commands.py` (1646 lines) into `commands/` package (core, analytics, workflow)
- README redesigned with progressive disclosure, visual flow, scannable layout

### Added
- 54 pytest tests for scoring, config, db, validators
- Badges and AI Development Benchmark in README

### Fixed
- Duplicate detection before adding offers
- Threshold recommendation in `applyr doctor`
- Input validations across all commands
- Templates packaging in wheel

## [0.4.1] — 2026-08-06

### Added
- `applyr cv review <file.html>` — generates recruiter prompt with ATS scoring rubric
- Topic key validation in `cmd_add` — warns on unknown keys
- Full rewrite of `AGENT_INSTRUCTIONS.md` (scoring rubric, 4-step CV flow, error recovery)

## [0.4.0] — 2026-08-06

### Added
- `constants.py` — centralized magic numbers, thresholds, column widths
- `colors.py` — colorama wrapper with `NO_COLOR` support
- `--json` flag on all data commands
- Schema migration system in `db.py`
- `applyr doctor` — configuration and database health check

### Changed
- **First dependency:** colorama >= 0.4.6
- Exit codes now follow conventions (0=ok, 1=error)
- Error messages include actionable hints

### Fixed
- 18 bugs found during production quality audit

## [0.3.0] — 2026-08-06

### Added
- `applyr compare <id1> <id2> [idN...]` — side-by-side ASCII table (2-10 offers)
- `applyr plan [--limit N]` — prioritized learning plan from skill gaps
- `applyr salary [--seniority S] [--category C]` — salary stats by seniority/category
- `applyr setup-agent` — configure AI agent (claude, cursor, opencode, generic)
- Aliases: `cmp=compare`, `sal=salary`

### Changed
- `VALID_SENIORITY` expanded: added `trainee`, `entry_level`

## [0.2.1] — 2026-08-06

### Added
- Getting-started message for new users
- Quick-start section in README
- AI Development Benchmark documentation

## [0.2.0] — 2026-08-06

### Added
- Initial public release
- 17 commands, 28-column SQLite schema
- ATS CV generation with Chrome headless PDF
- Weighted compatibility scoring (6 topics)
- `--json` output for agent integration
- Published on PyPI as `applyr`

[0.5.1]: https://github.com/DeibyGS/applyr/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/DeibyGS/applyr/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/DeibyGS/applyr/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/DeibyGS/applyr/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/DeibyGS/applyr/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/DeibyGS/applyr/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/DeibyGS/applyr/releases/tag/v0.2.0
