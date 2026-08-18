## Spec: Calibration, redacted export, and README trust signals

### Status: IMPLEMENTED (code-reviewed, fixes applied, ready for PR)
### Version: 1.2

### Code review pass (2026-08-19)

`/code-review` found 10 real defects across `export --redact` and the (separately
bundled) `ats-check` fix — all fixed in this branch before PR:
- `--redact-fields` stripping to empty (e.g. `","`) now dies instead of silently
  exporting unredacted.
- `DEFAULT_REDACT_FIELDS` expanded: `cv_used`/`cover_letter_file` (leaked company
  identity via the slugged filename even with `company` redacted) and
  `follow_up_notes` (same free-text class as `notes`, previously missed).
- Numeric-field redaction generalized from a hardcoded `{salary_min, salary_max}`
  set to reading the real column type off `PRAGMA table_info(offers)` — any numeric
  column named via `--redact-fields` now redacts to `null`, not a type-corrupting
  string.
- `--redact` + `--redact-fields` combined (override, not merge) is now documented in
  the CLI help text — behavior unchanged, AC-B2 already specified it, it just wasn't
  visible to a user typing `--help`.
- `cv ats-check`'s sibling-hint no longer points at the same broken file when the
  input is already `.md`, and now checks `.html` siblings too, not just `.md`.
