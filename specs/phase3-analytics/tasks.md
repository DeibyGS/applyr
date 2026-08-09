# Task List: Phase 3 — Analytics

## Plan Reference
Implements: `specs/phase3-analytics/spec.md`

## Tasks

### Setup

- [ ] **TASK-001** [S] Create `applyr/analytics.py` skeleton with imports and docstring
  - Creates: `applyr/analytics.py`
  - Depends on: none

- [ ] **TASK-002** [M] Add DB migrations for `cv_versions` and `response_tracking` tables
  - Creates: migration file in `applyr/migrations/`
  - Tables: cv_versions (id, offer_id, cv_file, ats_score, created_at), response_tracking (id, offer_id, status, date, notes)
  - Depends on: TASK-001

### CV Comparison

- [ ] **TASK-003** [S] [P] Write tests for `compare_cvs()` in `tests/test_analytics.py`
  - Tests: AC-1 (ATS score delta, keyword coverage delta, recommendations)
  - Depends on: TASK-001

- [ ] **TASK-004** [M] Implement `compare_cvs()` in `applyr/analytics.py`
  - Contract: `specs/phase3-analytics/spec.md` → AC-1
  - Depends on: TASK-003

### Response Tracking

- [ ] **TASK-005** [S] [P] Write tests for `track_response()` in `tests/test_analytics.py`
  - Tests: AC-3 (response status storage)
  - Depends on: TASK-001, TASK-002

- [ ] **TASK-006** [M] Implement `track_response()` in `applyr/analytics.py`
  - Contract: `specs/phase3-analytics/spec.md` → AC-3
  - Depends on: TASK-005

- [ ] **TASK-007** [S] [P] Write tests for `calculate_response_rate()` in `tests/test_analytics.py`
  - Tests: AC-2, AC-4 (response rate calculation, trend analysis)
  - Depends on: TASK-001

- [ ] **TASK-008** [M] Implement `calculate_response_rate()` in `applyr/analytics.py`
  - Contract: `specs/phase3-analytics/spec.md` → AC-2, AC-4
  - Depends on: TASK-007

### CLI Integration

- [ ] **TASK-009** [S] Write tests for CLI routing of `compare-cvs` and `response-rate`
  - Tests: AC-1, AC-2 (CLI output format, --json flag)
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-010** [M] Add `compare_cvs()` and `response_rate()` to `commands/analytics.py`
  - Contract: `specs/phase3-analytics/spec.md` → AC-1, AC-2
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-011** [S] Add CLI routing in `cli.py` for `cv compare-cvs` and `response-rate`
  - Depends on: TASK-010

### Integration

- [ ] **TASK-012** [S] Integration test: full flow with real data
  - Tests: AC-1, AC-2 (end-to-end with test applications)
  - Depends on: TASK-011

## Legend
- `[S]` Small — under 1 hour
- `[M]` Medium — 1–3 hours
- `[L]` Large — 3–6 hours (consider splitting)
- `[P]` Parallelizable — can run concurrently with other `[P]` tasks at same level
