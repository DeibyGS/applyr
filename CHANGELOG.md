# Changelog

All notable changes to applyr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-08-09

### Added

- **`language` field on offers** (`en`, `es`): the language a CV is written in is
  a fact about the vacancy, so it is recorded with the offer rather than passed
  as a flag at generation time. `cv generate` writes the skeleton's headings in
  that language and tells the filling agent to use it throughout.
  - Falls back to `[cv] language` in `applyr.toml` (default `en`) when an offer
    does not declare one, so offers recorded before this release keep working.
  - Schema v4. `applyr show` displays it; `add` rejects a language applyr has no
    headings for, rather than silently producing an English CV.

### Fixed

- **`doctor` and `cv generate` accepted an unfilled cv-master.md.** Both judged
  the file by size (< 100 bytes meant "empty") and the template `init` writes
  weighs 94 — replacing the placeholder name with a real one was enough to make
  both report a filled profile. They now read the file: a section still holding
  the template's `...` placeholder is unfilled at any size. The check never
  matches section names, so profiles in any language pass.
- **Generated CVs mixed languages.** The skeleton hardcoded English headings
  while the agent wrote content in the language of the offer, delivering Spanish
  bullets under "Work Experience" — incoherent to the recruiter and invisible to
  an ATS scanning for "EXPERIENCIA".

## [1.0.0] — 2026-08-08

### Added

- **Three-state recommendation**: APPLY (>=80%), MAYBE (60-79%), LOW MATCH (<60%)
  - Configurable thresholds in `applyr.toml` (`threshold_apply`, `threshold_maybe`)
  - Backward compatible: old `threshold` still works
  - Colored output with icons: ✅ APPLY, ⚠️ MAYBE, ❌ LOW MATCH

- **Skill-level breakdown**: Strong (>=80%), Partial (50-79%), Missing (<50%)
  - Shown in `cmd_add` and `cmd_show` output
  - Icons: ✓ Strong, △ Partial, ✕ Missing

- **"Why you match" summary**: Top 3 strong topics + biggest weakness
  - Executive summary after recommendation
  - Helps user understand strengths and gaps quickly

- **CV tailoring hints**: HTML comments in generated CVs
  - Highlights skills to emphasize based on job requirements
  - Shows what to de-emphasize (low-scoring topics)
  - Tailoring summary in `cv generate` output

- **Score breakdown**: Weighted contribution per topic
  - Shows "Technical skills 80% × 30% weight = 24.0 contribution"
  - Explains why the total score is what it is

- 33 new tests for recommendation, breakdown, and tailoring logic

### Changed

- `cmd_add` output now shows recommendation, breakdown, and "Why you match"
- `cmd_show` output now shows breakdown, score breakdown, and recommendation
- `cv generate` output now shows tailoring summary

## [0.9.0] — 2026-08-08

### Changed

- **BREAKING: `cv generate` outputs `.md` instead of `.html`.** CVs are now
  drafted as markdown files with YAML frontmatter (offer_id, topic_scores,
  cv_master, date). The agent reads and edits markdown directly — no more
  stripping HTML tags to find the editable content

- **`cv_used` stores basename without extension.** The `offers.cv_used` column
  now stores `cv-acme-engineer` instead of `cv-acme-engineer.html`. Existing
  `.html` values are migrated via schema v2→v3

- **`cv review` and `cv pdf` accept both `.md` and `.html` files.** The commands
  dispatch by file extension. Legacy HTML files continue to work unchanged

### Added

- **`applyr/md_render.py`**: Narrow markdown→ATS-HTML converter. Supports
  headings (h1-h6), paragraphs, unordered lists, bold, italic, and links.
  Rejects tables, images, and ATX closing headings with stable error codes

- **ADR 008**: Documents rationale for markdown-first pipeline

- Schema migration v2→v3: strips `.html` extension from `cv_used` values

- 11 tests for `md_render` module, 2 tests updated for markdown output

### Fixed

- `cv_used` no longer stores file extensions, preventing double-extension
  bugs when agents pass the value to `cv review` or `cv pdf`

## [0.8.4] — 2026-08-08

### Fixed
- **Commands no longer recreate a missing database.** Running `applyr list` (or any
  command other than `init`) against a missing `jobs.db` now fails with a clear error
  message instead of silently recreating the database. This was a regression from
  session 11 that made `doctor` always exit 0

