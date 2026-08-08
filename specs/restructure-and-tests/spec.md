## Spec: Restructure commands.py + add tests + cleanup

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution (CLAUDE.md): PR budget 400 lines, work-unit commits, Python 3.11+, SQLite, colorama
- Engram #1642: spec-applyr — 21 commands, 28-column schema, scoring engine
- No prior ADRs or refactor decisions
- Corrected assumptions: none — all 8 confirmed

### What does it do? (observable behavior, not implementation)
- Splits the 1646-line `commands.py` monolith into 3 domain modules inside `commands/`
- Removes dead files from repo (`templates/` at root, `build/`, `applyr_export.md`)
- Adds pytest test suite covering pure functions (scoring, config, db, validators)
- Updates README with new structure, test instructions, and recent features

### Acceptance criteria

#### PR A — Bugs + cleanup (already implemented, pending commit)

- `[MUST]` WHEN user runs `applyr add` with a duplicate company+title THE system SHALL reject it with exit code 1
- `[MUST]` WHEN user runs `applyr add` THE system SHALL print APPLY or SKIP based on threshold
- `[MUST]` WHEN user runs `applyr add` with invalid `role_category` THE system SHALL reject with valid values list
- `[MUST]` WHEN user runs `applyr add` with unparseable date THE system SHALL print a warning
- `[MUST]` WHEN installed via pip THE package SHALL include `applyr/templates/*` in the wheel
- `[MUST]` The `templates/` directory at repo root SHALL be removed
- `[MUST]` The `build/` directory SHALL be added to `.gitignore` and removed from tracking
- `[MUST]` The `applyr_export.md` file SHALL be removed

#### PR B — Split commands.py into commands/ package

- `[MUST]` The system SHALL maintain identical CLI behavior after the split (no regressions)
- `[MUST]` `commands/__init__.py` SHALL re-export all public `cmd_*` functions so `cli.py` imports remain unchanged
- `[MUST]` `commands/core.py` SHALL contain: `cmd_init`, `cmd_add`, `cmd_list`, `cmd_show`, `cmd_update`, `cmd_delete`, `cmd_search`, `cmd_setup_agent`
- `[MUST]` `commands/analytics.py` SHALL contain: `cmd_stats`, `cmd_gaps`, `cmd_followups`, `cmd_trends`, `cmd_summary`, `cmd_compare`, `cmd_plan`, `cmd_salary`
- `[MUST]` `commands/workflow.py` SHALL contain: `cmd_export`, `cmd_doctor`
- `[MUST]` Internal helpers (`_today`, `_parse_date`, `_CV_MASTER_TEMPLATE`, `_AGENT_TARGETS`, etc.) SHALL live in the module that uses them
- `[MUST]` Shared helpers used by 2+ modules SHALL live in `commands/_helpers.py`
- `[SHOULD]` `cli.py` import block SHALL change only the import path, not the function names
- `[WONT]` No behavioral changes — this is refactor only

#### PR C — Tests (pure functions)

- `[MUST]` `tests/test_scoring.py` SHALL test: empty topics, single topic, all topics, invalid scores, missing weights, boundary values (0, 100)
- `[MUST]` `tests/test_config.py` SHALL test: default config creation, weight normalization, missing keys fallback
- `[MUST]` `tests/test_db.py` SHALL test: schema creation, migration system, insert+query round-trip
- `[MUST]` `tests/test_validators.py` SHALL test: duplicate detection, date parsing, role_category validation, salary_min > salary_max rejection
- `[MUST]` All tests SHALL use a temporary database (tmp_path fixture), never touch `~/.applyr/`
- `[MUST]` `pyproject.toml` SHALL include `[tool.pytest.ini_options]` with `testpaths = ["tests"]`
- `[SHOULD]` Tests SHALL use `@pytest.mark.unit` markers
- `[WONT]` No integration tests, no CLI subprocess tests, no mocking of external systems — those are for a future PR

#### PR D — README update

