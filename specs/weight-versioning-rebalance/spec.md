# Spec: Weight Versioning + Rescore + Rebalanced Defaults

### Status: IMPLEMENTED
### Version: 1.2
### Target release: next minor (schema bump, additive — non-breaking for existing DBs)

---

## Recovered context

- **constitution.md**: SQLite via `db.py` migrations only (never edit `SCHEMA_SQL` in
  place), constants in `constants.py`, every failure ends in `die()`, `--json` keys are
  never renamed/removed, **PR budget 400 lines** (this repo's own limit — stricter than
  the 500-line global default), coverage gate 75%. Banned patterns directly relevant
  here: *"Never change `constants.py` DEFAULT_WEIGHTS without ADR"* and *"Never modify
  `templates/AGENT_INSTRUCTIONS.md` without human approval"* — both apply to this spec.
- **ADR 004 (Weighted scoring, Accepted)**: forbids changing `DEFAULT_WEIGHTS` or adding
  topics because no record exists of which weights produced a stored
  `compatibility_pct` — changing defaults silently breaks comparability of historical
  scores. This spec's entire premise is resolving that root cause, not bypassing it.
- **ADR 009 (this spec — renumbered from an initial draft of 005, which collided with the pre-existing 005-single-cli.md)**: supersedes ADR 004. Same RADAR already
  reasoned through in conversation with the project owner (4 alternatives: status quo,
  personal-config-only, versioned-weights + rescore + rebalance [chosen], backfill with
  guessed legacy weights [rejected — false precision]).
- **specs/scoring-confidence/spec.md** (precedent, v1.6.0/PR #61): same shape of change
  — additive schema migration (v7→v8), non-blocking warnings, derived-not-stored helper
  values, explicit "never influences `calculate_score()`" boundary, documented 400-line
  budget exception (696 lines). This spec follows the identical migration pattern
  (`MIGRATIONS[(8, 9)]`, `ALTER TABLE ... ADD COLUMN`, nullable, no backfill) and the
  identical PR-budget-exception precedent.
- **docs/contracts.md** Scoring/Database invariants: `calculate_score()` returns `int`
  in `[0,100]`; weights are normalized to sum `1.0` at load time, TOML stores relative
  integers; a topic absent from `[weights]` falls back to `DEFAULT_TOPIC_WEIGHT`. None of
  these invariants change — this spec adds a snapshot of the *input* weights, it does not
  touch the formula.
- **Real call site audited this session**: `applyr/commands/analytics.py:140`
  `_score_calibration()` (shipped in v1.6.0/PR #60) currently averages `compatibility_pct`
  across every `applied` offer into apply/maybe/low bands with no regard for what weights
  produced each score. This is the exact bug ADR 004 warns about, already shipped and
  live. This spec must fix it, not just prevent future instances.
- **Real edge case found reading `commands/core.py:621-635`**: `cmd_add` allows the
  caller to pass an explicit `compatibility_pct` override, bypassing `calculate_score()`
  and `topics` entirely (`compat_raw is not None` branch). When that branch is taken, no
  weights were used to produce the score — `weights_used` must be `NULL` in that case
  too, not just for pre-migration rows. Same for the `else: compatibility_pct = 0`
  branch (empty `topics`).
- **Engram**: no prior decisions found for "applyr weight versioning" / "applyr
  rescore".
- **Conversation history**: an external AI security/quality review of applyr raised this
  as item #13 ("I'd change the scoring weights — technical/experience over education").
  Web research (cited in conversation, 2025-26 recruiter surveys) supports the direction:
  experience/skills outweigh education for most roles. The project owner confirmed final
  numbers and every open question via two rounds of clarifying questions already — see
  Acceptance Criteria below for the settled values, not re-litigated here.

## What does it do? (observable behavior)

Today, `applyr add` computes `compatibility_pct` via `scoring.calculate_score(topics)`
using whatever `[weights]` are active in `applyr.toml` at that moment, and stores only
the resulting number — never which weights produced it. This means:
(a) the project cannot safely change `DEFAULT_WEIGHTS` for new users without silently
corrupting the meaning of every already-stored score across the install base, and
(b) `applyr stats`'s score-calibration bands already mix scores computed under
different (unknown, unrecorded) weight configs.

This feature:

1. Records a snapshot of the weights actually used, per offer, at the moment
   `compatibility_pct` is computed from `topics` — enabling safe, future weight changes
   without repeating this problem.
2. Adds `applyr rescore <id>` to recompute one offer's `compatibility_pct` (from its
   already-judged `offer_topics`, never re-evaluating fit) under the *current* weights,
   for users who update their config or upgrade to new defaults and want a specific
   offer's score to reflect that.
3. Fixes `applyr stats`'s score-calibration bands to exclude offers with unknown
   (pre-migration or override-computed) weights, rather than silently mixing them.
4. Rebalances `DEFAULT_WEIGHTS` — now safe to do because of (1) — reflecting that
   technical fit and experience should carry more signal than education for most roles
   (project-owner decision, informed by 2025-26 hiring-practice research).
5. Records the decision as `docs/adr/009-weight-versioning-and-rebalance.md`, superseding
   `docs/adr/004-weighted-scoring.md` per this project's ADR convention (old ADR's body
   stays immutable; only its header gains a "Superseded by" pointer).

