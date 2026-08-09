# Task List: Phase 1 — ATS Compatibility

## Plan Reference
Implements: `specs/phase1-ats-compatibility/spec.md`

## Tasks

### Setup

- [ ] **TASK-001** [S] Create `applyr/ats.py` skeleton with imports and docstring
  - Creates: `applyr/ats.py`
  - Depends on: none

- [ ] **TASK-002** [S] Create `applyr/templates/ats_rules.json` with validation rules
  - Creates: `applyr/templates/ats_rules.json`
  - Contains: standard headers, forbidden formats, date patterns
  - Depends on: none

### ATS Validation

- [ ] **TASK-003** [S] [P] Write tests for `validate_ats_format()` in `tests/test_ats.py`
  - Tests: AC-1, AC-3 (single column, standard headers, no images/tables)
  - Depends on: TASK-001, TASK-002

- [ ] **TASK-004** [M] Implement `validate_ats_format()` in `applyr/ats.py`
  - Contract: `specs/phase1-ats-compatibility/spec.md` → AC-1, AC-3
  - Depends on: TASK-003

### Keyword Matching

- [ ] **TASK-005** [S] [P] Write tests for `extract_keywords()` in `tests/test_ats.py`
  - Tests: AC-2 (keyword extraction from offer)
  - Depends on: TASK-001

- [ ] **TASK-006** [M] Implement `extract_keywords()` in `applyr/ats.py`
  - Contract: `specs/phase1-ats-compatibility/spec.md` → AC-2
  - Depends on: TASK-005

- [ ] **TASK-007** [S] [P] Write tests for `match_keywords()` in `tests/test_ats.py`
  - Tests: AC-2 (keyword comparison: matched/missing/extra)
  - Depends on: TASK-001

- [ ] **TASK-008** [M] Implement `match_keywords()` in `applyr/ats.py`
  - Contract: `specs/phase1-ats-compatibility/spec.md` → AC-2
  - Depends on: TASK-007

### CLI Integration

- [ ] **TASK-009** [S] Write tests for CLI routing of `ats-check` and `keywords`
  - Tests: AC-1, AC-2 (CLI output format, --json flag)
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-010** [M] Add `ats_check()` and `keywords()` to `commands/cv.py`
  - Contract: `specs/phase1-ats-compatibility/spec.md` → AC-1, AC-2
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-011** [S] Add CLI routing in `cli.py` for `cv ats-check` and `cv keywords`
  - Depends on: TASK-010

### Integration

- [ ] **TASK-012** [S] Integration test: full flow with real CV and offer
  - Tests: AC-1, AC-2 (end-to-end with Excelia CV from test)
  - Depends on: TASK-011

## Legend
- `[S]` Small — under 1 hour
- `[M]` Medium — 1–3 hours
- `[L]` Large — 3–6 hours (consider splitting)
- `[P]` Parallelizable — can run concurrently with other `[P]` tasks at same level