- `[MUST]` README SHALL reflect the new `commands/` package structure
- `[MUST]` README SHALL document how to run tests (`pytest`)
- `[MUST]` README SHALL document: duplicate detection, threshold recommendation, role_category validation
- `[SHOULD]` README SHALL clarify that an AI coding agent is required (not optional)
- `[WONT]` No redesign of the README — only additive updates

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/commands.py` | DELETE | Replaced by commands/ package |
| `applyr/commands/__init__.py` | CREATE | Re-exports all cmd_* functions |
| `applyr/commands/core.py` | CREATE | init, add, list, show, update, delete, search, setup_agent |
| `applyr/commands/analytics.py` | CREATE | stats, gaps, followups, trends, summary, compare, plan, salary |
| `applyr/commands/workflow.py` | CREATE | export, doctor |
| `applyr/commands/_helpers.py` | CREATE | Shared internal helpers (if any used by 2+ modules) |
| `applyr/cli.py` | MODIFY | Update import path from commands → commands package |
| `templates/` (root) | DELETE | Duplicate — now in applyr/templates/ |
| `build/` | DELETE + GITIGNORE | Build artifact, should never be tracked |
| `applyr_export.md` | DELETE | Test artifact |
| `.gitignore` | MODIFY | Add build/, dist/, *.egg-info |
| `tests/conftest.py` | CREATE | Shared fixtures (tmp db, tmp config) |
| `tests/test_scoring.py` | CREATE | Scoring engine tests |
| `tests/test_config.py` | CREATE | Config loading tests |
| `tests/test_db.py` | CREATE | Database schema tests |
| `tests/test_validators.py` | CREATE | Input validation tests |
| `pyproject.toml` | MODIFY | Add pytest config, optional pytest dep |
| `README.md` | MODIFY | Structure, tests, new features |

### Dependencies
- **pytest** — dev dependency only, added to `[project.optional-dependencies]`
- No new runtime dependencies

### Explicit assumptions
- `cli.py` uses `from applyr.commands import cmd_add, cmd_list, ...` → after split, same imports work via `__init__.py` re-exports
- Helpers used by only 1 module stay in that module → no premature `_helpers.py` if not needed
- `build/` can be safely deleted — it's a setuptools artifact regenerated by `python -m build`

### Edge cases / risks
- **Import order**: circular imports between commands modules → mitigated by keeping db/config imports at module level, not cross-importing between command modules
- **Shared state**: `_CV_MASTER_TEMPLATE` used in both init and add → lives in core.py since both functions are there
- **Test isolation**: tests must never touch `~/.applyr/` → `tmp_path` + `monkeypatch.setenv("HOME", ...)` in conftest

### Task breakdown (execution order)

#### PR A — Bugs + cleanup (~200 lines)
- [x] 1. Duplicate detection in cmd_add [S]
- [x] 2. Threshold recommendation output [S]
- [x] 3. role_category validation [S]
- [x] 4. Date format warning [S]
- [x] 5. Fix templates packaging (copy to applyr/templates/) [S]
- [x] 6. AGENT_INSTRUCTIONS.md rewrite [M]
- [ ] 7. Remove templates/ from root, build/, applyr_export.md [S]
- [ ] 8. Update .gitignore [S]

#### PR B — Split commands.py (~300 lines changed)
- [ ] 1. Identify shared helpers → create _helpers.py if needed [S]
- [ ] 2. Create commands/__init__.py with re-exports [S]
- [ ] 3. Extract core.py (init, add, list, show, update, delete, search, setup_agent) [L]
- [ ] 4. Extract analytics.py (stats, gaps, followups, trends, summary, compare, plan, salary) [L]
- [ ] 5. Extract workflow.py (export, doctor) [S]
- [ ] 6. Update cli.py imports [S]
- [ ] 7. Delete commands.py [S]
- [ ] 8. Smoke test: pip install -e . && applyr version && applyr add && applyr stats [S]

#### PR C — Tests (~300 lines)
- [ ] 1. Add pytest to optional-dependencies + pytest config in pyproject.toml [S]
- [ ] 2. Create conftest.py with tmp_db and tmp_config fixtures [S]
- [ ] 3. test_scoring.py [M]
- [ ] 4. test_config.py [M]
- [ ] 5. test_db.py [M]
- [ ] 6. test_validators.py [M]
- [ ] 7. Run full suite, verify all green [S]

#### PR D — README (~100 lines)
- [ ] 1. Update project structure section [S]
- [ ] 2. Add testing section [S]
- [ ] 3. Document new features (duplicates, threshold, role_category) [S]
- [ ] 4. Clarify AI agent as requirement [S]

### Out of scope
- `[WONT]` src/ layout migration — flat layout is correct for this project size
- `[WONT]` Integration/E2E tests — future PR
- `[WONT]` CI workflow changes — wait for GitHub Actions to come back online
- `[WONT]` CLI subprocess tests (testing argparse routing) — future PR
- `[WONT]` New features — this is infrastructure only
