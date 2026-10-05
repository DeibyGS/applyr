# Tasks: Step Handoff Gates

Spec: `spec.md` (APPROVED) · Plan: `plan.md` · ADR: `../../docs/adr/018-step-handoff-gates.md`

Order: top to bottom within a PR; `[P]` = parallelisable with its siblings.
Every implementation task is preceded by its test task (test-first).
PR split keeps each PR under the 400-line budget.

## PR A — Plan artifact gate

- [ ] **T1 [MUST][test] `tests/test_gates.py` — plan validation** · S · deps: —
  Five states (`missing`, `wrong_offer`, `empty`, `unreadable`, `valid`), Spanish +
  English heading aliases, `offer_id` mismatch, empty forbidden list = missing.
  Covers AC-03, AC-05, AC-06, AC-E1, AC-E2.
- [ ] **T2 [MUST][impl] `applyr/gates.py` + `applyr/constants.py`** · M · deps: T1
  `plan_path_for`, `validate_plan`, `PlanStatus` enum; error codes `plan_required` /
  `plan_invalid`, heading aliases, section display labels.
- [ ] **T3 [MUST][test] `tests/test_gates_cli.py` — generation gate** · S · deps: —
  No plan → exit 1 `plan_required` and **no file written**; valid plan → generated;
  `--force` → generated **and** note appended (visible in `show`); malformed plan →
  `plan_invalid`. Covers AC-01, AC-02, AC-04, AC-E1.
- [ ] **T4 [MUST][impl] `applyr/cv.py` — `cmd_cv_generate` gate** · M · deps: T2, T3
  Call `validate_plan` after the offer row is loaded; extract the notes-append SQL out
  of `_note_forced_pdf` into a shared `_append_note(offer_id, line)` used by both.
- [ ] **T5 [MUST][test] retro-compat** · S · deps: T2
  Offer with `cv_used` and no plan → generation of the *next* CV is not required to
  retro-approve, and nothing in `gates.py` reports `plan` as `missing` for it.
  Covers AC-05.

## PR B — Visibility: `next --plan` and `cv gate`

- [ ] **T6 [MUST][test] `tests/test_gates_cli.py` — states** · S · deps: PR A
  `next` returns `plan` after a recorded blind review with no CV; returns `generate`
  once a valid plan exists; never returns `plan` for an offer that already has a CV.
  Covers AC-09, AC-10, AC-05.
- [ ] **T7 [MUST][impl] `applyr/pipeline_next.py` + `applyr/commands/workflow.py`** · M ·
  deps: T6
  `derive_next(..., plan_status=...)` keyword-only param returning the `plan` state
  between `decide` and `generate`; `cmd_next` computes it. Keeps `derive_next` I/O-free.
- [ ] **T8 [MUST][test] `tests/test_gates_cli.py` — `cv gate`** · S · deps: T6
  Human and `--json` shapes (status vocabulary, `state`, `missing`, exit codes),
  AC-E3 unknown offer, AC-E4 no CV linked. Covers AC-07, AC-08, AC-11, AC-E3, AC-E4.
- [ ] **T9 [MUST][impl] `applyr/commands/workflow.py` + `applyr/cli.py`** · M · deps: T7, T8
  `cmd_cv_gate` (derives `state` by calling `derive_next`, layers artifact detail),
  routes `cv gate`, adds it to the valid-subcommand list and the help text.

## PR C — Fact Checker as a recorded step

- [ ] **T10 [MUST][test] fact-check record + `next`** · S · deps: —
  `--record` appends `fact_check` with a **derived** verdict (`PASS` iff
  score ≥ `FACT_CHECK_PASS_MIN`); `cv_iteration` does not increment; `next` returns
  `fact_check` after a ready review and does not advance on a failing record.
  Covers AC-12, AC-13, AC-16, AC-17.
- [ ] **T11 [MUST][impl] `pipeline_next.py` + `cv.py` + `cli.py`** · M · deps: T10
  `review_verdict` branch for `fact_check`; `cmd_cv_fact_check` printing the packaged
  role file plus the recording appendix; routing for `cv fact-check`.
- [ ] **T12 [MUST][test] `cv pdf` fact-check gate** · S · deps: T10
  No fresh passing fact check → exit 1 `fact_check_required`, no PDF; `--force` → PDF
  plus dated note; CV without embedded offer id → behaviour unchanged.
  Covers AC-14, AC-15, AC-E5.
- [ ] **T13 [MUST][impl] `applyr/cv.py` — `_check_pdf_gate`** · S · deps: T12
  Return the failing code alongside the reason so the caller can raise
  `verify_required` or `fact_check_required`; keep the existing verify logic intact.

## PR D — Deterministic framing warning

- [ ] **T14 [MUST][test] framing lint** · S · deps: —
  Term only under PROYECTOS → warning naming the section; term under experience →
  silence; skills-only → warning; no experience section → silence; project names and
  employers never flagged; verdict/exit code unchanged. Covers AC-18, AC-19, AC-20.
- [ ] **T15 [MUST][impl] `applyr/cv.py` + `applyr/constants.py`** · S · deps: T14
  `framing` array in the verify result + printed section; CV summary-section heading
  aliases; never touches `passed`. AC-21 (WONT) enforced by the T14 assertions.

## PR E — Instructions, roles and docs

- [ ] **T16 [MUST][impl] `applyr/templates/AGENT_INSTRUCTIONS.md`** · M · deps: PR A-C
  Step 5.7 names the plan artifact + gate; new Step 6c (fact check) between review and
  verify; Steps 6/6b/7 reference `cv gate`; bypass-leaves-a-trace rule. AC-22, AC-24.
- [ ] **T17 [MUST][test] `tests/test_agent_instructions.py`** · S · deps: T16
  Asserts the packaged instructions carry the new steps and that each of the five role
  files starts with the checklist instruction. Covers AC-22, AC-23.
- [ ] **T18 [MUST][impl] `applyr/templates/agents/*.md` (5 files)** · S · deps: T17
  First instruction of each role: run `applyr cv gate <id>` and stop if an earlier
  artifact is missing. AC-23.
- [ ] **T19 [SHOULD][impl] `docs/contracts.md`, `docs/cli-reference.md`, `CHANGELOG.md`** · S · deps: PR A-D
  New commands, new states, new error codes, `[Unreleased]` entry, behaviour changes
  for `cv generate` and `cv pdf`.

## Final

- [ ] **T20 [MUST] Full validation** · M · deps: all
  `pytest` green · `pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801
  --fail-under=7.0` · manual demo of the whole flow on a fresh offer · traceability
  matrix (every `[MUST]` AC → test + implementation) before the PRs are opened.

## Dependencies

```
T1 → T2 → T4 → (PR A)
T3 ─────↗
T5 → (PR A)
T6 → T7 → T9 → (PR B)   T8 → T9
T10 → T11, T13 → (PR C)  T12 → T13
T14 → T15 → (PR D)
T16 → T17 → T18 → (PR E)   T19 → T20
```

No cycles. PRs A→B→C→D→E are chained (each builds on the previous); T1/T3/T5 and
T10/T14 can start in parallel with PR A's review.