### Removed
- **`skill_gaps` table dropped.** The table was write-only since v0.5.0 — `cmd_add`
  wrote to it, but `_live_skill_gaps()` derives gaps from `offer_topics` and ignores
  the table entirely. Schema migrated from v1 to v2 with `DROP TABLE IF EXISTS`

### Changed
- **Python 3.11 now supported.** `requires-python` lowered from `>=3.12` to `>=3.11`.
  CI matrix expanded to test on 3.11, 3.12, and 3.13

### Added
- 115 tests for `cli.py` routing (AC-2.1 … AC-2.7), coverage 0% → 92%
- Regression guard tests ensuring no command recreates a missing database
- Migration test verifying `skill_gaps` table is dropped on upgrade

## [0.8.3] — 2026-08-08

`setup-agent` copies applyr's instructions into other projects' AI config, so a
stale local copy never stayed local — it propagated outdated guidance everywhere
it was run.

### Fixed
- **`AGENT_INSTRUCTIONS.md` no longer goes stale forever.** `init` wrote
  `~/.applyr/AGENT_INSTRUCTIONS.md` only when it was missing, and
  `_get_agent_instructions()` preferred that local copy unconditionally. Upgrading
  applyr therefore changed nothing: `setup-agent` kept emitting whatever the first
  install happened to ship. Instructions are now stamped with the applyr version
  that wrote them, and a stale copy is bypassed in favour of the packaged one

### Added
- **`doctor` reports instruction drift** as a `note` — visible, but not blocking.
  A stale copy does not invalidate the setup, because `setup-agent` already serves
  the packaged version, so it must not gate `applyr doctor && applyr cv generate`
- 23 tests covering stamping, staleness comparison and the distribution rules

### Notes
- The local file is **never rewritten**. It is the user's and may carry hand
  edits; silently overwriting it would be the mirror image of the bug being fixed.
  To refresh it, delete it and run `applyr init`
- A copy stamped by a *newer* applyr (the user downgraded) counts as current.
  Warning about the future is noise
- The stamp is applied when the file is written, not stored in the shipped
  template, so a release cannot ship a template claiming the wrong version

## [0.8.2] — 2026-08-07

`doctor` was the command v0.8.1 told every agent to run first, and it could not
fail. Two defects made it report a healthy setup no matter what.

### Fixed
- **`applyr doctor` exits `1` when the setup is unhealthy.** It always exited `0`,
  including while printing "3 issue(s) found", so `applyr doctor && applyr cv
  generate 3` built a CV from an empty profile without hesitating. This was
  already a contract violation: `docs/contracts.md` states that a command
  reporting a problem and exiting `0` is a bug. Chrome stays non-blocking — a
  missing PDF renderer does not invalidate the setup
- **`doctor` no longer recreates the database it is checking.** Every command
  except `init` ran `init_db()` before routing, so by the time the health check
  looked, a deleted `jobs.db` had been silently recreated and its `NOT FOUND`
  branch was unreachable. `doctor` is now excluded from that auto-init and
  observes the real state

### Added
- **`applyr doctor --json`** — `{"healthy", "issues", "checks": [...]}`, with a
  `status` of `ok`, `issue` or `note` per check. Agents read this command first;
  now they can parse it instead of scraping text
- 8 tests for `doctor`, which had none. `commands/workflow.py` coverage went from
  11% to 49%, and total from 32% to 35%

### Changed
- `docs/contracts.md` distinguishes a failed invocation from a command whose job
  is to render a verdict, and records that `doctor` must never mutate what it
  inspects — the ambiguity is what let both defects look acceptable
- `cmd_doctor` split into one function per check, clearing its
  `too-many-branches` and `too-many-statements` warnings (pylint 9.36 → 9.41)

## [0.8.1] — 2026-08-07

### Added
- **The test suite now runs in CI.** The `test` job only ever smoke-tested the
  CLI, so the unit tests never ran on a pull request — which is how seven of the
  eight bugs found in the v0.8.0 audit reached a release from modules with no
  coverage. `pytest --cov` now runs on 3.12 and 3.13
- **Coverage measurement** via `pytest-cov`, configured in `pyproject.toml`.
  Baseline is 32%: `cli.py` 0%, `commands/analytics.py` 7%,
  `commands/workflow.py` 11%. No `fail_under` gate yet — the floor gets set once
  those modules are covered
- Regression tests for `update --cv`, which had none

### Changed
- **`AGENT_INSTRUCTIONS.md` now opens with `applyr doctor`.** The health check
  already detected an unfilled `cv-master.md`, but the documented flow never ran
  it, so the check existed and nobody reached it. `doctor` is now step 1 of both
  setup and the per-offer workflow, and the entry point for error recovery
