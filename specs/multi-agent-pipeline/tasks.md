# Task List: Multi-Agent Pipeline

## Plan Reference
Implements: `specs/multi-agent-pipeline/plan.md`

## Tasks

### Phase A: Schema + Gap Commands

- [x] **TASK-001** [S] Add learning_gaps table — migration v5
  - Modify: `applyr/db.py` (SCHEMA_VERSION, MIGRATIONS, SCHEMA_SQL)
  - Tests: `tests/test_db.py` — test migration from v4 DB, test fresh install
  - Depends on: none

- [x] **TASK-002** [M] Implement `applyr gaps save`
  - Modify: `applyr/commands/analytics.py` (new function `cmd_gaps_save`)
  - Modify: `applyr/cli.py` (routing for `gaps save`)
  - Modify: `applyr/commands/__init__.py` (export)
  - Contract: `specs/multi-agent-pipeline/contracts/gaps.md`
  - Tests: `tests/test_gaps.py` — test save, test empty gaps error, test invalid topic, test invalid offer
  - Depends on: TASK-001

- [x] **TASK-003** [M] Implement `applyr gaps list`
  - Modify: `applyr/commands/analytics.py` (new function `cmd_gaps_list`)
  - Modify: `applyr/cli.py` (routing for `gaps list`)
  - Contract: `specs/multi-agent-pipeline/contracts/gaps.md`
  - Tests: `tests/test_gaps.py` — test list, test filter by topic, test filter by severity, test empty
  - Depends on: TASK-001

- [x] **TASK-004** [S] Implement `applyr gaps stats`
  - Modify: `applyr/commands/analytics.py` (new function `cmd_gaps_stats`)
  - Modify: `applyr/cli.py` (routing for `gaps stats`)
  - Contract: `specs/multi-agent-pipeline/contracts/gaps.md`
  - Tests: `tests/test_gaps.py` — test stats with data, test empty stats
  - Depends on: TASK-001

### Phase B: Blind Recruiter

- [x] **TASK-005** [M] Implement `review_blind()` in cv.py
  - Modify: `applyr/cv.py` (new function `review_blind(offer_id, as_json=False)`)
  - Must NOT load compatibility_pct from DB
  - Must read cv-master.md fresh via `inspect_cv_master()`
  - Contract: `specs/multi-agent-pipeline/contracts/review-blind.md`
  - Tests: `tests/test_cv_review_blind.py` — test blind evaluation, test verdict logic, test missing offer, test missing cv-master
  - Depends on: TASK-001

- [x] **TASK-006** [S] Wire `review-blind` into CLI
  - Modify: `applyr/commands/workflow.py` (routing for `cmd_review_blind`)
  - Modify: `applyr/cli.py` (argument parsing for `cv review-blind`)
  - Modify: `applyr/commands/__init__.py` (export)
  - Contract: `specs/multi-agent-pipeline/contracts/review-blind.md`
  - Tests: `tests/test_cli_routing.py` — test `cv review-blind 42` routes correctly
  - Depends on: TASK-005

### Phase C: Documentation

- [x] **TASK-007** [S] Update AGENT_INSTRUCTIONS.md template
  - Modify: `applyr/templates/AGENT_INSTRUCTIONS.md` — document two-agent workflow
  - This is the end-user contract — changes must be deliberate
  - AC-W1 from spec
  - Depends on: TASK-002, TASK-006

- [x] **TASK-008** [S] Update version to 1.2.0
  - Modify: `applyr/__init__.py` (__version__)
  - Modify: `pyproject.toml` (version)
  - Depends on: TASK-007

### Phase D: Integration

- [x] **TASK-009** [M] Integration test: full two-agent flow
  - Test: add offer → review-blind → gaps save → gaps list → gaps stats
  - Tests all ACs end-to-end
  - Depends on: TASK-002, TASK-003, TASK-004, TASK-006

- [x] **TASK-010** [S] Run lint + full test suite
  - pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801 --fail-under=7.0
  - pytest — all tests pass
  - Depends on: TASK-009

## Legend
- `[S]` Small — under 1 hour
- `[M]` Medium — 1–3 hours
- `[L]` Large — 3–6 hours (consider splitting)
- `[P]` Parallelizable — can run concurrently with other `[P]` tasks at same level
