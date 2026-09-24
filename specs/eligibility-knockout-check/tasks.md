# Tasks: Eligibility / Knockout Check

Chained PRs (500-line budget): **PR 1** = T1–T2 · **PR 2** = T3–T6 · **PR 3** = T7–T9.

## PR 1 — Evaluator (pure, no CLI wiring)
- [x] T1 — ADR-017 + constants (tolerance, CEFR order, language/section aliases) [S] — implements AC-12 (contract) — Depends on: none
  - Done when: `docs/adr/017-eligibility-knockout-check.md` is written; constants are importable.
- [x] T2 — `applyr/eligibility.py`: profile parser, `validate_requirements()`, `evaluate()` + `tests/test_eligibility.py` [M] — implements AC-03..09, AC-E1, AC-E4 — Depends on: T1
  - Done when: unit tests cover pass/warn/block/unknown per item, EN/ES section and language names, native ≥ C2, remote never blocks, and invalid blocks raise with the field name.

## PR 2 — Storage and recommendation
- [x] T3 — Schema v15 migration + `SCHEMA_SQL` columns [S] — implements AC-01, AC-E3 — Depends on: PR 1
  - Done when: a v14 DB migrates with both columns NULL; a fresh DB has them; `test_db` passes.
- [x] T4 — `recommendation_for()` eligibility-aware (reason via `eligibility.block_reason()`) [S] — implements AC-10, AC-11, AC-12 — Depends on: T3
  - Done when: a `block` result returns `low_match` for a score of 95; two-arg calls unchanged.
- [x] T5 — `add`: validate before insert, evaluate, store, print; `show` / list / search expose `eligibility` + `eligibility_block` [M] — implements AC-01, AC-02, AC-10, AC-13, AC-14, AC-E1, AC-E2 — Depends on: T4
  - Done when: CLI tests show an invalid block stores nothing (`invalid_eligibility`), a blocked 95% offer reads `low_match` in add/show/list/search text and `--json`, and a missing CV master yields all-`unknown`.
- [x] T6 — `pipeline`, `summary`, calibration, `rescore` (re-evaluates), `applyr next` warning [M] — implements AC-10, AC-15, AC-16, AC-17 — Depends on: T5
  - Done when: a blocked offer is `low_match` in pipeline/summary/calibration; editing the profile then `rescore` flips the result; `next` names the blocking item.

## PR 3 — Health check and docs
- [x] T7 — `doctor` non-fatal WARNING when the section is missing [S] [P] — implements AC-18 — Depends on: PR 2
  - Done when: `doctor` exit code is unchanged with the section missing and the warning names it (text + `--json`).
- [x] T8 — Template + AGENT_INSTRUCTIONS + matcher role + contracts/cli-reference [S] [P] — implements AC-19 — Depends on: PR 2
  - Done when: template shows the four keys in EN; instructions say "mandatory requirements only" with the JSON example; `test_agent_instructions` passes.
- [x] T9 — CHANGELOG entry [S] — implements — (docs) — Depends on: T7, T8
  - Done when: `Unreleased` lists the feature, schema v15, and the new error code.

Task sizes: S (<1h) | M (1-3h) | L (3-6h)
