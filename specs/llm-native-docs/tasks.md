# Task List: Applyr LLM-Native Documentation

## Plan Reference
Implements: `specs/llm-native-docs/plan.md`

## Tasks

### PR-A: Agent-Facing Docs

- [ ] **TASK-001** [M] Create AGENTS.md at project root
  - Covers: project purpose, architecture, file map, conventions, how to add commands, what not to modify
  - Tests: AC-1, AC-E1, AC-E2 from spec.md
  - Depends on: none

- [ ] **TASK-002** [S] Create llms.txt at project root
  - Quick summary: purpose, install, run, architecture, testing (<200 lines)
  - Tests: AC-2 from spec.md
  - Depends on: none

### PR-B: Contributor Docs

- [ ] **TASK-003** [M] Create CONTRIBUTING.md
  - Covers: setup, test/lint commands, branch naming, commit format, PR checklist
  - Tests: AC-3 from spec.md
  - Depends on: none

- [ ] **TASK-004** [S] Create CHANGELOG.md
  - Format: Keep a Changelog
  - Content: v0.5.1, v0.5.0, v0.4.1, v0.4.0, v0.3.0 (from git history)
  - Tests: AC-6 from spec.md
  - Depends on: none

### PR-C: Examples

- [ ] **TASK-005** [S] Create examples/basic_usage.py
  - Shows: init, add offer, list, show, stats
  - Tests: AC-4 from spec.md
  - Depends on: none

- [ ] **TASK-006** [S] Create examples/add_offer.py
  - Shows: programmatic offer registration with all fields
  - Tests: AC-4 from spec.md
  - Depends on: none

- [ ] **TASK-007** [S] Create examples/cli_usage.sh
  - Shows: all CLI commands with comments
  - Tests: AC-4 from spec.md
  - Depends on: none

### PR-D: Organized Docs

- [ ] **TASK-008** [S] Create docs/getting-started.md
  - Covers: install, init, config, first offer
  - Tests: AC-5, AC-7 from spec.md
  - Depends on: none

- [ ] **TASK-009** [M] Create docs/architecture.md
  - Covers: Mermaid diagram, module responsibilities, data flow
  - Tests: AC-5, AC-8 from spec.md
  - Depends on: none

- [ ] **TASK-010** [M] Create docs/cli-reference.md
  - Covers: all 21 commands with examples, flags, aliases
  - Tests: AC-5 from spec.md
  - Depends on: none

- [ ] **TASK-011** [S] Create docs/troubleshooting.md
  - Covers: common errors, solutions, doctor command
  - Tests: AC-5 from spec.md
  - Depends on: none

## Legend
- `[S]` Small — under 1 hour
- `[M]` Medium — 1–3 hours
- `[L]` Large — 3–6 hours (consider splitting)
- `[P]` Parallelizable — can run concurrently with other `[P]` tasks at same level
