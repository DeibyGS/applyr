# Tasks: Compact Agent Instructions, `applyr guide`, Native Agent Targets

Each PR is opened only after the previous one is merged to `main` (lesson from #139).

## PR 0 — ADR-016 + this spec (branch `feat/cc-compact-instructions`)
- [x] T0 — ADR-016, ADR index, spec/plan/tasks — Depends on: none

## PR 1 — End-marked injection (fix)
- [x] T1 — `END_MARKER` + `replace_block` (marker-aware, legacy EOF fallback, duplicate cleanup) [M] — implements AC-01, AC-02, AC-03, AC-05 — Depends on: PR 0
  - Done when: user text before and after the block survives `--force` byte for byte.
- [x] T2 — Legacy trailing-text warning [S] — implements AC-04 — Depends on: T1
- [x] T3 — CHANGELOG (Fixed) [S] — Depends on: T1–T2

## PR 2 — Core block + `applyr guide`
- [x] T4 — Write `templates/AGENT_CORE.md` (≤100 lines) [M] — implements AC-06, AC-07 — Depends on: PR 1
- [x] T5 — `GUIDE_SLUGS` + `guide_section` + slug↔heading test [M] — implements AC-09, AC-10 — Depends on: PR 1
- [x] T6 — `cmd_guide` + CLI (pre-init, `--json`, unknown slug) [S] — implements AC-08, AC-11, AC-E1 — Depends on: T5
- [x] T7 — `setup-agent` injects the stamped core [S] — implements AC-06, AC-12 — Depends on: T4
- [x] T8 — Wheel ships `AGENT_CORE.md`; docs + CHANGELOG (Changed) [S] — Depends on: T4–T7

## PR 3 — New and corrected targets
- [x] T9 — Gemini / Copilot / Windsurf / Cline targets + detection [M] — implements AC-13, AC-18 — Depends on: PR 2
- [x] T10 — Cursor `.mdc` always, `.cursorrules` warning, `--global cursor` error [S] — implements AC-14, AC-15, AC-16 — Depends on: PR 2
- [x] T11 — `--global` table: claude, gemini, opencode (claude-skill joins in PR 4) [S] — implements AC-17 — Depends on: T9
- [x] T12 — Docs + CHANGELOG [S] — Depends on: T9–T11

## PR 4 — Claude Code skill
- [x] T13 — `claude-skill` target: frontmatter + stamped core, whole-file write, never auto-detected [M] — implements AC-19, AC-20, AC-21 — Depends on: PR 3
- [x] T14 — Docs + CHANGELOG; set spec status IMPLEMENTED [S] — Depends on: T13