- **`applyr update <id> <status> --cv ""` stores `NULL` instead of `""`.**
  Clearing already worked; the empty string just left two different values
  meaning "no CV" in the database. Whitespace-only values clear too

## [0.8.0] — 2026-08-07

Thirteen bugs found by running one real job application end to end — register
offer, score, generate CV, review, PDF — then exercising every analytics
command and error path. Seven of the first eight lived in modules that had no
test coverage at all.

### Changed
- **`cv generate` refuses to overwrite an existing CV.** Regenerating used to
  replace finished, hand-tailored content with an empty skeleton, with no undo.
  Pass `--force` to opt in
- **`cv generate` rejects an unfilled `cv-master.md`.** The guard existed only
  in `doctor`, so generation succeeded and left the agent nothing to fill the
  placeholders from — a silent failure that could go unnoticed for weeks
- **`delete` requires `--force` when no terminal is attached.** It used to
  raise a bare `EOFError` traceback instead of a structured error
- Generated CVs no longer embed topic scores. Candid self-assessment shipped
  inside the file sent to the recruiter. `cv review` now resolves scores from
  the database through an `applyr:offer-id` marker, falling back to the old
  inline block for CVs generated by earlier versions
- The generated `applyr.toml` ships `cv_master` and `output_dir` uncommented
  and documented. Both were supported but invisible, so the CV workflow could
  not start and never said why

### Fixed
- Generated CVs spilled onto a second page. Chrome stacks its own default page
  margin on top of the body padding; the ATS template now sets
  `@page { margin: 0 }` and owns its margins
- `update <id> applied` never recorded `date_applied`, so `summary` always
  reported zero applications, the default `list` sort had nothing to sort on
  and follow-ups never came due. `COALESCE` preserves the first date across
  later transitions
- Skill gaps are derived from `offer_topics` instead of the `skill_gaps` table.
  That table is an append-only counter nothing decrements, so deleted offers
  inflated it forever and `plan` could recommend studying a topic that only
  ever existed in a test
- `_strip_html_tags` restarted from the original HTML when removing `<script>`,
  undoing the stylesheet removal and pushing the entire CSS into the review
  prompt. It now also strips HTML comments
- The config template hardcoded `~/.applyr`, which overrode the
  `APPLYR_HOME`-derived default and wrote generated CVs outside an isolated
  install. It now interpolates the real directory
- User-facing messages in `init`, `setup-agent` and the Chrome error print the
  actual path instead of a literal `~/.applyr`
- `applyr add --help` parsed `--help` as JSON instead of showing usage
- CV filenames keep only `[a-z0-9-]`; "Full Stack (JS)" produced names that
  needed shell quoting

### Added
- `tests/test_cv.py` and `tests/test_commands.py` — 24 regression tests, one
  per fix above, covering `cv.py`, `commands/core.py` and `commands/analytics.py`
- `.gitignore` now excludes `cv/` and `*.pdf`: this is a public repository and
  generated CVs carry personal data

## [0.7.0] — 2026-08-07

### Fixed
- Chrome failure paths in `cv pdf` called `sys.exit(1)` directly and printed to stdout, so they emitted nothing in `--json` mode and mixed diagnostics into parsed output. They now report through `die()` with a `chrome_failed` code and Chrome's stderr in `details`
- Removed unused imports left behind across `cv.py`, `commands/core.py`, `commands/analytics.py` and `commands/workflow.py`

### Added
- `applyr cv stats` — compare CVs by response rate (any reply, including rejections) and interview rate (reached `in_process` or `offer`). Flags samples below `--min-sample` as noise and reports offers with no CV recorded
- `applyr cv generate` now records the generated filename in `cv_used`, so CV tracking populates itself
- `--cv` flag on `applyr update`, to record a CV for offers applied to outside the `cv generate` flow
- `applyr/cv_stats.py` with 17 tests
- Structured JSON errors: with `--json`, failures emit `{"error": {"code", "message", "details"}}` on stderr so agents can branch on a stable code instead of matching English prose. See [ADR 007](docs/adr/007-structured-json-errors.md)
- `docs/adr/007-structured-json-errors.md`
- 15 tests for error routing, JSON mode and code stability

### Fixed
- Several error paths printed a message and returned instead of exiting, so commands like `applyr show abc` reported a failure but exited `0` — scripts and agents read that as success. All failure paths now exit `1`

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
