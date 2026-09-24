# Tasks: CLI-Enforced Pipeline Gates

## PR 0 — ADR-015 + this spec (branch `feat/cc-next-state-machine`, docs only, ~365 lines)

- [x] T0 — ADR-015, ADR index, spec/plan/tasks — Depends on: none

## PR 1 — `cv pdf` gate + `score_source` (branch `feat/cc-next-state-machine-pdf-gate`, chained on PR 0)

- [x] T1 — Extract `_verify_cv()` from `cmd_cv_verify`, no behavior change [M] — implements AC-04 — Depends on: none
  - Done when: `tests/test_cv_verify*.py` pass unchanged.
- [x] T2 — Gate `cmd_cv_pdf` on `_verify_cv`, error `verify_required` [M] — implements AC-01, AC-02, AC-E1 — Depends on: T1
  - Done when: a failing CV produces no PDF and exits 1; a passing CV renders.
- [x] T3 — `cv pdf --force`: stderr warning + dated note on the linked offer [S] — implements AC-03, AC-E2 — Depends on: T2
  - Done when: the note is appended without clobbering existing notes; no id → no DB write.
- [x] T4 — `score_source` validation + deprecation warning in `add` [S] [P] — implements AC-05, AC-06, AC-E3 — Depends on: none
  - Done when: warns without `manual`, is silent with it, rejects other values before insert.
- [x] T5 — Update `examples/` + `llms.txt` [S] [P] — implements AC-07 — Depends on: T4
  - Done when: `grep compatibility_pct examples llms.txt` shows `score_source` on each line that sets it.
- [x] T6 — CHANGELOG (Changed: `cv pdf` gate; Deprecated: bare `compatibility_pct`) [S] — Depends on: T2–T5

## PR 2 — `--record` + `applyr next` (branch `feat/cc-next-state-machine-next-cmd`, chained on PR 1)

- [x] T7 — History helpers `read_history` / `append_history` in `applyr/pipeline_next.py` [S] — implements AC-10, AC-E7 — Depends on: PR 1
  - Done when: an append keeps prior entries; corrupt JSON raises `history_corrupt`.
- [x] T8 — `--record` on `cv review-blind` and `cv review` [M] — implements AC-08, AC-09, AC-E4, AC-E5 — Depends on: T7
  - Done when: entries carry the derived verdict; `cv_iteration` counts only `cv_review` entries.
- [x] T9 — Pure `derive_next()` covering all 8 states [M] — implements AC-12..AC-20 — Depends on: T7
  - Done when: one unit test per state and per transition edge (mtime ordering, iteration cap).
- [x] T10 — `cmd_next` + CLI routing + `--json` [S] — implements AC-11, AC-E6 — Depends on: T9
  - Done when: `applyr next <id> --json` is valid JSON and the DB is unchanged after the call.
- [x] T11 — AGENT_INSTRUCTIONS.md + CHANGELOG [S] — implements AC-21 — Depends on: T10