## Acceptance criteria

### Schema & migration

- [MUST] `SCHEMA_VERSION` bumps from 8 to 9. `MIGRATIONS[(8, 9)] = ["ALTER TABLE offers ADD COLUMN weights_used TEXT"]`, following the exact pattern of the existing `(7, 8)` migration in `db.py` (nullable, no default, no backfill).
- [MUST] `SCHEMA_SQL`'s `offers` `CREATE TABLE IF NOT EXISTS` includes `weights_used TEXT` so a fresh install lands on schema v9 directly with the column present.
- [MUST] `weights_used` stores the **raw, pre-normalization integer weights dict** (e.g. `{"tech_stack": 35, "experience": 35, "projects": 15, "education": 5, "english": 5, "cultural_fit": 5}`), JSON-encoded via `json.dumps(..., sort_keys=True)` — matching how the TOML itself stores relative integers, never fractions (`contracts.md` invariant).
- [MUST] `weights_used` reflects the caller's **merged, effective config** (`config["weights"]` as returned by `load_config()` — defaults merged with the user's `applyr.toml`), not the global `DEFAULT_WEIGHTS` constant — it must describe what was *actually* used for that specific offer.
- [WONT] No backfill for existing rows. They read back as `NULL` and are permanently labeled "weights unknown," per explicit project-owner decision — there is no reliable way to know what a user's `applyr.toml` looked like at some point in the past.

### `applyr add` — capture

- [MUST] WHEN `cmd_add` computes `compatibility_pct` via the `elif topics: compatibility_pct = calculate_score(topics)` branch (`commands/core.py:632-633`), THE system SHALL also serialize `config["weights"]` into `weights_used` and persist both together in the same `INSERT INTO offers` statement.
- [MUST] WHEN `cmd_add` takes the explicit-override branch (`compat_raw is not None`, `commands/core.py:625-631`) THE system SHALL store `weights_used = NULL` — no weights were used to derive an externally supplied score.
- [MUST] WHEN `cmd_add` takes the empty-topics branch (`else: compatibility_pct = 0`, `commands/core.py:635`) THE system SHALL store `weights_used = NULL`.
- ~~[MUST] Existing `--json` keys on `add`'s output are not renamed or removed. `weights_used` is added as a new top-level key.~~ **CORRECTED then RESOLVED (BUG-001, adversarial-test 2026-08-15):** this AC assumed `cmd_add`/`applyr add --json` already existed. It did not — `add` never had a `--json` mode, `cli.py` never forwarded the flag, confirmed via `build/lib/applyr/commands/core.py` predating this PR. Not a regression from this spec; the AC was written on a false premise. Project owner chose to close the gap in this same PR rather than defer it: `cmd_add` gained `as_json: bool = False`, `cli.py` now forwards `--json`, and a JSON payload (`id`, `title`, `company`, `compatibility_pct`, `weights_used`, `status`, `follow_up_date`, `skill_gaps`, `recommendation`, `confidence`, `topics`, `why_match`, `biggest_weakness`) is emitted — this is a brand-new contract, not a change to an existing one, so constitution.md's "never rename/remove --json keys" isn't in tension with it. Also fixed in the same pass: the "topic not in config" warning was a bare `print()` to stdout (would have corrupted this exact payload) — now routed through the existing `warn()` helper, which is a no-op in `--json` mode by this codebase's existing `error()`/`warn()` design (not redirected to stderr — genuinely suppressed, confirmed by reading `errors.py`). Tests: `tests/test_cli_routing.py::TestGlobalFlags::test_json_flag_add` and `test_json_flag_add_unknown_topic_warning_does_not_break_json`; the adversarial-tester's original bug-proving test was updated in place to guard the fix (`tests/test_weight_versioning_adversarial.py::TestAddJsonContractGap::test_add_honors_json_flag`).

