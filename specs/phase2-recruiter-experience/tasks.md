# Task List: Phase 2 — Recruiter Experience

## Plan Reference
Implements: `specs/phase2-recruiter-experience/spec.md`

## Tasks

### Setup

- [ ] **TASK-001** [S] Create `applyr/templates/bullet_patterns.json` with duty→achievement patterns
  - Creates: `applyr/templates/bullet_patterns.json`
  - Contains: weak verbs, strong verbs, metric patterns, CAR formula examples
  - Depends on: none

- [ ] **TASK-002** [S] Create `applyr/templates/cover_letter.md` with template structure
  - Creates: `applyr/templates/cover_letter.md`
  - Contains: opening hook, achievement slots, call to action
  - Depends on: none

### Bullet Optimization

- [ ] **TASK-003** [S] [P] Write tests for `analyze_bullets()` in `tests/test_cv_bullets.py`
  - Tests: AC-1, AC-3 (duty detection, metric detection, weak verb detection)
  - Depends on: TASK-001

- [ ] **TASK-004** [M] Implement `analyze_bullets()` in `applyr/cv.py`
  - Contract: `specs/phase2-recruiter-experience/spec.md` → AC-1, AC-3
  - Depends on: TASK-003

- [ ] **TASK-005** [S] [P] Write tests for `suggest_improvements()` in `tests/test_cv_bullets.py`
  - Tests: AC-1, AC-4 (suggestion generation, strong verb alternatives)
  - Depends on: TASK-001

- [ ] **TASK-006** [M] Implement `suggest_improvements()` in `applyr/cv.py`
  - Contract: `specs/phase2-recruiter-experience/spec.md` → AC-1, AC-4
  - Depends on: TASK-005

### Cover Letter Generation

- [ ] **TASK-007** [S] [P] Write tests for `generate_cover_letter()` in `tests/test_cover_letter.py`
  - Tests: AC-2 (cover letter generation from cv-master + offer)
  - Depends on: TASK-002

- [ ] **TASK-008** [M] Implement `generate_cover_letter()` in `applyr/cv.py`
  - Contract: `specs/phase2-recruiter-experience/spec.md` → AC-2
  - Depends on: TASK-007

### CLI Integration

- [ ] **TASK-009** [S] Write tests for CLI routing of `bullet-optimize` and `cover-letter`
  - Tests: AC-1, AC-2 (CLI output format, --json flag)
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-010** [M] Add `bullet_optimize()` and `cover_letter()` to `commands/cv.py`
  - Contract: `specs/phase2-recruiter-experience/spec.md` → AC-1, AC-2
  - Depends on: TASK-004, TASK-006, TASK-008

- [ ] **TASK-011** [S] Add CLI routing in `cli.py` for `cv bullet-optimize` and `cv cover-letter`
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
