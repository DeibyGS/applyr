# Spec: MD-first CV pipeline and maintenance backlog

### Status: APPROVED
### Version: 1.0
### Target releases: v0.8.3 (phase 1) · v0.8.4 (phase 4) · v0.9.0 (phase 3)

---

## Recovered context

**Project constitution (`AGENTS.md`)**
- Applyr works *with* AI agents, not *through* them. No LLM API calls (ADR 003).
- Python 3.11+, `X | Y` unions, standard library plus a single runtime dependency (ADR 005).
- `applyr/templates/AGENT_INSTRUCTIONS.md` is marked **DO NOT MODIFY** for agents working
  on the codebase. Phase 1 changes how that file is *distributed*, not its prose.

**Relevant ADRs**
- **ADR 003 — no LLM calls**: rules out "let a model convert the markdown".
- **ADR 005 — single CLI, one dependency**: rules out adding `markdown` or `mistune` from
  PyPI for the md→HTML step in phase 3.
- **ADR 006 — errors to stderr**: every failure path ends in `die()`.
- **ADR 007 — structured JSON errors**: new failures need a stable `code`.
- ADRs are immutable once accepted; phase 3 adds **ADR 008**, it does not edit an existing one.

**Contracts at stake (`docs/contracts.md`)**
- stdout is data, stderr is errors and warnings.
- `doctor` is the documented exception: its report is data on stdout, and it exits 1 when a
  blocking issue exists. It must never mutate what it inspects.
- `offers.cv_used` holds **the filename of the CV sent** for that offer. `cv stats` computes
  response and interview rates grouped by that value, over sent offers only.

**Engram**
- No prior decisions on a markdown-first CV pipeline. This is new ground.

**Current state (v0.8.2)**
- 145 tests · pylint 9.41 · coverage 35% with no `fail_under` gate.
- `cli.py` sits at 0% coverage over 233 statements.

**Corrected assumptions from Step 2**
- None. All 19 assumptions were confirmed as written on 2026-08-08.

---

## What does it do? (observable behavior)

Four independent phases, one PR each, merged in order.

1. **Phase 1** — `applyr` stops propagating stale agent instructions. When the installed
   package is newer than the local copy of `AGENT_INSTRUCTIONS.md`, `setup-agent` emits the
   packaged version and says so, and `doctor` reports the drift.
2. **Phase 2** — the `cli.py` command router gains a real test suite, closing the blind spot
   that produced three of the bugs found in session 11.
3. **Phase 3** — the CV pipeline becomes markdown-first: `cv generate` produces a `.md`
   draft, `cv review` reads markdown, and HTML plus PDF are rendered only at the end.
4. **Phase 4** — the write-only `skill_gaps` table is removed and Python 3.11 joins the
   supported matrix.

### Execution order (deviates from the numbering, deliberately)

Phases run **1 → 2 → 4 → 3**, not 1 → 2 → 3 → 4:

- Phase 2 builds the router tests that make phase 3 safe. Phase 3 rewires `cv` routing in
  `cli.py`, and doing that against 0% coverage repeats the exact mistake of session 11.
- Phase 4 is cheap, self-contained, and carries a destructive migration. Landing it before
  the large breaking change keeps the two migrations out of the same release.
- Phase 3 lands last and alone, as v0.9.0, so the breaking release contains one idea.

---

## Phase 1 — AGENT_INSTRUCTIONS refresh (v0.8.3)

### The bug, confirmed in code

- `commands/core.py:80-81` — `_get_agent_instructions()` returns the local copy the moment it
  exists, never consulting the packaged template.
- `commands/core.py:167` — `cmd_init` writes the file only `if not agent_instructions_dst.exists()`.

There is no update path. `setup-agent` therefore copies instructions from an arbitrarily old
applyr version into the `CLAUDE.md` of every other project. A manual workaround was applied
on 2026-08-07 (backups at `~/.applyr/*.bak-20260807`); this phase replaces it with a fix.