### `applyr rescore <id>` — new command

- [MUST] `applyr rescore <id>` loads the offer's existing `offer_topics` rows (score/detail/confidence, unchanged — this command never re-evaluates fit) and recomputes `compatibility_pct` via `scoring.calculate_score()` using the **current** effective `config["weights"]`.
- [MUST] WHEN the target offer has zero `offer_topics` rows (never scored via `add` with `topics`), THE system SHALL `die()` with a clear `code="not_found"`-style error (e.g. `code="no_topics"`, message naming the offer id) rather than silently writing a `0` score.
- [MUST] WHEN the target offer id does not exist, THE system SHALL `die()` with `code="not_found"`, same shape as `cmd_show`'s existing not-found handling.
- [MUST] On success, updates `compatibility_pct` and `weights_used` on that offer (same serialization rule as `add`) and prints old score → new score (e.g. `Rescored offer #42: 74% → 81% (weights updated)`, or `... 74% → 74% (no change)` when the recomputed value is identical).
- [MUST] Supports `--json`, output shape `{"id": int, "old_compatibility_pct": int, "new_compatibility_pct": int, "weights_used": {...}}` — consistent with how `cmd_update` already returns structured confirmation for other mutating commands.
- [MUST] Wired into `cli.py` routing, `--help` output, and the command reference table in both `templates/AGENT_INSTRUCTIONS.md` and `README.md`.
- [WONT] No bulk `applyr rescore --all` in this iteration (explicit project-owner decision — single-id only for now).

### `applyr stats` — score calibration fix

- [MUST] `_score_calibration()` (`commands/analytics.py:140`) SHALL only include offers where `weights_used IS NOT NULL` when building the apply/maybe/low bands.
- [MUST] The human-readable `stats` output reports how many offers were excluded from calibration for having unknown weights (e.g. `N offers excluded from calibration (scored before weight tracking or via manual override)`), so the smaller sample size is never silently hidden.
- [MUST] The `--json` output of `stats` includes an `excluded_unknown_weights` count alongside `score_calibration`.
- [SHOULD] `applyr compare` (`commands/analytics.py:633`) — which displays offers side by side rather than averaging them — surfaces each offer's `weights_used` (or "unknown") in its own row, so two offers with different weight bases are never visually implied to be apples-to-apples without the reader being able to tell.

### `applyr show` — display

- [MUST] `cmd_show`'s query becomes `SELECT * FROM offers ...` (unchanged — already `SELECT *`), and both human and `--json` output surface `weights_used`.
- [MUST] Human output adds a line near the existing `Compatibility` field, e.g. `Scored Under : tech_stack=35, experience=35, projects=15, education=5, english=5, cultural_fit=5` when present, or `Scored Under : unknown (pre-v9 or manual override)` when `NULL`.
- [MUST] `--json` output parses the stored JSON text back into a nested object (`"weights_used": {...} | null`) — never a double-encoded JSON string.

### Rebalanced `DEFAULT_WEIGHTS`

- [MUST] `applyr/constants.py`'s `DEFAULT_WEIGHTS` becomes (project-owner confirmed, sums to 100, no new topic — seniority-fit folds into `experience`, whose rubric already covers "Wrong seniority/industry" at its 50-point anchor):
  ```python
  DEFAULT_WEIGHTS = {
      "tech_stack": 35,
      "experience": 35,
      "projects": 15,
      "education": 5,
      "english": 5,
      "cultural_fit": 5,
  }
  ```
