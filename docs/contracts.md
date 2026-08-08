# Contracts & Invariants

> What is safe to change, what is not, and what must always hold true.

This document is the authority on stability guarantees. When it disagrees with
any other doc, this file wins. Every value below is verified against the source
files named in parentheses — never restate them from memory.

---

## Stable contracts

Breaking any of these requires a **major version bump** and a CHANGELOG entry.

### CLI surface

Command names, their positional arguments, and their aliases are public
(`applyr/cli.py`). Renaming or removing one breaks user scripts and any agent
following `templates/AGENT_INSTRUCTIONS.md`.

Current aliases: `ls` → `list`, `st` → `stats`, `fu` → `followups`,
`cmp` → `compare`, `sal` → `salary`.

Adding a new command is always safe. Renaming an existing one is not.

### JSON output

Every command accepting `--json` emits machine-readable output consumed by
agents. Adding a key is backward compatible; renaming or removing one is not.

### Database schema

`SCHEMA_SQL` in `applyr/db.py` defines four tables:

| Table | Purpose |
|-------|---------|
| `offers` | Main record — 31 columns |
| `offer_topics` | Per-topic scores, cascades on offer delete |
| `skill_gaps` | Aggregated missing skills, keyed by skill name |
| `schema_version` | Single-row migration tracker |