### Acceptance criteria

- `[MUST]` **AC-1.1** — The system shall stamp instructions with an
  `<!-- applyr-version: X.Y.Z -->` marker on their first line, **applied at write time**
  rather than stored in the shipped template.
  *Revised during implementation (2026-08-08).* The original wording stamped the template
  file itself, which would have added a third place to bump on every release — and the first
  release that forgot would ship a template claiming the wrong version. Observable behavior
  is identical; the failure mode is gone.
- `[MUST]` **AC-1.2** — WHEN `init` writes `~/.applyr/AGENT_INSTRUCTIONS.md` for the first
  time THE system SHALL write the stamped packaged content verbatim.
- `[MUST]` **AC-1.3** — WHEN `setup-agent` runs AND the local copy's stamp is absent or older
  than `applyr.__version__` THE system SHALL emit the **packaged** instructions and warn on
  stderr naming both versions.
- `[MUST]` **AC-1.4** — WHILE the local copy is stale THE system SHALL leave
  `~/.applyr/AGENT_INSTRUCTIONS.md` byte-identical on disk. `setup-agent` never rewrites it.
- `[MUST]` **AC-1.5** — WHEN the local stamp matches `applyr.__version__` THE system SHALL
  use the local copy, preserving hand edits.
- `[MUST]` **AC-1.6** — WHEN `doctor` runs AND the local copy is stale THE system SHALL
  report it as a **note**, not a blocking issue, and SHALL still exit 0 if nothing else is
  wrong. Stale instructions do not stop work.
- `[SHOULD]` **AC-1.7** — IF the local file exists without a stamp THEN the system SHALL
  treat it as stale rather than erroring, since every pre-0.8.3 file is unstamped.
