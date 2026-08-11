## Spec: setup-agent — OpenCode integration (write AGENTS.md, not .opencode/instructions.md)

### Status: IMPLEMENTED
### Version: 1.0

### Validation (post-implementation)
- Tests: 426 passed (was 418 → +8 new). New cases cover: opencode writes/creates `AGENTS.md`,
  append preserving existing content, dedupe on project and global paths, `--global` writing to
  `~/.config/opencode/AGENTS.md`, error on `--global` without `--agent`, error on
  `--global` + `generic`, deprecation warning for a stale `.opencode/instructions.md`.
- Pylint: 9.39/10 on touched files (core.py, cli.py); gate ≥7.0.
- Verified that `.opencode/instructions.md` is never created and that cwd stays untouched in
  global mode.

### Recovered context
- Project constitution: `/Users/db/Documents/GitHub/applyr/constitution.md`
- Relevant ADRs: ADR 003 (no LLM calls), ADR 006 (errors to stderr)
- Audit date: 2026-08-10 — found while onboarding applyr 1.4.0 into OpenCode
- Recovered around the last audit, this repo's spec/plan/tasks were regenerated. Worked trees: 3
  feature branches exist locally (ATS, multi-agent) but NONE is merged into main (1.4.0).

### The problem
`_AGENT_TARGETS["opencode"] = (".opencode/instructions.md",)` (core.py:85) and the detection
entry `("opencode", ".opencode/instructions.md")` (core.py:94). **OpenCode does not read
`.opencode/instructions.md`.** OpenCode loads `AGENTS.md` at the project root and
`~/.config/opencode/AGENTS.md` globally. As a result `applyr setup-agent --agent opencode`
writes a dead file: the agent never receives the contract. Verified in this session: after
`setup-agent`, the only path that actually reached the agent was the manual edit of the global
`AGENTS.md`.

### What does it do? (observable behavior)
- `applyr setup-agent --agent opencode` injects the applyr instructions into `AGENTS.md` in the
  current directory (instead of `.opencode/instructions.md`).
- `applyr setup-agent --agent opencode --global` injects them into the user's global
  `~/.config/opencode/AGENTS.md`.
- Auto-detection no longer matches `.opencode/instructions.md`; `AGENTS.md` is the opencode
  contract file.

### What files does it touch?
| File | Action | Reason |
|------|--------|--------|
| applyr/commands/core.py | MODIFY | `_AGENT_TARGETS`, `_AGENT_DETECT_ORDER`, `cmd_setup_agent()` (target resolution + `global` flag) |
| applyr/cli.py | MODIFY | Parse `--global` flag and forward it to `cmd_setup_agent()` |
| tests/test_cli_routing.py | MODIFY | New tests: opencode target, `--global`, dedupe, deprecated-file warning |

### Dependencies
- Reuses `agent_instructions.py` packaged template (unchanged)
- Reuses existing append + dedupe logic (`cmd_setup_agent` core.py:425-436)
- No DB, no API, no new commands, no alias changes

### Acceptance criteria

#### Interop — OpenCode contract file
- `[MUST]` WHEN `applyr setup-agent --agent opencode` runs, THE system SHALL write the
  instructions to `AGENTS.md` in the current directory and SHALL NOT create
  `.opencode/instructions.md`
- `[MUST]` GIVEN an `AGENTS.md` that already exists with content, WHEN
  `applyr setup-agent --agent opencode` runs, THEN the existing content SHALL be preserved and
  the instructions appended after the `---` separator
- `[MUST]` GIVEN an `AGENTS.md` that already contains applyr instructions, WHEN
  `applyr setup-agent --agent opencode` runs, THEN the system SHALL skip with the existing
  "already contains applyr instructions" message (no duplication)
- `[MUST]` GIVEN `AGENTS.md` does not exist, WHEN `applyr setup-agent --agent opencode` runs,
  THEN the system SHALL create `AGENTS.md` containing the instructions

#### Global mode (all agents)
- `[MUST]` WHEN `--global` is set AND `--agent opencode` is given, THE system SHALL write the
  instructions to `~/.config/opencode/AGENTS.md`, creating the `~/.config/opencode` directory
  when missing
