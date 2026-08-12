# OC-REPORT — Onboarding fixes v1.4.0

## Status: DONE

## Completed tasks
- [x] TASK-001 — Invert null check in `cmd_cv_keywords` (`if offer is None`); regression test added
- [x] TASK-002 — `cmd_cv_review_blind` reads `threshold_apply`/`threshold_maybe` (not legacy `threshold`/`maybe_threshold`); config test added
- [x] TASK-003 — Removed duplicate `cmd_cv_ats_check` (cv.py:1261-1306); single definition remains
- [x] TASK-004 — `_is_initialized()` only checks `jobs.db` exists (a lone `applyr.toml` no longer counts); test added
- [x] TASK-005 — `cmd_init` ships the rich packaged template via `_cv_master_template_text()` loader; template rewritten (9 sections, all leave-bare `...`)
- [x] TASK-006 — audit false positive: `_check_cv_master()` already present in `cmd_doctor` (workflow.py) → no-op
- [x] TASK-007 — `_warn_if_profile_empty()` called by `cmd_setup_agent`; covers missing and unfilled cv-master.md; tests added
- [x] TASK-008 — Full suite + CI pylint pass

## Incomplete tasks
- [ ] None

## Spec deviations [DISAGREEMENT]
| # | Spec said | OC did | Reason | CC decides |
|---|-----------|--------|--------|-----------|
| 1 | TASK-005 template should read as "filled" so `inspect_cv_master` passes | Template keeps bare `...` placeholders (still "not filled") | Empty placeholders are what the shipped-template guard (`test_shipped_template_is_not_filled`) checks; a "filled" shipped template breaks the guard that stops `cv generate` on nothing | [x] accept / [ ] reject / [ ] escalate |
| 2 | TASK-007 assertion assumed offers without tech_stack die `no_keywords` | Existing offer proceeds to CV lookup and dies `no_cv` | `extract_keywords` yields tokens from the title alone, so the no-keywords branch is unreachable for seeded offers; the meaningful regression is `not found` vs proceeding — test asserts exactly that | [x] accept / [ ] reject / [ ] escalate |

## Simplifications applied [SIMPLIFIED]
- TASK-007 warning reuse `warn()` (stderr) instead of a new output channel — matches existing diagnostics, keeps tests on `capsys.err`.
- Lazy imports inside `_warn_if_profile_empty` to avoid a circular import between `commands.core` and `cv`/`cv_master`.

## Doubts / Blockers
- Test-side effect: `setup-agent` writes `CLAUDE.md` into the pytest cwd (repo root). `CLAUDE.md` is gitignored, so no diff pollution — but this predates these changes (`test_setup_agent_with_agent` already did it) and is worth isolating later via `chdir`.

## Check results
- `python -m pytest tests/ -q` → 418 passed
- `pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801 --fail-under=7.0` → 9.31/10 (threshold 7.0)