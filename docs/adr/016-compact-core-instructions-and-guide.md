# ADR 016 — Compact Core Instructions, `applyr guide`, and Native Agent Targets

**Status:** Accepted
**Date:** 2026-09-24
**Supersedes:** None (new decision)

> Numbering note: ADRs 012–014 live on the unmerged `feat/cc-visual-ui` branch;
> 015 is on `main`. This one takes 016.

## Context

`setup-agent` injects the full `AGENT_INSTRUCTIONS.md` — 565 lines, roughly 5k
tokens — into a project's agent file (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`).
Three problems follow from that:

1. **Every session pays for all of it.** An agent that only wants to log a status
   change still loads the scoring rubric, the JSON template, the Architect's
   output format and the ATS rules.
2. **It goes stale on every release.** The injected block is a copy. applyr shipped
   more than 25 releases in a month, and each one that touched the template made
   every injected copy out of date. This project has already shipped three fixes
   for stale copies (v0.8.3, v1.5.0, the `setup-agent --force` staleness fix).
3. **`--force` can destroy the user's text.** `strip_stamped_block` assumes the
   injected block is the last thing in the file and drops everything from the stamp
   to end of file. Anything the user wrote after the block is lost on refresh.

On top of that, `setup-agent` only knows Claude, Cursor (via `.cursorrules`, which
Cursor is phasing out), OpenCode and a generic `AGENTS.md`. Gemini CLI, GitHub
Copilot, Windsurf and Cline users get no native target, and Claude Code users have
no way to load applyr only when it is relevant.

[ADR 015](015-cli-enforced-pipeline-gates.md) already moved the pipeline order into
the CLI (`applyr next`). That makes most of the step-by-step prose redundant in
every session: the agent can ask applyr where it is, and read only that step.

## Decision

### 1. A small core block, the full document on demand

`setup-agent` injects a new `templates/AGENT_CORE.md` (about 80 lines):

- the core principles and the privacy note;
- the pipeline as one line per step, each with its command;
- `applyr next <id>` as the way to find your place;
- the points where the agent must stop for the user;
- the response format;
- how to get more detail: `applyr guide <step>` and `applyr role <name>`.

The full `AGENT_INSTRUCTIONS.md` stays in the package as the single source of the
detailed workflow. `init` still copies it to `~/.applyr/`, and `doctor` still checks
that copy for staleness.

### 2. `applyr guide [<step>]`

`applyr guide` lists a fixed set of stable slugs (`setup`, `score`, `decide`,
`recruiter`, `architect`, `generate`, `verify`, `deliver`, `ats-rules`, `errors`, …).
`applyr guide <slug>` prints that section of the **packaged** template, cut at its
heading. It always matches the installed version, so it cannot go stale. A test fails
if a heading changes and leaves a slug pointing at nothing.

Slugs are a fixed list rather than derived from heading text, because agents will
hard-code them. A reworded heading must not break those agents.

### 3. Explicit end marker for the injected block

The injected block keeps its version stamp as the first line and now ends with
`<!-- applyr-end -->`. `--force` replaces only what lies between the two, so text
before and after the block survives. A block injected by an older version has no end
marker. It is treated as running to end of file, as before, and applyr warns when
text after the last applyr heading does not look like part of the template.

### 4. Native targets

| `--agent` | Project file | `--global` |
|-----------|--------------|------------|
| `claude` | `CLAUDE.md` (or existing `.claude/CLAUDE.md`) | `~/.claude/CLAUDE.md` |
| `claude-skill` | `.claude/skills/applyr/SKILL.md` | `~/.claude/skills/applyr/SKILL.md` |
| `cursor` | `.cursor/rules/applyr.mdc` (frontmatter, `alwaysApply`) | not supported |
| `gemini` | `GEMINI.md` | `~/.gemini/GEMINI.md` |
| `copilot` | `.github/copilot-instructions.md` | not supported |
| `windsurf` | `.windsurfrules` | not supported |
| `cline` | `.clinerules` | not supported |
| `opencode` | `AGENTS.md` | `~/.config/opencode/AGENTS.md` |
| `generic` | `AGENTS.md` | not supported |

`claude-skill` writes a Claude Code skill. Its frontmatter `description` makes Claude
load it only when the conversation is about job offers, CVs or applications, so
sessions that never touch applyr pay zero tokens. The file belongs entirely to
applyr, so it has no markers and `--force` rewrites it whole. It is never
auto-detected.

`--global --agent cursor` stops writing `~/.cursorrules`, which Cursor does not read,
and fails with an explanation instead. An existing project `.cursorrules` gets a
warning but is left untouched.

## Consequences

**Positive**
- An injected block costs about 80 lines of context instead of 565 per session.
  `claude-skill` costs nothing until it is needed.
- The injected text barely changes between releases, so the stale-copy problem
  mostly goes away. The detail lives in the package and is served by `guide`, which
  always matches the installed version.
- `--force` becomes safe to run on files the user has edited around the block.
- Nine agent targets instead of four.

**Negative**
- **Behavior change:** users who refresh with `--force` get the core instead of the
  full document. An agent that never calls `guide` works with less context.
  Mitigated by putting the rules that must not be skipped (never invent, `verify`
  and `next`, the stop points) in the core itself.
- The fixed slug list is one more thing to keep in sync with the template. A test
  enforces it.
- The target table is a list of other tools' file conventions, which those tools can
  change.

**Neutral**
- No schema change, no new dependency, no LLM call (ADR 003).

## Alternatives considered

- **Keep injecting the full document.** No work, but every problem in Context stays.
- **Core block plus per-step files copied to disk.** The copies go stale exactly
  like the injected block did.
- **Slugs derived from heading text.** No maintenance, but a reworded heading
  silently breaks every agent that hard-coded the old slug.
- **MCP server.** Deferred by the project owner (2026-09-24). It would add a
  dependency, and applyr keeps a single dependency (colorama).
