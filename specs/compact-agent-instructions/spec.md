# Spec: Compact Agent Instructions, `applyr guide`, Native Agent Targets

### Status: APPROVED
### Version: 1.0

### Recovered context
- Constitution: no `docs/constitution.md` — `AGENTS.md` plus ADRs. Binding:
  [ADR 003](../../docs/adr/003-no-llm-calls.md) (no LLM calls),
  [ADR 007](../../docs/adr/007-structured-json-errors.md) (structured error codes),
  [ADR 015](../../docs/adr/015-cli-enforced-pipeline-gates.md) (`applyr next` owns the
  pipeline order).
- Governing decision: [ADR 016](../../docs/adr/016-compact-core-instructions-and-guide.md).
- Engram: `adr:applyr:compact-instructions-guide` (2026-09-24).
- History: stale instruction copies were fixed in v0.8.3, v1.5.0 and the
  `setup-agent --force` staleness fix. The canonical `~/.applyr/AGENT_INSTRUCTIONS.md`
  contract (version stamp on line 1, checked by `doctor`) is unchanged.
- Confirmed assumptions (Deiby, 2026-09-24): the core replaces the full document in
  injected blocks only; `guide` reads the packaged template; `claude-skill` is opt-in
  and never auto-detected; `--global --agent cursor` becomes an error; an existing
  `.cursorrules` is warned about, never modified.

### What does it do?
- `setup-agent` writes a short core block (about 80 lines) instead of the full
  565-line document.
- `applyr guide` lists the workflow sections, and `applyr guide <step>` prints one of
  them from the installed package.
- Refreshing an injected block with `--force` no longer deletes text the user wrote
  after it.
- `setup-agent` supports Gemini, Copilot, Windsurf, Cline, Cursor `.mdc` rules and a
  Claude Code skill.

### Boundaries
**Always do:** keep the packaged `AGENT_INSTRUCTIONS.md` as the single source of the
detailed workflow; preserve user text around an injected block.
**Ask first:** deleting or rewriting any file applyr did not create; adding a
dependency.
**Never do:** modify a legacy `.cursorrules`; auto-install `claude-skill`; call an LLM.

### Acceptance criteria

#### PR 1 — End-marked injection
- `[MUST]` AC-01: WHEN `setup-agent` injects instructions THE system SHALL end the
  block with `<!-- applyr-end -->` after the stamped content.
- `[MUST]` AC-02: Given a file with user text before and after an end-marked block,
  When `setup-agent --force` runs, Then the block is replaced and both user texts are
  kept byte for byte.
- `[MUST]` AC-03: Given a block written by an older version (no end marker), When
  `--force` runs, Then the block is treated as running to end of file (as before) and
  replaced.
- `[SHOULD]` AC-04: Given a legacy block followed by text that is not part of the
  packaged template, When `--force` runs, Then a warning names the risk before the
  file is rewritten.
- `[MUST]` AC-05: Running `setup-agent --force` twice in a row SHALL leave exactly one
  applyr block in the file.

#### PR 2 — Core block and `applyr guide`
- `[MUST]` AC-06: `setup-agent` SHALL inject the core instructions, not the full
  document. The core states the core principles, `applyr next`, the steps where the
  agent must stop for the user, and how to reach `applyr guide` and `applyr role`.
- `[MUST]` AC-07: The core SHALL be at most 100 lines.
- `[MUST]` AC-08: `applyr guide` SHALL list every slug with a one-line description.
  `--json` returns `{"steps": [{"slug", "title"}]}`.
- `[MUST]` AC-09: `applyr guide <slug>` SHALL print the matching section of the
  packaged full instructions, from its heading up to the next heading of the same or
  higher level. `--json` returns `{"slug", "title", "content"}`.
- `[MUST]` AC-10: Every slug SHALL resolve to a heading in the packaged document. A
  slug with no matching heading is a test failure, not a runtime surprise.
- `[MUST]` AC-11: `applyr guide` SHALL work before `applyr init` has run.
- `[MUST]` AC-E1: Given an unknown slug, When `applyr guide <slug>` runs, Then it
  exits with `invalid_value` and `details.valid` lists the slugs.
- `[MUST]` AC-12: An injected core block SHALL still be version-stamped, so a core
  from an older release reads as stale exactly as a full block did.

#### PR 3 — New and corrected targets
- `[MUST]` AC-13: `--agent gemini|copilot|windsurf|cline` SHALL write `GEMINI.md`,
  `.github/copilot-instructions.md`, `.windsurfrules` and `.clinerules` respectively,
  creating parent directories when needed.
- `[MUST]` AC-14: `--agent cursor` SHALL write `.cursor/rules/applyr.mdc` with its
  `alwaysApply` frontmatter.
- `[MUST]` AC-15: IF a project `.cursorrules` exists THEN `--agent cursor` SHALL warn
  that Cursor is phasing it out and leave it untouched.
- `[MUST]` AC-16: `--global --agent cursor` SHALL exit with `invalid_value` and explain
  that Cursor has no global rules file. `~/.cursorrules` is never written.
- `[MUST]` AC-17: `--global` SHALL support `claude`, `claude-skill`, `gemini` and
  `opencode`, and reject the rest with `invalid_value` listing those four.
- `[MUST]` AC-18: Auto-detection (no `--agent`) SHALL also recognise `GEMINI.md`,
  `.github/copilot-instructions.md`, `.windsurfrules` and `.clinerules`, after the
  existing Claude, Cursor and `AGENTS.md` checks.

#### PR 4 — Claude Code skill
- `[MUST]` AC-19: `--agent claude-skill` SHALL write `.claude/skills/applyr/SKILL.md`
  (`~/.claude/skills/applyr/SKILL.md` with `--global`). The file has frontmatter
  `name: applyr` and a `description` that names job offers, CVs and applications, and
  its body is the core instructions.
- `[MUST]` AC-20: `claude-skill` SHALL never be chosen by auto-detection.
- `[MUST]` AC-21: Given an existing SKILL.md from an older version, When `--force`
  runs, Then the whole file is rewritten. Without `--force`, applyr reports it as
  stale and leaves it unchanged, like other targets.

### Edge cases
- A file containing two legacy blocks (from an old bug) → `--force` leaves exactly one
  current block.
- The target is a symlink → it is written through, like today.
- `guide` on a template missing from the package (broken install) → a structured
  `not_found` error, not a traceback.

### Out of scope
- `[WONT]` MCP server (deferred by the project owner).
- `[WONT]` Changing role files (`templates/agents/*.md`) or rewriting the substance of
  the full document beyond stable headings.
- `[WONT]` Auto-migrating existing injected blocks without `--force`.
- `[WONT]` Claude Code plugin / marketplace packaging.
