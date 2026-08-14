# Spec: Topic Confidence + Required Evidence

### Status: IMPLEMENTED
### Version: 1.0
### Target release: v1.6.0 (patch/minor — additive, non-breaking)

---

## Recovered context

- **constitution.md**: SQLite via `db.py` migrations only (never edit `SCHEMA_SQL` in place for existing installs), constants in `constants.py`, every failure ends in `die()`, `--json` keys are never renamed/removed, PR budget **400 lines** (this repo's own limit, stricter than the 500-line global default).
- **ADR 003 (No LLM calls)**: applyr never calls a model. This feature does not add one — it only validates and aggregates values the calling agent already submits. No conflict.
- **ADR 004 (Weighted scoring)**: `scoring.py`'s `calculate_score()` formula is a banned-pattern-protected file — changing it requires an ADR. This feature does **not** touch it: confidence is metadata stored alongside a topic score, never an input to the weighted-mean calculation. `compatibility_pct` is computed exactly as today.
- **Engram**: no prior decisions found for "applyr scoring confidence evidence hybrid".
- **This session**: found and fixed a real bug (PR #59) caused by two parallel representations of the same concept (`threshold` vs `threshold_apply`/`threshold_maybe`) silently disagreeing. This spec deliberately avoids repeating that shape — see AC-04.
- **Corrected assumption from this conversation**: the free-invented `CONFIDENCE: high|medium|low` line lives in `AGENT_INSTRUCTIONS.md`'s Step 3 "Agent response format" (right after `applyr add`), **not** in `cv.py`'s `cv review`/`cv review-blind` prompt templates (verified: no `CONFIDENCE` string exists anywhere in `cv.py`). Scope is corrected accordingly — this spec does not touch `cv.py`.

## What does it do? (observable behavior)

Today, `applyr add` accepts a `topics` JSON where each topic is `{"score": int, "detail": str}`. `detail` is optional and unvalidated — an agent can submit a bare score with zero justification, and nothing about how *certain* that score is gets captured anywhere. Separately, `AGENT_INSTRUCTIONS.md` tells the agent to write a `CONFIDENCE: high|medium|low` line in its own reply after `add`, but that value is invented fresh each time with nothing behind it.

This feature:
1. Adds an optional `confidence` field per topic (`"high" | "medium" | "low"`), validated and persisted.
2. Warns (non-blocking) when a topic has a `score` but no `detail` — evidence becomes an expected, surfaced norm without becoming a breaking requirement.
3. Derives one overall confidence per offer from the weakest per-topic confidence provided, computed on demand (never stored redundantly).
4. Surfaces both (per-topic + derived overall) in `applyr add`, `applyr show`, and their `--json` output.
5. Updates `AGENT_INSTRUCTIONS.md` so the agent is told to use the derived value in its response format instead of inventing one.

## Acceptance criteria

### Schema & validation

- [MUST] `SCHEMA_VERSION` bumps from 7 to 8. `MIGRATIONS[(7, 8)] = ["ALTER TABLE offer_topics ADD COLUMN confidence TEXT"]`, following the exact pattern of the existing `(3, 4)` migration (`language` column: nullable, no default, no backfill).
- [MUST] `SCHEMA_SQL`'s `offer_topics` `CREATE TABLE IF NOT EXISTS` includes `confidence TEXT` so a fresh install lands on schema v8 directly with the column present.
- [MUST] A new `VALID_CONFIDENCE_LEVELS = ("high", "medium", "low")` constant is added (same file/placement convention as `VALID_SALARY_PERIODS` in `constants.py`).
- [MUST] WHEN `cmd_add` receives a topic with a `confidence` value NOT in `VALID_CONFIDENCE_LEVELS`, THE system SHALL `die()` with `code="invalid_value"`, `details={"field": "confidence", "topic": <topic_key>, "value": <bad_value>, "valid": [...]}`, following the exact message/code shape of the existing `salary_period` validation in `commands/core.py`.
- [MUST] WHEN a topic omits `confidence`, THE system SHALL store `NULL` — never a fabricated default (no silent "medium").
- [MUST] WHEN a topic has a `score` present but `detail` missing or empty, THE system SHALL print a non-blocking warning (same call shape as the existing `"Warning: topic '{key}' not in config"` line) and SHALL still insert the row — this must never call `die()`.
- [WONT] No top-level `confidence` key is accepted on the `add` payload (only per-topic, inside `topics`). If an agent sends one anyway, it is silently ignored, consistent with how every other unrecognized top-level key already behaves.
- [WONT] No backfill of `confidence` for existing `offer_topics` rows. They read back as `NULL`.

### Derivation

- [MUST] The system SHALL provide a pure function (e.g. `_derive_confidence(topics: dict) -> str`) that returns the weakest confidence among topics that provided one, using the order `low < medium < high`.
- [MUST] IF no topic among those provided included a `confidence` value THEN the derived result SHALL be `"unknown"` — never defaulted to `"medium"` or omitted.
- [MUST] This function SHALL live outside `scoring.py` (e.g. in `commands/core.py`, alongside the existing `_get_recommendation` helper) and SHALL NOT be called from `calculate_score()` — confidence must never influence `compatibility_pct`.
- [SHOULD] The same derivation logic is reused (not reimplemented) everywhere the overall confidence is displayed (`add`, `show`) — a single function, multiple call sites.

### Display — `applyr add`

- [MUST] Human-readable output prints each topic's confidence next to its score/detail line when present (e.g. `✓ Tech Stack: 85% (high confidence) — Knows Python+FastAPI`), and omits the "(... confidence)" suffix when a topic has no confidence value, rather than printing "(unknown confidence)" on every line that never asked for it.
- [MUST] Human-readable output prints one derived overall confidence line near the existing recommendation banner (e.g. `CONFIDENCE: MEDIUM`), including when it is `UNKNOWN`.
- [MUST] `--json` output includes `confidence` per topic in the existing topic breakdown structure, plus one new top-level `"confidence"` key holding the derived value (`"high" | "medium" | "low" | "unknown"`).
- [MUST] Existing `--json` keys are not renamed or removed (constitution.md banned pattern).

### Display — `applyr show`

- [MUST] The `SELECT topic, score, detail FROM offer_topics` query in `cmd_show` becomes `SELECT topic, score, detail, confidence FROM offer_topics`.
- [MUST] Human output shows per-topic confidence the same way `add` does.
- [MUST] Human output shows the derived overall confidence (reusing the same function from the Derivation section) near the existing `Compatibility` field.
- [MUST] `--json` output for `show` includes `confidence` in each topic dict and one top-level derived `"confidence"` key — same shape as `add`'s JSON, so the two commands cannot disagree about what fields exist.

### Documentation

- [MUST] `AGENT_INSTRUCTIONS.md`'s scoring rubric (Step 3) documents the new `confidence` field: what it means, the three valid values, and that it's optional but expected.
- [MUST] `AGENT_INSTRUCTIONS.md`'s scoring rubric reinforces that `detail` is expected for every scored topic (not hard-enforced, but no longer presented as an afterthought).
- [MUST] `AGENT_INSTRUCTIONS.md`'s "Agent response format" section (the one with `CONFIDENCE: high | medium | low`) is reworded to instruct the agent to use the derived value `applyr add` returns, instead of inventing one.
- [WONT] ~~A new ADR~~ — corrected during implementation. `docs/adr/README.md`'s own criteria ("When to write one") lists: replacing the storage engine, adding a dependency/network/LLM call, changing the scoring formula or `DEFAULT_WEIGHTS`, or redesigning the CLI/`--json` shape. This feature does none of those — it adds optional fields, never renames/removes existing ones, and `scoring.py` is untouched. Per the same doc: "Routine work does not need one." Writing one anyway would violate the project's own convention as much as skipping a required one would.
- [COULD] `README.md`'s Features list gets one line, consistent with how the score-calibration feature (PR #60) was documented — deferred if the PR is already near budget.

## Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | `SCHEMA_VERSION` 7→8, new migration entry, `offer_topics` `CREATE TABLE` gets `confidence TEXT` |
| `applyr/constants.py` | MODIFY | Add `VALID_CONFIDENCE_LEVELS` |
| `applyr/commands/core.py` | MODIFY | Validate `confidence` in `cmd_add`'s topic loop, warn on missing `detail`, add `_derive_confidence()`, update `cmd_add`/`cmd_show` display + JSON |
| `applyr/templates/AGENT_INSTRUCTIONS.md` | MODIFY | Document `confidence`, reinforce `detail`, reword response-format CONFIDENCE line |
| `README.md` | MODIFY (optional, budget-permitting) | One Features-list line |
| `tests/test_commands.py` or a new `tests/test_confidence.py` | MODIFY/CREATE | Coverage for every `[MUST]` AC above |

## Dependencies

- DB table: `offer_topics` (existing, `offers` unaffected structurally).
- No external APIs (ADR 003).
- No new CLI flags (`cli.py` untouched — `confidence` travels inside the existing `topics` JSON blob).
- Reuses: `REPLY_STATUSES`-style "single constant, multiple call sites" pattern; `die()`/`warn()` from `errors.py`; the `salary_period` validation shape as the template for `confidence` validation.

## Explicit assumptions

- We assume no top-level `confidence` key is meaningful on `add`'s payload → if this turns out to be wanted later, it's a strictly additive follow-up, not a breaking change to what's shipped here.
- We assume the derived confidence should never be persisted on `offers` → if a future feature needs to query/filter by confidence at scale without joining `offer_topics`, that's a follow-up migration, not a reason to duplicate the source of truth now.
- We assume "low" is the correct minimum-wins semantics for deriving overall confidence (matching how `threshold_maybe`/`threshold_apply` bands already work: the weakest signal decides) → if the real want is an average/majority instead, that changes AC "Derivation" only, isolated from everything else.

## Non-functional requirements

- Performance: negligible — one extra nullable TEXT column, one extra Python comparison per topic at insert/read time. No new query loops beyond what `add`/`show` already run.
- Security: no new input surface beyond one more validated enum field; same parameterized-query pattern as every other insert in `commands/core.py`.
- Backward compatibility: fully additive. Any agent/script that never sends `confidence` continues to work exactly as before — `detail`-missing only warns, never blocks.

## Edge cases / risks

- **Risk**: an agent starts sending `confidence: "high"` on every topic regardless of actual certainty (gaming the signal, similar to ADR 004's "garbage in, garbage out" caveat about scores). **Mitigation**: none built into this feature — same limitation applyr already accepts for scores themselves per ADR 004; not a regression, and out of scope to solve here.
- **Risk**: mixed old/new data — an offer added before this ships has `confidence = NULL` on every topic row; `_derive_confidence` must treat that offer as `"unknown"`, not crash or default to `"medium"`. Covered by AC "Derivation" and needs an explicit test.
- **Risk**: this is a DB migration touching a real, currently-in-use local database (~200+ offers per HANDOFF.md). **Mitigation**: the migration is additive-only (`ADD COLUMN`, no data transformation, no `UPDATE`), matching the lowest-risk category of migration already in `MIGRATIONS` (see `(3, 4)`). No `UPDATE`/backfill statement is part of this migration, by design (see AC "Schema & validation" — no backfill).

## Task breakdown (execution order)

- [x] 1. `db.py`: bump `SCHEMA_VERSION`, add migration `(7, 8)`, update `SCHEMA_SQL`. [S]
- [x] 2. `constants.py`: add `VALID_CONFIDENCE_LEVELS`. [S]
- [x] 3. `commands/core.py`: validate `confidence` in `cmd_add`'s topic loop (die on invalid), warn on missing `detail`, insert `confidence` column. [S]
- [x] 4. `commands/core.py`: add `_derive_confidence()` helper + unit tests directly against it. [S]
- [x] 5. `commands/core.py`: wire per-topic + derived confidence into `cmd_add`'s human output (no `--json` mode exists for `add` — confirmed during implementation, not part of the real contract). [M]
- [x] 6. `commands/core.py`: wire the same into `cmd_show`'s query, human + JSON output. [M]
- [x] 7. Tests: schema migration test (fresh DB lands on v8; a v7 DB migrates cleanly and old rows read back as `NULL`/`"unknown"`), validation tests (invalid confidence dies, missing detail warns not dies), derivation tests (weakest-wins, all-missing → unknown), `add`/`show` output shape tests. 50/50 passing (`tests/test_confidence.py` + `tests/test_db.py`), plus `tests/test_commands.py` (57/57) checked for regressions. [M]
- [x] 8. `AGENT_INSTRUCTIONS.md`: document the new field, reword the response-format CONFIDENCE line. [S]
- [x] 9. ~~ADR~~ — skipped, see "Documentation" AC. [S]
- [x] 10. `README.md`: one line. [S]
- [x] 11. Full test suite (597/597) + `simplify-lean` — no changes needed, deliberate design choices preserved. [S]
- [x] 12. Traceability matrix (above) + `/adversarial-test` — **PASS**, 10/10 hypotheses held, 0 defects. The tester also wrote 10 hardening tests (`tests/test_confidence_adversarial.py`) closing real gaps in the original suite (multi-topic atomicity, real v7-schema migration, empty-string `detail`). Kept both test files. [M]

### Budget exception

Total diff: **696 lines** (188 tracked code/docs + 508 in new files: spec.md 166, test_confidence.py 123, test_confidence_adversarial.py 219) — over both `constitution.md`'s local 400-line budget and the global 500-line rule in `~/.claude/CLAUDE.md`. Deiby explicitly approved a documented exception, re-confirmed after the number was corrected upward twice during this session (first found missing spec.md from the count, then a `/code-review` pass added a few more lines while fixing 2 real bugs it found). This is one logical work unit: the feature, its spec, and the verification its own migration risk mandatorily triggered (`/adversarial-test`, whose findings became `tests/test_confidence_adversarial.py`) — splitting the tests from the feature that motivated them would separate evidence from the claim it supports.

## Traceability Matrix (SDD Step 6a)

| AC | Priority | Description | Test | Implementation | Status |
|----|----------|--------------|------|-----------------|--------|
| AC-01 | MUST | Migration (7,8) adds `confidence` to `offer_topics` | `TestMigrationV7ToV8` (test_db.py) | db.py:9, db.py:54 | PASS |
| AC-02 | MUST | Fresh install `SCHEMA_SQL` includes `confidence TEXT` | `TestInitDb.test_creates_tables` (pre-existing, still passes) + manual smoke test this session | db.py:107 | PASS |
| AC-03 | MUST | `VALID_CONFIDENCE_LEVELS` enum exists | `TestConfidenceValidation.test_valid_confidence_is_accepted` | constants.py:72 | PASS |
| AC-04 | MUST | Invalid `confidence` → `die(code="invalid_value")` | `test_invalid_confidence_dies` | core.py:715-719 | PASS |
| AC-05 | MUST | Missing `confidence` → stored `NULL`, never a default | `test_missing_confidence_is_stored_as_null_not_a_default` | core.py:714 (`values.get("confidence")`, no default) | PASS |
| AC-06 | MUST | Missing `detail` with a score → warning, not `die()` | `test_missing_detail_warns_but_does_not_die` | core.py:720-721 | PASS |
| AC-07 | MUST | `_derive_confidence`: weakest per-topic value wins | `TestDeriveConfidence` (6 tests) | core.py:131-144 | PASS |
| AC-08 | MUST | No topic provided confidence → `"unknown"` | `test_no_topics_provided_confidence_is_unknown`, `test_empty_list_is_unknown` | core.py:141-142 | PASS |
| AC-09 | MUST | Derivation lives outside `scoring.py`, never feeds `calculate_score()` | verified by inspection — `scoring.py` diff is empty this session | core.py:131 (not scoring.py) | PASS |
| AC-10 | MUST | `add` human output: per-topic confidence suffix | `test_add_prints_per_topic_and_derived_confidence` | core.py:176-188, 758-761 | PASS |
| AC-11 | MUST | `add` human output: derived overall confidence line | `test_add_prints_per_topic_and_derived_confidence` | core.py:759 | PASS |
| AC-12 | N/A | `add --json` includes confidence | — | — | **N/A — corrected during implementation: `cmd_add` has no `--json` mode at all (verified: no `as_json` parameter exists on the function). Nothing to wire.** |
| AC-13 | MUST | Existing `--json` keys not renamed/removed | full suite green (597/597), no key removed/renamed in any diff | core.py (show's JSON dict) | PASS |
| AC-14 | MUST | `show`'s query includes `confidence` | `test_show_json_includes_derived_confidence` | core.py (SELECT in `cmd_show`) | PASS |
| AC-15 | MUST | `show` human output: per-topic confidence | manual smoke test (this session, captured in conversation) | core.py:176-188 (`_topic_display_suffix` reused) | PASS |
| AC-16 | MUST | `show` human output: derived overall confidence | manual smoke test | core.py:981 | PASS |
| AC-17 | MUST | `show --json`: confidence per topic + top-level derived | `test_show_json_includes_derived_confidence`, `test_show_json_confidence_is_unknown_when_never_provided` | core.py (JSON branch of `cmd_show`) | PASS |
| AC-18 | MUST | `AGENT_INSTRUCTIONS.md` documents `confidence` | manual doc review | AGENT_INSTRUCTIONS.md:198-204 | PASS |
| AC-19 | MUST | `AGENT_INSTRUCTIONS.md` reinforces `detail` expected | manual doc review | AGENT_INSTRUCTIONS.md:198-199 | PASS |
| AC-20 | MUST | Response-format `CONFIDENCE` line reworded to use derived value | manual doc review | AGENT_INSTRUCTIONS.md (Agent response format section) | PASS |

Every `[MUST]` AC has a test or an explicit inspection-based verification, and an implementation citation. AC-12 is the one deviation from the original spec, documented above (Step 6b below) rather than silently dropped.

## Drift check (SDD Step 6b)

- **Scope drift**: none — no functions/endpoints exist in code that aren't in the spec.
- **Coverage gap**: AC-12 (`add --json`) has no test because the premise was wrong — `cmd_add` never had a `--json` mode to extend. This is intentional scope correction, not a gap. AC-15/AC-16 (human `show` output) are covered by manual smoke tests captured in this session's transcript rather than automated `capsys` tests — acceptable since `TestAddAndShowSurfaceConfidence` already exercises the same `_topic_display_suffix`/`_derive_confidence` functions from the `add` side with automated tests, and `show`'s JSON path (which uses the same underlying data) is automated.
- **Behavior drift**: none found vs. the (corrected) spec.
- **Files modified outside "Affected files"**: none.

## Out of scope

- `[WONT]` Full deterministic requirement extraction (structured `Requirement`/`Skill` objects) — that's the doc's larger P1 vision, explicitly deferred by Deiby's decision this session.
- `[WONT]` `cv.py` / `cv review` / `cv review-blind` changes — corrected scope, see "Recovered context."
- `[WONT]` Backfilling confidence for historical offers via LLM re-evaluation.
- `[WONT]` A numeric/float confidence representation.
- `[WONT]` Cross-model confidence variance tracking (doc's P1 item #15) — separate, larger feature.