- `[WONT]` — `init --force`. Rejected: it only helps the user who already knows about the
  problem, which is precisely the user who does not need the fix.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/agent_instructions.py` | CREATE | Stamping and staleness comparison, shared by `core.py` and `workflow.py` — added during implementation, see note below |
| `applyr/commands/core.py` | MODIFY | `_get_agent_instructions()` compares stamps; `cmd_init` writes stamped content |
| `applyr/commands/workflow.py` | MODIFY | `_check_agent_instructions()` reports drift as note |
| `tests/test_agent_instructions.py` | CREATE | Cover AC-1.1 … AC-1.7 |
| `applyr/__init__.py` · `pyproject.toml` | MODIFY | Bump to 0.8.3 |
| `CHANGELOG.md` · `docs/contracts.md` | MODIFY | Document the distribution rule |

### Edge cases

- Local file stamped **newer** than the installed package (user downgraded) → treat as a
  match and use the local copy. Warning about the future is noise.
- Malformed stamp (`<!-- applyr-version: banana -->`) → treat as unstamped, therefore stale.
- `~/.applyr/` missing entirely → existing `init` path already covers it; no change.

---

## Phase 2 — `cli.py` router coverage (no release)

### Why here

Session 11's three bugs all lived in routing, not in command bodies: `init_db()` fired before
dispatch and silently recreated a deleted database, `doctor` always exited 0, and the CI never
ran pytest at all. A unit test calling `cmd_doctor()` directly cannot see any of them.

### Acceptance criteria

- `[MUST]` **AC-2.1** — Tests shall invoke `cli.main()` with a patched `sys.argv` and assert
  on captured stdout/stderr and `SystemExit.code`.
- `[MUST]` **AC-2.2** — Every command registered in the router shall have at least one test
  asserting it dispatches to the right function with the right parsed arguments.
- `[MUST]` **AC-2.3** — The global flags `--json` and `--no-color` shall be covered on at
  least one command each.
- `[MUST]` **AC-2.4** — The exit-code contract shall be covered: success 0, `die()` paths
  non-zero, `doctor` 1 when a blocking issue exists.
- `[MUST]` **AC-2.5** — WHEN a command other than `init` runs against a missing database THE
  tests SHALL assert the database is **not** recreated (regression guard for session 11).
- `[MUST]` **AC-2.6** — `cli.py` statement coverage shall reach **≥70%** (from 0%).
- `[SHOULD]` **AC-2.7** — Unknown command and missing-argument paths shall be covered.
- `[COULD]` **AC-2.8** — Bump `fail_under` once all four phases land, using the achieved
  floor. Deliberately deferred: setting it mid-series freezes a moving number.
- `[WONT]` — `subprocess` tests against the installed binary. The CI smoke test added in
  session 11 already covers that layer, and subprocess tests are slow and environment-bound.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `tests/test_cli_routing.py` | CREATE | The whole phase |
| `tests/conftest.py` | MODIFY | Shared fixture: isolated `APPLYR_HOME`, patched argv |
| `applyr/cli.py` | MODIFY | Only if the tests expose a real bug |

### Risks

- Tests that assert on exact output strings turn every copy tweak into a failing test →
  assert on structure and exit codes, and on substrings only where the wording is contractual.
- `calculate_score()` reads `~/.applyr/applyr.toml` (documented in `AGENTS.md`) → every test
  sets `APPLYR_HOME` to a temp dir. Never touch the real one.

---

## Phase 4 — Remove `skill_gaps`, add Python 3.11 (v0.8.4)

### Finding: the table is write-only

`cmd_add` still writes to it (`commands/core.py:439-442`) while `analytics.py:225`
(`_live_skill_gaps`) derives gaps from `offer_topics` and ignores the table entirely — a
change made in v0.5.0 and recorded in `CHANGELOG.md:93`. Rows accumulate and nothing reads
them. Removing the table therefore requires removing the write first.

### Acceptance criteria

- `[MUST]` **AC-4.1** — `cmd_add` shall no longer INSERT into `skill_gaps`.
- `[MUST]` **AC-4.2** — WHEN an offer is added with topics below threshold THE system SHALL
  still print the skill-gap notice. It is computed in memory (`core.py:466-468`) and its
  behavior must not change.
- `[MUST]` **AC-4.3** — A schema migration shall bump `schema_version` and `DROP TABLE
  skill_gaps`, without backup.
- `[MUST]` **AC-4.4** — WHEN the migration runs against a database that never had the table
  THE system SHALL succeed (`DROP TABLE IF EXISTS`).
- `[MUST]` **AC-4.5** — `gaps`, `plan` and `summary` output shall be byte-identical before
  and after the migration for the same data, proving nothing read the table.
- `[MUST]` **AC-4.6** — `requires-python` shall become `>=3.11`, and both CI workflows shall
  add 3.11 to the matrix.
- `[SHOULD]` **AC-4.7** — `tests/test_db.py` shall drop its `skill_gaps` assertions
  (`test_db.py:21`, `test_db.py:99-107`) and gain a migration test.
- `[WONT]` — Exporting the table to JSON before dropping. The data is an append-only counter
  nothing has consumed since v0.5.0.
- `[WONT]` — Python 3.10. EOL October 2026.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | Remove `CREATE TABLE` (`db.py:65`), add migration |
| `applyr/commands/core.py` | MODIFY | Remove the INSERT, keep the in-memory notice |
| `pyproject.toml` | MODIFY | `requires-python = ">=3.11"`, version bump |
| `.github/workflows/pylint.yml` · `python-package.yml` | MODIFY | Add 3.11 to matrix |
| `tests/test_db.py` | MODIFY | Drop table assertions, add migration test |
| `AGENTS.md` · `CHANGELOG.md` · `docs/architecture.md` | MODIFY | 4 tables → 3 |

### Risks

- `>=3.11` is a **compatibility widening**, not a break — but the code must actually run on
  3.11. `tomllib` is stdlib from 3.11, which was the only known blocker. CI proves the rest.
- The DROP is irreversible. Accepted explicitly on 2026-08-08.
- Session 11 noted the 3.13 runners were flaky. Adding 3.11 grows the matrix; if runners
  stall, that is a GitHub Actions problem, not a reason to revert the phase.

---

## Phase 3 — MD-first CV pipeline (v0.9.0, BREAKING)

### RADAR analysis

This decision is **architecturally significant**: it changes a public CLI contract, the shape
of generated artifacts, and the instructions every downstream agent follows.

**R — Requirements**

1. Cut the token cost of `cv review`. The agent currently reads HTML markup that
   `_strip_html_tags` (`cv.py:395`) discards anyway — the markup is pure overhead.
2. Keep CVs ATS-safe. The locked single-column CSS is non-negotiable.
3. Keep the offer→CV link intact: `cv review` resolves topic scores from the DB via the
   `applyr:offer-id` marker (`cv.py:443`).
4. Keep the A/B tracking of v0.7.0 working across the change (`cv stats`, `offers.cv_used`).
5. No new runtime dependency (ADR 005). No LLM calls (ADR 003).

**A — Alternatives**

- **A. MD-first, replacing HTML output.** `cv generate` emits `.md`; render to HTML+PDF at
  the end.
- **B. MD alongside HTML,** behind `--format md`. Both paths supported indefinitely.
- **C. Keep HTML, strip it before the agent reads it.** `cv review` already converts to
  plain text; make `cv generate` emit a plain-text view too.
- **D. Slim the HTML template.** Keep the format, cut the markup to the minimum.

**D — Differences**

| Criterion | A (chosen) | B | C | D |
|---|---|---|---|---|
| Token cost of the draft | Lowest | Unchanged by default | Low | Moderate |
| Public contract | Breaks `cv generate` output | Intact | Intact | Intact |
| Paths to maintain | One | Two, indefinitely | Two representations | One |
| Editing ergonomics for the agent | Best — markdown is native | Mixed | Poor: no canonical source | Poor: still markup |
| ATS safety | Enforced at render, centrally | Two renderers to keep aligned | Enforced at render | Unchanged |
| Migration cost | High, one-off | None | Low | None |

**A — Analysis**

Option A is chosen. B fails requirement 1 where it matters: the default path stays expensive,
and "two paths indefinitely" is the shape that later rots — the HTML branch would keep every
bug the MD branch fixes. C is a genuine cheap win, but it leaves the draft and the artifact in
two formats with no single source of truth, which is the actual defect. D reduces the symptom
and keeps the agent editing markup.

The cost is a one-off migration, paid once, at a pre-1.0 version where breaking a CLI contract
is cheapest it will ever be.

**R — Risks**

- A hand-rolled md→HTML converter is where correctness bugs will hide. Mitigated by keeping
  it deliberately narrow (see AC-3.7) and refusing unsupported syntax loudly.
- Existing `.html` CVs and their `cv_used` values must not be orphaned (AC-3.9, AC-3.10).
- `cv_used` migration touches real data in the live database.

### Acceptance criteria

- `[MUST]` **AC-3.1** — WHEN `cv generate <id>` runs THE system SHALL write
  `cv-<slug>.md` to the output directory and SHALL NOT write HTML.
- `[MUST]` **AC-3.2** — The generated `.md` shall carry YAML frontmatter holding the offer id
  and the offer context that today lives in HTML comments.
- `[MUST]` **AC-3.3** — WHILE topic scores contain candid self-assessment THE system SHALL
  keep them out of the generated file, as it does today (`cv.py:190-193`). `cv review` reads
  them from the DB via the frontmatter offer id.
- `[MUST]` **AC-3.4** — WHEN `cv review <file.md>` runs THE system SHALL parse markdown
  directly, without passing through `_strip_html_tags`.
- `[MUST]` **AC-3.5** — WHEN `cv pdf <file.md>` runs THE system SHALL render markdown to
  ATS-safe HTML and then to PDF in one invocation, applying the locked template CSS.
- `[MUST]` **AC-3.6** — The rendered HTML shall satisfy every ATS rule in `.claude/CLAUDE.md`:
  single column, no tables, no flexbox or grid, no images, full URLs, `|` as separator.
- `[MUST]` **AC-3.7** — The converter shall support exactly the subset the CV template
  produces: headings, paragraphs, unordered lists, bold, italic, links, horizontal rules.
  IF unsupported syntax is found THEN the system SHALL `die()` with a stable error code
  naming the line, rather than emitting silently wrong HTML.
- `[MUST]` **AC-3.8** — No new runtime dependency shall be added (ADR 005).
- `[MUST]` **AC-3.9** — WHEN `cv review` or `cv pdf` receives a `.html` file THE system SHALL
  process it with the existing logic. Read compatibility is preserved; only `cv generate`
  output changes.
- `[MUST]` **AC-3.10** — `offers.cv_used` shall store the basename **without extension**, and
  a migration shall strip the extension from existing values so `cv stats` keeps grouping
  the same CV across `.md`, `.html` and `.pdf`.
- `[MUST]` **AC-3.11** — `cv stats` response and interview rates shall be unchanged for
  existing data after the `cv_used` migration.
- `[MUST]` **AC-3.12** — WHEN `cv generate` would overwrite an existing draft THE system
  SHALL refuse unless `--force`, preserving the v0.8.0 fix.
- `[MUST]` **AC-3.13** — **ADR 008** shall be written before implementation, in the repo
  format, and `docs/adr/README.md` updated.
- `[MUST]` **AC-3.14** — `docs/contracts.md`, `docs/cli-reference.md`, `docs/agent-workflow.md`
  and `templates/AGENT_INSTRUCTIONS.md` shall describe the MD-first flow.
- `[SHOULD]` **AC-3.15** — `doctor` shall keep verifying Chrome, since PDF rendering still
  depends on it.
- `[WONT]` — Converting existing `.html` drafts to `.md`. They render and review as they are.
- `[WONT]` — Markdown beyond the template subset (tables, footnotes, images). Tables in
  particular are ATS-hostile and must stay unsupported.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `docs/adr/008-md-first-cv-pipeline.md` | CREATE | Architectural record, written first |
| `applyr/cv.py` | MODIFY | `cmd_cv_generate` emits md; `cmd_cv_review` parses md; `cmd_cv_pdf` dispatches by extension |
| `applyr/md_render.py` | CREATE | Narrow md→ATS-HTML converter |
| `applyr/templates/cv-master-template.md` | MODIFY | Align with the draft structure |
| `applyr/templates/cv-ats.html` | MODIFY | Becomes the render target, not the draft |
| `applyr/db.py` | MODIFY | `cv_used` extension-stripping migration |
| `applyr/cli.py` | MODIFY | `cv` subcommand routing and help |
| `tests/test_md_render.py` · `tests/test_cv_pipeline.py` | CREATE | AC-3.1 … AC-3.12 |
| `docs/*.md` · `AGENTS.md` · `CHANGELOG.md` | MODIFY | AC-3.14 |

---

## Dependencies

- **DB tables**: `offers` (`cv_used`), `offer_topics`, `schema_version`; `skill_gaps` dropped.
- **External binary**: Chrome headless, PDF only. Unchanged.
- **Runtime dependency**: `colorama`, and nothing else. Unchanged.
- **Config**: `~/.applyr/applyr.toml` — `cv_master` and `output_dir` point at `applyr/cv/`.
- **CI gates on `main`**: 4 required checks (pylint 3.12/3.13, package 3.12/3.13, growing to
  6 with 3.11 in phase 4).

## Explicit assumptions

1. `cv-master.md` stays markdown and stays the single source of truth → unaffected by phase 3.
2. No third party consumes applyr's generated HTML → if false, AC-3.9 read compatibility is
   the mitigation.
3. `applyr/cv/` and `*.pdf` remain gitignored; this is a public repo. Never `git add -f` them.
4. The manual workaround backups (`~/.applyr/*.bak-20260807`) can be deleted once phase 1 ships.

## Non-functional requirements

- **Performance**: `cv pdf` on a one-page CV completes in under 5 s including Chrome startup —
  no regression against today's HTML path.
- **Token cost**: the generated draft is ≥40% smaller in bytes than the equivalent HTML
  skeleton. This is the point of phase 3; measure it and record the number in the PR.
- **Compatibility**: applyr runs on 3.11, 3.12 and 3.13, proven by CI.
- **Safety**: no command other than `init` creates or mutates the database implicitly
  (session 11 contract). `doctor` never mutates what it inspects.
- **PR budget**: each phase stays within 500 changed lines. Phase 3 is the one at risk; if the
  forecast exceeds it, split with `/chained-pr` into converter, then pipeline rewiring.

## Task breakdown

**Phase 1 — v0.8.3** (PR 1) — **COMPLETE, pending PR**
1. [x] `agent_instructions.py`: stamping at write time, staleness comparison [S]
2. [x] Rewire `cmd_init` and `_get_agent_instructions` per AC-1.2 … AC-1.5 [S]
3. [x] Extend `_check_agent_instructions` as a non-blocking note [S]
4. [x] `tests/test_agent_instructions.py` (23 tests), bump, CHANGELOG, contracts [S]

*Implementation note:* the shared helpers went into a new `applyr/agent_instructions.py`
rather than staying private in `core.py`, because `workflow.py` needs the same staleness
comparison for `doctor` and importing a private helper across command modules would have
coupled them. The dead first path candidate (`repo_root/templates/`, a leftover from before
the v0.5.0 restructure — the directory does not exist) was removed rather than carried over.

**Phase 2 — no release** (PR 2)
5. `conftest.py` fixture: isolated `APPLYR_HOME` + argv patching [S]
6. `tests/test_cli_routing.py` covering dispatch, flags, exit codes, AC-2.5 guard [M]
7. Confirm ≥70% on `cli.py`; fix any bug the tests expose [S]

**Phase 4 — v0.8.4** (PR 3)
8. Remove the `skill_gaps` INSERT, keep the in-memory notice [S]
9. Migration: bump `schema_version`, `DROP TABLE IF EXISTS` [S]
10. Python 3.11 in `requires-python` and both workflows [S]
11. Update `test_db.py`, `AGENTS.md`, `architecture.md`, CHANGELOG [S]

**Phase 3 — v0.9.0** (PR 4, split if over budget)
12. Write **ADR 008** and get it approved before any code [S]
13. `md_render.py`: the narrow converter, with loud failure on unsupported syntax [M]
14. `cmd_cv_generate` → markdown draft with YAML frontmatter [M]
15. `cmd_cv_review` → markdown parsing; `cmd_cv_pdf` → extension dispatch [M]
16. `cv_used` extension-stripping migration + `cv stats` equivalence proof [S]
17. Tests, docs, `AGENT_INSTRUCTIONS.md`, CHANGELOG, token-size measurement [M]

## Out of scope

- `[WONT]` Scoring offer #17 (Galadrim). Data entry, not code.
- `[WONT]` The LinkedIn post.
- `[WONT]` Coverage targets for `analytics.py` (7%), `workflow.py` (49%), `core.py` (39%).
  Phase 2 is scoped to `cli.py`; the rest is a separate effort.
- `[WONT]` Setting `fail_under` during phases 1-3. Deferred to after phase 4 (AC-2.8).
- `[WONT]` Any change to the scoring formula or `DEFAULT_WEIGHTS` (ADR 004).
