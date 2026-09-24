# Plan: Compact Agent Instructions, `applyr guide`, Native Agent Targets

### Affected files
| File | Action | Reason | PR |
|------|--------|--------|----|
| `docs/adr/016-compact-core-instructions-and-guide.md`, `docs/adr/README.md` | CREATE / MODIFY | Governing decision | 0 |
| `applyr/agent_instructions.py` | MODIFY | `END_MARKER`, marker-aware `strip_stamped_block` → `replace_block`, legacy trailing-text check | 1 |
| `applyr/commands/core.py` (`cmd_setup_agent`) | MODIFY | Write end marker; use `replace_block` | 1 |
| `tests/test_agent_instructions.py` | MODIFY | AC-01..05 | 1 |
| `applyr/templates/AGENT_CORE.md` | CREATE | Core block (≤100 lines) | 2 |
| `applyr/agent_instructions.py` | MODIFY | `packaged_core()`, `GUIDE_SLUGS` (slug → heading), `guide_section()` | 2 |
| `applyr/commands/workflow.py` | MODIFY | `cmd_guide` | 2 |
| `applyr/cli.py`, `applyr/commands/__init__.py` | MODIFY | `guide` routing (pre-init allowed, like `role`), help | 2 |
| `applyr/commands/core.py` | MODIFY | `setup-agent` injects core | 2 |
| `tests/test_guide.py` | CREATE | AC-06..12, AC-E1 | 2 |
| `applyr/commands/core.py` | MODIFY | `_AGENT_TARGETS`, `_AGENT_GLOBAL_TARGETS`, `_AGENT_DETECT_ORDER`, Cursor changes | 3 |
| `tests/test_setup_agent_targets.py` | CREATE | AC-13..18 | 3 |
| `applyr/templates/SKILL_FRONTMATTER` (inline constant) / `core.py` | MODIFY | `claude-skill` target | 4 |
| `tests/test_setup_agent_targets.py` | MODIFY | AC-19..21 | 4 |
| `README.md`, `docs/cli-reference.md`, `CHANGELOG.md` | MODIFY | Docs per PR | 1–4 |
| `pyproject.toml` (package data) | READ / MODIFY if needed | Make sure `AGENT_CORE.md` ships in the wheel | 2 |

### Dependencies
- No DB change. No new dependency.
- Reused: `stamp`, `find_stamped_version`, `is_stale`, `INJECT_SEPARATOR`,
  `role_instructions` (pattern for reading packaged templates), `die`/`warn`.

### Design
- **Block boundaries:** stamp line = start; `END_MARKER = "<!-- applyr-end -->"` =
  end. `replace_block(existing, new_block) -> str`: find the last stamp; if an
  `END_MARKER` follows it, splice between them (keeping the text after the marker);
  otherwise treat the block as running to end of file (legacy). Duplicate legacy
  blocks are handled by repeating until no stamp remains before re-appending.
- **Legacy trailing-text check (AC-04):** in a legacy block, take the lines after
  the last `## ` heading that the packaged template also contains. Warn if the
  block's tail contains a `## ` heading the template does not have.
- **Guide:** `GUIDE_SLUGS: dict[str, str]` maps slug to exact heading text.
  `guide_section(slug)` finds the heading line, takes its level (count of `#`), and
  slices until the next heading of level ≤ that. A test iterates `GUIDE_SLUGS` and
  asserts each heading exists (AC-10).
- **Core template:** `AGENT_CORE.md`, written by hand. It carries no stamp in the
  source; `stamp()` adds one at write time, as today.
- **Targets:** extend the tuples and dicts. Cursor: `_AGENT_TARGETS["cursor"] =
  (".cursor/rules/applyr.mdc",)`. `.cursorrules` gets a detect-only entry that warns.
  `claude-skill`: target path + `_SKILL_FRONTMATTER`; whole-file write, no separator
  or markers (the stamp goes right after the frontmatter so staleness still works).

### Explicit technical assumptions
- `find_stamped_version` / `is_stale` already work on a stamp that is not on line 1
  (it scans every line) → the SKILL.md stamp after the frontmatter is detected. If
  false → a dedicated check.
- Package data: `pyproject.toml` includes `templates/*` → verify with
  `python -m build` and a wheel listing in PR 2.

### Non-functional
- `applyr guide` is pure file I/O on the installed package: <100 ms.
- No network, no LLM (ADR 003).

### Risks
- Agents with only the core skip detail → the core carries the stop points and the
  never-invent rules, and `applyr next` covers ordering.
- Other tools change their file conventions → the target table is documented in
  ADR 016 and the CLI reference, so a change is a one-line table edit.