Schema changes go through the migration system, never through direct edits to
`SCHEMA_SQL` on an existing version. See [Migrations](#migrations).

### Configuration format

`~/.applyr/applyr.toml` sections `[general]` and `[weights]` are public.
`APPLYR_HOME` overrides the directory (`applyr/config.py`). Config is optional —
defaults must keep working with no file present.

### Error codes

With `--json`, failures emit one JSON object on stderr
([ADR 007](adr/007-structured-json-errors.md)):

```json
{"error": {"code": "not_found", "message": "offer #42 not found.", "details": {"offer_id": 42}}}
```

`code` is stable and public. `message` wording is not — never match on it.
`details` is optional and additive.

| Code | Meaning |
|------|---------|
| `not_found` | Offer, file or template does not exist |
| `duplicate` | An identical or near-identical offer already exists (`--force` overrides) |
| `invalid_value` | Value outside an allowed enum — `details.valid` lists the accepted ones |
| `invalid_argument` | Argument of the wrong type, e.g. a non-integer ID |
| `invalid_range` | Numerically inconsistent, e.g. `salary_min > salary_max` |
| `invalid_json` | Input JSON could not be parsed |
| `missing_field` | Required field absent from the payload |
| `missing_value` | A flag was given without its value |
| `chrome_not_found` | Chrome/Chromium missing, needed for PDF |
| `db_error` | Database could not be opened or initialized |
| `error` | Unclassified — refining one into a specific code is additive, not breaking |

Adding a code is safe. Renaming or removing one is breaking.

### Enumerated values

Defined in `applyr/db.py`. These are stored as plain text in SQLite, so removing
a value orphans existing rows.

| Constant | Accepted values |
|----------|-----------------|
| `VALID_STATUSES` | `pending`, `applied`, `waiting`, `in_process`, `rejected`, `discarded`, `offer` |
| `VALID_CHANNELS` | `linkedin_easy`, `linkedin_direct`, `email`, `portal`, `referral`, `other` |
| `VALID_WORK_MODES` | `remote`, `hybrid`, `onsite` |
| `VALID_SENIORITY` | `trainee`, `entry_level`, `junior`, `mid`, `senior`, `lead`, `director` |
| `VALID_ROLE_CATEGORIES` | `backend`, `frontend`, `fullstack`, `ai`, `devops`, `data`, `mobile`, `qa`, `other` |
| `VALID_SALARY_PERIODS` (`constants.py`) | `annual`, `monthly`, `hourly` |

Scoring topic keys (`TOPIC_LABELS` in `applyr/config.py`): `tech_stack`,
`education`, `english`, `experience`, `projects`, `cultural_fit`.

---

## CV tracking

`offers.cv_used` holds the filename of the CV sent for that offer. `cv generate`
sets it automatically; `update --cv` sets it manually. Rates in `cv stats` are
computed only over **sent** offers (`applied`, `waiting`, `in_process`,
`rejected`, `offer`) — counting `pending` would make every rate fall as you
register offers you have not applied to yet.

A rejection counts as a *response* but not as an *interview*: being rejected
means the CV was read.

## Agent instructions distribution

`~/.applyr/AGENT_INSTRUCTIONS.md` is written once by `init` and carries a version
stamp on its first line (`<!-- applyr-version: X.Y.Z -->`). The stamp is applied
at write time, not stored in the shipped template.

Two rules hold together, and neither may be relaxed without the other:

- **A stale copy is bypassed, never obeyed.** When the stamp is older than the
  installed package — or absent, as in every file written before 0.8.3 —
  `setup-agent` emits the packaged instructions and warns on stderr. Serving
  outdated instructions is a bug, because `setup-agent` writes them into other
  projects.
- **A stale copy is bypassed, never rewritten.** The file belongs to the user and
  may hold hand edits. No command overwrites it; refreshing means deleting it and
  running `init` again.

A stamp from a newer applyr counts as current. `doctor` reports drift as a
`note`, not an `issue`: the setup still works, so it must not gate.

## Invariants

Properties that must hold after every change. A failing invariant is a bug, not
a preference.

### Scoring

- `calculate_score()` returns an `int` in `[0, 100]` — `applyr/scoring.py`
- Empty topics dict returns `0`, never raises
- Topic scores outside `[0, 100]` are **skipped**, not clamped and not an error
- A topic absent from `[weights]` falls back to `DEFAULT_TOPIC_WEIGHT` (`0.10`)
- Weights are normalized to sum `1.0` at load time — the TOML stores relative
  integers (`30`, `15`, `10`), never fractions
- When `total_weight` is `0`, the result is `0` — never a division by zero

### Database

- `offers.id` is `INTEGER PRIMARY KEY AUTOINCREMENT` — never reused, never
  reassigned
- `PRAGMA foreign_keys = ON` is set on every connection (`get_conn()`)
- Deleting an offer cascades to its `offer_topics` rows
- `offers.status` defaults to `pending`
- `offers.salary_period` defaults to `annual`
- Boolean-ish columns (`applied`, `follow_up_done`, `cover_letter`) are `0`/`1`
  integers, not SQLite booleans
- Dates are stored as `TEXT` in `YYYY-MM-DD` format
- A DB with `version > SCHEMA_VERSION` must fail loudly, never silently downgrade

### CLI

- Every command closes its connection in a `finally` block
- `NO_COLOR` env var and `--no-color` flag both disable color (`applyr/colors.py`)
- **stdout carries data only. All errors and warnings go to stderr** via
  `applyr/errors.py` (`error()`, `warn()`, `die()`) — see
  [ADR 006](adr/006-errors-to-stderr.md). Never use a bare `print()` for an
  error, a warning, or a hint line that follows one.
- **Every failure path ends in `die()`**, never a bare `return`. A command that
  reports a problem and exits `0` is a bug — see the `--json` note below.
- Validation failures print a message starting with `Error:` on stderr and exit `1`
- `--json` output goes to stdout with nothing else mixed in. A failed `--json`
  invocation emits nothing on stdout and exits non-zero
- Usage text shown when a command is called with no arguments is help, not an
  error: it goes to stdout and exits `0`
- **A command whose job is to render a verdict exits non-zero on a negative one,
  and its report stays on stdout.** `doctor` is the only such command today: a
  health check that always exits `0` cannot gate anything, so it exits `1` when a
  blocking issue is found — while still printing the full report as data, in text
  and in `--json`. This is not the "failed invocation" case above: the command
  succeeded, the answer is just "unhealthy". Do not route it through `die()`
- **`doctor` must never mutate what it inspects.** It is excluded from the
  automatic `init_db()` in `cli.py`; while it ran through that path the database
  was recreated before the check and a missing database always reported OK

---

## Extension points

Safe places to add functionality without touching a stable contract.

| You want to add | Where it goes |
|-----------------|---------------|
| A CRUD command | `applyr/commands/core.py` |
| An analytics/report command | `applyr/commands/analytics.py` |
| An export format or system command | `applyr/commands/workflow.py` |
| A shared display helper | `applyr/commands/_helpers.py` |
| An error or warning message | `applyr/errors.py` — never a bare `print()` |
| A duplicate-detection rule | `applyr/duplicates.py` |
| A CV performance metric | `applyr/cv_stats.py` |
| A scoring topic | `TOPIC_LABELS` (`config.py`) + `DEFAULT_WEIGHTS` (`constants.py`) |
| A threshold or magic number | `applyr/constants.py` — never inline |
| A CV or document template | `applyr/templates/` |

Every new command also needs: an export in `commands/__init__.py`, a routing
branch in `cli.py`, tests, and a CHANGELOG entry.

---

## Not extension points

Changing any of these is an architectural decision requiring an ADR in
`docs/adr/`, not a routine PR.

- **Replacing the storage engine.** SQLite choice is documented in
  `docs/adr/002-why-sqlite.md`.
- **Adding LLM API calls.** Applyr never calls a model — see
  `docs/adr/003-no-llm-calls.md`.
- **Redesigning the CLI or JSON shape.** Both are public contracts.
- **Changing `DEFAULT_WEIGHTS` or the scoring formula.** Users' historical scores
  would become inconsistent with new ones.
- **Editing `templates/AGENT_INSTRUCTIONS.md`.** It is the end-user contract that
  external agents load at runtime.

---

## Migrations

`SCHEMA_VERSION` and `MIGRATIONS` live in `applyr/db.py`.

To change the schema:

1. Bump `SCHEMA_VERSION` from `N` to `N + 1`
2. Add `MIGRATIONS[(N, N + 1)] = ["ALTER TABLE offers ADD COLUMN ...;"]`
3. Update `SCHEMA_SQL` so fresh installs match the migrated shape
4. Add a test asserting an old DB upgrades cleanly

Migrations are additive. Dropping a column loses user data with no recovery
path — applyr databases are local and typically unbacked up.

---

## Deliberately unstable

No compatibility promise. Change freely.

- Private helpers (leading underscore): `_bar()`, `_today()`, `_truncate()`,
  `_deep_merge()`, `_normalize_weights()`, `_detect_chrome()`
- Human-readable table layout — column widths in `constants.py` are cosmetic
- Wording of any non-JSON console message
- Internal test fixtures and helpers