- `[MUST]` WHEN `--global` is set AND `--agent claude` is given, THE system SHALL write the
  instructions to `~/.claude/CLAUDE.md`, creating the `~/.claude` directory when missing
- `[MUST]` WHEN `--global` is set AND `--agent cursor` is given, THE system SHALL write the
  instructions to `~/.cursorrules`
- `[MUST]` WHEN `--global` is set AND `--agent generic` is given, THE system SHALL exit with a
  structured error (`code=invalid_value`) stating that `generic` has no canonical global path
- `[MUST]` WHEN `--global` is set AND no `--agent` is passed, THE system SHALL exit with a
  structured error (`code=invalid_value`) explaining that `--global` requires an explicit
  `--agent`
- `[MUST]` GIVEN a global file that already contains applyr instructions, WHEN `--global` runs,
  THEN the system SHALL apply the same dedupe rule (skip, do not duplicate)

#### Detection
- `[MUST]` THE system SHALL NOT match OpenCode through `.opencode/instructions.md` in
  `_AGENT_DETECT_ORDER`
- `[SHOULD]` WHEN no `--agent` is passed AND `AGENTS.md` exists in the current directory, THEN
  detection SHALL resolve to a target that writes `AGENTS.md` (`generic` or `opencode`)
  without duplication in the detect order

#### Deprecation
- `[SHOULD]` IF `.opencode/instructions.md` exists in the current directory AND
  `--agent opencode` runs, THEN the system SHALL print a warning that the file is deprecated and
  that instructions now go to `AGENTS.md`

### Explicit assumptions
- OpenCode reads `AGENTS.md` (project) and `~/.config/opencode/AGENTS.md` (global). Verified in
  this session against OpenCode. If false, the fix targets the wrong file.
- `AGENTS.md` is a safe append target for every agent family (`generic` already uses it).
- Writing a global file is opt-in via `--global`; the default stays project-local. `--global`
  requires an explicit `--agent` (Gate 1 decision).
- `--global` applies to all agents, each with its canonical global path (Gate 1 decision):
  opencode → `~/.config/opencode/AGENTS.md`, claude → `~/.claude/CLAUDE.md`,
  cursor → `~/.cursorrules`. `generic` has no global path and errors.
- `~/.config/opencode/` and `~/.claude/` may not exist — the resolver SHALL create parent dirs.

### Edge cases / risks
- Risk: dedupe check is substring-based ("applyr" + "agent instructions"); a user's own
  unrelated text containing both words would be skipped → low likelihood, acceptable (same
  behavior as today).
- Risk: `--global` on a system where `~/.config` exists but `opencode/` doesn't → mitigated by
  `mkdir(parents=True, exist_ok=True)`.
- Risk: existing users with a stale `.opencode/instructions.md` never notice → mitigated by the
  deprecation warning.

### Task breakdown (execution order)
1. Change `_AGENT_TARGETS["opencode"]` to `("AGENTS.md",)` and drop the opencode row from
   `_AGENT_DETECT_ORDER` [S]
2. Add a resolvable global path per agent (opencode → `~/.config/opencode/AGENTS.md`,
   claude → `~/.claude/CLAUDE.md`, cursor → `~/.cursorrules`) [S]
3. Extend `cmd_setup_agent(agent, global_=False)` — resolve target (project vs global), create
   parent dirs, keep append + dedupe [S]
4. Parse `--global` in `cli.py` and forward it [S]
5. Add deprecation warning for an existing `.opencode/instructions.md` [S]
6. Tests: opencode writes AGENTS.md, dedupe on project + global paths, `--global` writes the
   canonical global path per agent, error when `--global` without `--agent` or with `generic`,
   no `.opencode` dir created, deprecation warning [M]
7. Run `pytest` + `pylint` (CI gate) [S]

### Out of scope
- `[WONT]` Rename or remove a CLI command or alias (contracts.md)
- `[WONT]` Modify `templates/AGENT_INSTRUCTIONS.md`
- `[WONT]` Migrate existing `.opencode/instructions.md` content automatically (warning only)
- `[WONT]` Change targets for `claude`, `cursor`, `generic` beyond the `--global` mapping
- `[WONT]` DB schema, migrations, or `scoring.py`

### Open questions
- None — resolved in Gate 1: `--global` applies to all agents (canonical global paths), and
  `--global` requires an explicit `--agent`.