- `read_text()` now specifies `encoding="utf-8"` explicitly (matches the rest of the
  file's convention; the one implicit call was the only one platform-dependent).
- The same `UnicodeDecodeError` guard extended to `cv bullet-optimize` (identical
  user-supplied-path pattern) and `cv keywords` (DB-resolved path, no sibling hint —
  user decision to include both in this PR rather than defer).
`/simplify-lean` ran after: no changes needed.

### Revision note (discovered during Task 1 implementation)

`applyr stats` / `stats --json` already ships a `score_calibration` section
(PR #60, predates this spec — missed during "Recovered context" because the
search for prior art didn't catch it under this exact name). It already: buckets
by `threshold_apply`/`threshold_maybe`, excludes `weights_used IS NULL` per
ADR-009, and always exposes raw counts in `--json` regardless of sample size —
the exact honesty property this spec's Feature A wanted. Its `responded`/
`interview`/`offer` funnel is a *superset* of the resolved-only success/failure
view this spec proposed (a stricter framing that would have thrown away the
interview-stage signal, not added anything).

**Decision (user, mid-implementation): discard the new `applyr calibration`
command entirely.** The original `cmd_calibration` implementation (which also
had a real bug: it didn't exclude `weights_used IS NULL`, unlike the existing
helper) was reverted in full. The only change kept from Feature A:
`CALIBRATION_MIN_SAMPLE` raised from 3 to 5 in `applyr/constants.py`, applied
to the existing `_score_calibration()` used by `stats`.

Feature A below is left in the spec as a record of what was considered and
rejected, not as work still to be done.

### Recovered context

- **ADR-009** (supersedes ADR-004): scores are snapshotted per offer via `weights_used`,
  specifically so a stored `compatibility_pct` never drifts from what the user actually
  saw at decision time. Calibration must read the stored score, never recompute it.
- **PR #64** (`doctor` — CV Privacy check): the project already has a precedent for
  privacy-conscious features guarding against accidentally publishing sensitive data.
  `--redact` follows the same spirit for `export`.
- **`cmd_export`** (`applyr/commands/workflow.py:49`) already has a deliberate design
  note: exports default into `APPLYR_DIR`, not the cwd, specifically to avoid an
  accidental `git add .` publishing the whole database. `--redact` extends that same
  privacy posture to the *content*, not just the file location.
- **HANDOFF.md** roadmap: "career intelligence / outcome calibration (necesita datos de
  uso real acumulados, no iniciado)" — this spec implements the read side of that item.
  It does not and cannot fix the fact that the metric needs volume over time; the
  minimum-sample guard (AC-A2) exists specifically so the command is honest about that.
- **README.md** already has a live CI badge for `python-package.yml` and a static
  `tests-576 passed` badge — the latter is stale (verified test count is higher after
  the 2026-08-16 and 2026-08-18 sessions). `pylint.yml` has no badge at all.
- Corrected assumption from Step 2: calibration's population excludes `discarded`
  offers (in addition to unresolved ones), because most `discarded` offers were never
  applied to — counting them as failures would make LOW MATCH read as "0% success"
  by construction, not because of any real market signal.

### What does it do? (observable behavior, not implementation)

- `applyr calibration` reports, per score bucket (APPLY / MAYBE / LOW MATCH, using the
  user's configured thresholds), what fraction of offers the user actually applied to
  and heard back on turned into an offer — so the tool's own scoring can be checked
  against real outcomes instead of taken on faith.
- `applyr export --redact` produces the same CSV/JSON/Markdown export as today, with a
  fixed set of sensitive fields replaced by a redaction marker, so a user can publish a
  real export (e.g. as evidence in a blog post or LinkedIn post) without leaking company
  names, salary, contact info, or notes.
- README.md gains a `pylint.yml` CI badge and a corrected, verified test-count badge.

### Acceptance criteria

#### `applyr calibration` — DISCARDED, see revision note above; superseded by raising `CALIBRATION_MIN_SAMPLE` (3→5) on the existing `stats` calibration

- `[MUST]` The system shall compute bucket boundaries from `threshold_apply` /
  `threshold_maybe` in the user's config (`load_config()`), never hardcoded values.
- `[MUST]` The system shall read `compatibility_pct` directly from the `offers` table
  for each offer — never recompute it from `offer_topics`.
- `[MUST]` The system shall restrict the calibration population to offers with
  `status IN ('rejected', 'offer')`. Offers with `status IN ('pending', 'discarded',
  'applied', 'waiting', 'in_process')` are excluded from both numerator and denominator.
- `[MUST]` WHEN a bucket's resolved count (`success + failure`) is less than 5, THE
  system SHALL omit the percentage in text output and print
  `muestra insuficiente (n=X)` instead, where X is the actual resolved count.
- `[MUST]` WHEN `--json` is passed, THE system SHALL always emit, per bucket, the raw
  `success`, `failure`, `resolved` counts and a boolean `insufficient_sample` field —
  regardless of sample size. JSON output is never gated on sample size; only the
  human-readable percentage is.
- `[SHOULD]` WHEN there are zero resolved offers across every bucket, THE system SHALL
  print one clear message ("aún no hay suficientes ofertas resueltas") instead of an
  empty or all-blank table.
- `[SHOULD]` Given a bucket has `resolved >= 5`, When `applyr calibration` runs, Then
  the printed percentage is `success / resolved`, rounded to the nearest integer.
- `[WONT]` Any UI/dashboard beyond the existing text/`--json` CLI pattern the rest of
  the tool already uses.

#### `applyr export --redact`

- `[MUST]` WHEN `--redact` is passed without `--redact-fields`, THE system SHALL
  replace these fields in every exported record: `company`, `job_url`, `contact_name`,
  `contact_role`, `location`, `salary_min`, `salary_max`, `notes`, `rejection_reason`,
  `summary`. Text fields become `"[REDACTED]"`; `salary_min`/`salary_max` become `null`
  (JSON) / empty (CSV/MD).
- `[MUST]` WHEN `--redact-fields "a,b,c"` is passed, THE system SHALL redact exactly
  that field list instead of the default set (override, not merge).
- `[MUST]` WHEN `--redact-fields` alone is passed (no `--redact`), THE system SHALL
  still redact — passing an explicit field list implies redaction is active.
- `[MUST]` WHEN any name in `--redact-fields` is not a real `offers` column, THE system
  SHALL `die()` with `code="invalid_value"` naming the invalid field(s) in `details`,
  instead of silently ignoring it or exporting unredacted.
- `[MUST]` The system shall apply the same redaction logic across `csv`, `json`, and
  `md` export formats.
- `[SHOULD]` Given `--redact` is not passed, When `applyr export` runs, Then behavior
  is byte-for-byte identical to the current implementation — redaction is strictly
  opt-in, never a new default.
- `[WONT]` Redacting fields outside the `offers` table (e.g. `offer_topics.detail` /
  `learning_gaps.gap_detail`) — out of scope for this iteration; `export` does not
  currently include those tables either.

#### README trust signals

- `[MUST]` The system shall add a `pylint.yml` CI status badge to `README.md`,
  positioned next to the existing `python-package.yml` badge.
- `[MUST]` WHEN this spec's tasks execute, THE actual test count SHALL be measured via
  `pytest --collect-only -q` and the existing `tests-576 passed` badge text SHALL be
  updated to that real, current number.
- `[WONT]` Integrating Codecov or any other external coverage service — explicitly
  rejected in the pre-spec decision to avoid a new dependency in the CI pipeline.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/constants.py` | MODIFY | `CALIBRATION_MIN_SAMPLE` 3→5 (only surviving piece of Feature A) |
| `applyr/cli.py` | MODIFY | Add `--redact`/`--redact-fields` to the `export` subcommand |
| `applyr/commands/workflow.py` | MODIFY | `cmd_export()` gains redaction logic |
| `README.md` | MODIFY | Add `pylint.yml` badge, correct test-count badge |
| `tests/test_commands.py` | MODIFY | Tests for `cmd_export` redaction (default set, custom list, invalid field, format parity) |

### Dependencies

- DB tables: `offers` (`compatibility_pct`, `status`, plus the fields named in
  `--redact`'s default set). No schema change, no migration.
- Config: `load_config()` for `threshold_apply` / `threshold_maybe` (existing pattern,
  same as `cmd_stats`).
- No new external dependency, no network call, no new CI service.

### Explicit assumptions

- We assume the calibration sample will be small (single-digit resolved offers) at
  first, possibly below the n=5 floor for every bucket → mitigated by AC-A2/AC-A5;
  the command is designed to say "not enough data yet" honestly rather than force a
  number.
- We assume `--redact-fields` values are compared case-sensitively against the real
  column names in `SCHEMA_SQL` → if false (user expects fuzzy matching), AC-B4's error
  message still surfaces the mismatch immediately rather than exporting unredacted data.

### Non-functional requirements

- Security/privacy: redaction must happen in-memory before any file write — never
  write the raw value and redact after, to avoid a partial-write race leaking data.
- Consistency: `applyr calibration`'s text/`--json` duality follows the exact pattern
  already used by `stats`/`trends`/`doctor` (see `docs/contracts.md`).

### Edge cases / risks

- User has zero offers with `status='offer'` ever → every bucket shows 0% (once past
  n=5) or "muestra insuficiente" — correct behavior, not a bug; the tool should not
  soften this.
- User passes `--redact-fields` with a field that exists but is meaningless to redact
  (e.g. `id`) → still honored (AC-B2 says "exactly that list"); no denylist of
  "fields you're not allowed to redact" — the user's call, not the tool's.
- `pytest --collect-only` count changes again the next time tests are added → the
  badge will go stale again; this is a known, accepted limitation of a hand-maintained
  badge (documented in HANDOFF as a gotcha to check before each release), not solved
  by this spec.

### Task breakdown (execution order)

1. [x] ~~`cmd_calibration()` in `analytics.py` + CLI routing + tests~~ — DISCARDED.
   Kept only: `CALIBRATION_MIN_SAMPLE` 3→5 in `applyr/constants.py` [S]
2. [x] Redaction logic in `cmd_export()` (default set, `--redact-fields` override,
   invalid field error, format parity across csv/json/md) + CLI routing + tests [M]
3. [x] ~~Document `applyr calibration --json` shape in `docs/contracts.md`~~ —
   DISCARDED, no new command to document
4. [x] README: add `pylint.yml` badge, refresh test-count badge — verified
   655 tests via `pytest --collect-only -q` (was stale at 576)

### Out of scope

- `[WONT]` Codecov / external coverage service integration.
- `[WONT]` Auto-apply, scraping, or any change to how `cv-master.md` is used for
  scoring — this spec is purely additive reporting/export/docs.
- `[WONT]` Redacting `offer_topics` or `learning_gaps` tables.
- `[WONT]` A dashboard or any UI beyond the existing CLI text/`--json` pattern.