- [MUST] `config.py`'s `TOML_TEMPLATE` `[weights]` section is updated to match (this is what a fresh `applyr init` writes for new users).
- [MUST] `templates/AGENT_INSTRUCTIONS.md`'s scoring rubric table (topic weight column) is updated to match — **this file is banned-pattern-protected in `constitution.md` ("never modify without human approval")**; the PR must call this out explicitly and the project owner must review this specific diff before merge, not just approve the PR as a whole.
- [WONT] No new `seniority` topic. No change to `offer_topics` schema. No change to `threshold_apply`/`threshold_maybe`.

### ADR

- [MUST] `docs/adr/009-weight-versioning-and-rebalance.md` created, Status: Accepted, containing: Context (restating ADR 004's constraint), Decision (weights_used snapshot + rescore + rebalance), Consequences (positive: defaults can now change safely going forward; negative: extra schema column, `rescore` must not be confused with re-judging fit; neutral: legacy rows permanently unlabeled, no backfill), Alternatives considered (the 4 already reasoned through), and an explicit "Supersedes ADR 004" line.
- [MUST] `docs/adr/004-weighted-scoring.md`'s header gains a `**Superseded by:** [ADR 009](009-weight-versioning-and-rebalance.md)` line. Its body (Context/Decision/Consequences/Alternatives) is **not** edited — ADRs are immutable once accepted per this project's convention.
- [MUST] `docs/contracts.md`'s Database invariants section gains a line documenting `weights_used`: JSON snapshot of the weights dict used to compute `compatibility_pct`, `NULL` for pre-v9 offers and for offers scored via explicit `compatibility_pct` override.

## Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | `SCHEMA_VERSION` 8→9, `MIGRATIONS[(8,9)]`, `SCHEMA_SQL` offers table |
| `applyr/commands/core.py` | MODIFY | `cmd_add` captures `weights_used`; `cmd_show` displays it |
| `applyr/commands/analytics.py` | MODIFY | `_score_calibration()` excludes `NULL` rows; `cmd_compare` surfaces `weights_used` per offer; new `cmd_rescore` |
| `applyr/cli.py` | MODIFY | Route `rescore` subcommand, `--help` text |
| `applyr/constants.py` | MODIFY | `DEFAULT_WEIGHTS` rebalanced |
| `applyr/config.py` | MODIFY | `TOML_TEMPLATE` `[weights]` section |
| `applyr/templates/AGENT_INSTRUCTIONS.md` | MODIFY (needs explicit human review — banned-pattern file) | Rubric table weights, command reference row for `rescore` |
| `README.md` | MODIFY | Command reference row for `rescore` |
| `docs/adr/009-weight-versioning-and-rebalance.md` | CREATE | New ADR, supersedes 004 |
| `docs/adr/004-weighted-scoring.md` | MODIFY (header only) | "Superseded by" pointer |
| `docs/contracts.md` | MODIFY | New Database invariant for `weights_used` |
| `tests/test_db.py` (or equivalent migration test file — verify exact name) | MODIFY | Migration v8→v9 coverage |
| `tests/test_scoring.py` or `tests/test_cli_routing.py` | MODIFY | `weights_used` capture on `add`, override/empty-topics NULL cases |
| New `tests/test_rescore.py` | CREATE | `rescore` command tests |
| `tests/test_analytics.py` (or equivalent — verify exact name) | MODIFY | Calibration exclusion test |

## Dependencies

- DB: `offers` table (new nullable column), `offer_topics` table (read-only, unchanged) via existing `get_conn()`.
- No new external dependency — `json` is already used throughout (`stdlib`-only philosophy preserved).
- `scoring.calculate_score()` — reused as-is, not modified (constitution.md banned pattern respected: the formula itself never changes, only its configured inputs).

## Explicit assumptions

- We assume `config["weights"]` at `add`-time is the correct thing to snapshot (not `DEFAULT_WEIGHTS`) → if this is wrong, every stored snapshot for users with custom `applyr.toml` would misrepresent what was actually used, defeating the entire purpose.
- We assume "no bulk rescore" is acceptable for this iteration → if a user changes weights and wants everything updated at once, they currently must call `rescore` per id; documented as a known limitation, not silently missing.
- We assume `_score_calibration`'s existing bucket definitions (apply/maybe/low) don't otherwise change, only their input filter → if calibration semantics need to change too, that's a separate spec.

## Non-functional requirements

- Performance: `rescore` and the `weights_used` capture add one `json.dumps`/`json.loads` call each — negligible, no measurable target needed for a local SQLite CLI.
- Backward compatibility: a DB at schema v9 read by an older applyr build already triggers the existing forward-compat `doctor` note (`db.py`'s `db_version > SCHEMA_VERSION` path) — no new behavior needed there.
- Security: no new input surface beyond existing `topics`/config validation; `weights_used` is server-computed (from `load_config()`), never taken directly from user-supplied JSON on `add`.

## Edge cases / risks

- An offer with `weights_used` set, then the user edits `applyr.toml` again before calling `rescore` — expected and correct: `rescore` always uses *current* config, that's its entire purpose.
- A topic present in stored `offer_topics` but no longer present in `config["weights"]` (e.g. a topic was removed from `[weights]` in the TOML) — `calculate_score()` already handles this via `DEFAULT_TOPIC_WEIGHT` fallback (existing behavior, unchanged); `rescore`'s snapshot will reflect whatever `calculate_score()` actually used.
- `stats` calibration sample size shrinking sharply right after this ships (all pre-migration offers excluded) — mitigated by the required "N excluded" message so it's never a silent, confusing drop.
- Risk: forgetting a call site that averages `compatibility_pct` across offers besides `_score_calibration`. Mitigation: `grep -rn "compatibility_pct" applyr/` during implementation to confirm `cmd_compare`, `cmd_list --sort`, `pipeline --min-score`, and `cv_stats.py` don't perform any cross-offer averaging (display/sort/filter of individual values is fine and out of scope; only aggregation across offers is the concern).

## Task breakdown (execution order)

1. [x] `db.py`: schema v8→v9 migration + `SCHEMA_SQL` update + migration test. [S]
2. [x] `scoring`/`core.py`: capture `weights_used` in `cmd_add` (all three branches: computed / override / empty). [M]
3. [x] `core.py`: `cmd_show` displays `weights_used` (human + `--json`). [S]
4. [x] `analytics.py`: new `cmd_rescore` command + tests. [M]
5. [x] `cli.py`: route `rescore`, help text. [S]
6. [x] `analytics.py`: fix `_score_calibration` exclusion + `cmd_compare` display + tests. [M]
7. [x] `constants.py` + `config.py`: rebalance `DEFAULT_WEIGHTS` + `TOML_TEMPLATE`. [S]
8. [x] `docs/adr/005-...md` (new) + `docs/adr/004-...md` (header only) + `docs/contracts.md`. [S]
9. [x] `templates/AGENT_INSTRUCTIONS.md` + `README.md` — **pause here for explicit human review before committing**, per banned-pattern rule. [S]
10. [x] Full `grep -rn "compatibility_pct"` audit for missed aggregation call sites (Edge cases / risks above). [S] — found 2 additional cross-offer averages not named in this spec's own audit list (`cmd_stats`'s overall `avg_compatibility_pct`, `cmd_summary`'s weekly `avg_compat`). Project owner approved fixing both in this same PR (single-PR pre-approval already covers going over budget). [S] Fixed: both now filter `weights_used IS NOT NULL`, report an `*_excluded_unknown_weights` count (human + `--json`), tests added in `tests/test_commands.py::TestAvgCompatExcludesUnknownWeights`, new invariant recorded in `docs/contracts.md`.

### Budget exception

`constitution.md`'s PR budget was raised from 400 to 500 lines (project-owner decision,
2026-08-15, matching this owner's other projects' global default) specifically ahead of
this feature. Expected total: schema migration + new command + calibration fix + compare
display + rebalanced defaults + ADR + contracts doc + AGENT_INSTRUCTIONS.md + README +
~4 test files may still exceed even 500 lines, similarly to PR #61 (696 lines, documented
exception). **Pre-approved by the project owner: ship as a single PR regardless of size**
— do not split into chained PRs for this feature. Document the exact final line count and
this justification in the PR body's budget checklist line.

## Out of scope

- `[WONT]` Bulk `applyr rescore --all`.
- `[WONT]` New `seniority` scoring topic.
- `[WONT]` Backfilling `weights_used` for pre-migration offers.
- `[WONT]` Changing `threshold_apply`/`threshold_maybe` values.
- `[WONT]` Changing `offer_topics` schema or the `calculate_score()` formula itself.
- `[WONT]` Retroactive auto-rescore of all offers on migration.
