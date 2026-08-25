## Spec: Evidence-Based CV Engine

### Status: APPROVED
### Version: 1.0

### Recovered context

- **Project constitution** (`constitution.md`, `AGENTS.md`, ADR-003): applyr makes
  **zero LLM API calls** — it is a storage/computation layer, the calling agent is
  the brain. Everything in this spec (evidence parsing, claim extraction, alias
  matching) must be deterministic Python. No network layer, no API keys.
- **ADR-008 (MD-first CV pipeline)**: `cv generate` produces `cv-<slug>.md`
  (Markdown, not HTML). `cv review` parses Markdown directly. `.html` files remain
  readable for backward compatibility (dispatch by extension). This spec's
  `cv verify` follows the same dispatch pattern and parses Markdown as its primary
  format.
- **Schema state**: `SCHEMA_VERSION = 10` in `applyr/db.py`. Migration for this
  spec is v10 → v11, via the existing versioned migration system
  (`_run_migrations`). Editing `SCHEMA_SQL` in place is forbidden
  (`AGENTS.md` → Forbidden Changes).
- **Existing partial grounding**: `applyr/cv.py:153-196` (`_get_tailoring_hints`)
  already filters offer `tech_stack` against `cv-master.md` via lowercase
  substring match, labeling ungrounded terms `NOT INCLUDED`. This spec replaces
  its internals with the Evidence Graph (Component 3) while preserving its
  external contract (the `<!-- TAILOR -->` / `<!-- NOT INCLUDED -->` HTML-comment
  hints already embedded in the generated skeleton).
- **`offers` table already has `job_url`** (`applyr/db.py`) — this spec does NOT
  add a duplicate URL column; `job_description` is new, `job_url` is reused as-is.
- **cv-master.md structure** (`applyr/templates/cv-master-template.md`): flat
  `## SECTION` headings (CONTACT, PROFESSIONAL SUMMARY, WORK EXPERIENCE,
  EDUCATION, PROJECTS, CERTIFICATIONS, TECHNICAL SKILLS, LANGUAGES, ADDITIONAL).
  Within WORK EXPERIENCE / PROJECTS / EDUCATION / CERTIFICATIONS, entries start
  with a `**Bold Title — Context**` line followed by bullet points. Not
  machine-enforced — the parser (Component 2) must tolerate missing sections,
  missing bullets, and free-text deviation without crashing (see Edge cases).
- **No prior Engram memory** on evidence graphs, claim verification, or CV
  hallucination guards for this project — this is a new decision, not a
  continuation.
- **Corrected assumptions from Step 2** (confirmed with user before writing this
  spec): schema is v10 not v12; pipeline is MD-first not HTML-first; ADR-003
  ("no LLM calls") applies as a hard constraint, not a stylistic preference.
- **Session decision trail**: user explicitly chose the full Evidence Graph
  (Option A) over two lighter alternatives after a RADAR trade-off analysis, then
  chose "derive at runtime, don't persist the graph itself, but snapshot per-CV
  usage for audit" over persisting a cached `evidence_claims` table (rejected: a
  stale cache could make the truth gate approve/reject against claims that no
  longer match the live master — the one failure mode this feature exists to
  prevent).

### What does it do? (observable behavior, not implementation)

- When a user registers an offer with `applyr add`, they can now attach the
  original job posting text (`job_description`) alongside the Matcher's scored
  interpretation — the raw source survives, not just the LLM's summary of it.
- When `cv generate` builds the tailoring hints (`<!-- TAILOR -->` /
  `<!-- NOT INCLUDED -->`), the decision of what counts as "evidenced" comes from
  a structured parse of `cv-master.md` (skills, employers, dates, metrics as
  distinct claims) plus a curated alias dictionary (AWS ↔ Amazon Web Services),
  instead of a raw lowercase substring check on the whole file.
- A new command, `applyr cv verify <file>`, reads a generated CV and reports
  which factual claims in it (technologies, metrics, employers, job titles) are
  grounded in `cv-master.md` and which are not — deterministically, with no LLM
  judgment call required to get the answer. It exits non-zero and lists the
  unsupported claims when any are found, mirroring `doctor`'s exit-code
  contract. On a clean pass, it persists which evidence claims were verified for
  that CV onto the offer row, so `applyr show <id>` can later answer "what
  backed this CV" without re-parsing anything.
- `cv-master.md`'s file format does not change. Existing users on PyPI v1.11.1
  need zero migration to their profile file — only their local SQLite DB gets an
  additive schema bump (v10 → v11), same as every prior schema change.

### Acceptance criteria

Grouped by chained-PR component (see Task breakdown). AC IDs are
`AC-<PR>.<n>`.

#### PR1 — Raw job description storage + audit snapshot column

- `[MUST]` The system shall add a nullable `job_description TEXT` column to
  `offers` via schema migration v10 → v11.
- `[MUST]` The system shall add a nullable `cv_evidence_used TEXT` column (JSON
  array, stored as text — same pattern as the existing `weights_used` column) to
  `offers` in the same migration.
- `[MUST]` WHEN a database at schema v10 is opened THE system SHALL migrate it to
  v11 automatically via the existing `_run_migrations` path, with no user action
  required (same UX as every prior migration — see `HANDOFF.md` note on schema
  v12 needing a manual `init_db()` call: that was because the *frontend server*
  never called `init_db()` on startup, not a gap in the migration system itself;
  this spec does not touch that call site).
- `[MUST]` `applyr add '<json>'` shall accept an optional `job_description`
  string field and store it verbatim (no truncation, no transformation).
- `[MUST]` `applyr update <id>` shall accept an optional `--job-description`
  flag (or equivalent) to attach/replace the raw posting after the offer already
  exists, since it is not always available at `add` time (e.g. pasted from a
  second source afterward).
- `[SHOULD]` `applyr show <id> --json` shall include `job_description` and
  `cv_evidence_used` in its output when non-null.
- `[MUST]` Existing rows (job_description = NULL) shall continue to work through
  the entire pipeline exactly as today — `job_description` is informational
  input to Component 2/4, never a hard requirement in `add`, `cv generate`, or
  `cv verify`.
- `[WONT]` No backfill of `job_description` for existing offers. Historical
  offers keep NULL; only newly added/updated offers gain the field.

#### PR2 — Evidence Graph parser (`applyr/evidence.py`)

- `[MUST]` The system shall provide a pure function
  `parse_evidence(profile_text: str) -> list[EvidenceClaim]` with zero I/O and
  zero LLM calls (ADR-003).
- `[MUST]` The parser shall split `profile_text` on `## SECTION` headings
  (case-insensitive, matching the known section names in
  `cv-master-template.md`) and, within WORK EXPERIENCE / PROJECTS / EDUCATION /
  CERTIFICATIONS, treat each `**Bold Title — Context**` line as starting a new
  entry, with subsequent `-`/`*` bullets each becoming one `EvidenceClaim` tied
  to that entry.
- `[MUST]` Within TECHNICAL SKILLS and LANGUAGES, the parser shall extract each
  comma- or line-separated token as its own skill-type `EvidenceClaim` (no
  bullet/entry structure required there, matching the template's flat list
  style).
- `[MUST]` Each `EvidenceClaim` shall carry: an ephemeral `id` (stable only
  within one `parse_evidence` call, e.g. `EXP-001-C02`; never persisted as a
  foreign key — see Recovered context on why), `section`, `text` (verbatim,
  unmodified), and `entry_context` (the parent bold-line title, or None for
  flat-list claims).
- `[MUST]` WHEN a section is absent from `profile_text` THE parser SHALL skip it
  silently — cv-master.md is free text, not a validated schema; a missing
  CERTIFICATIONS section is not an error.
- `[MUST]` WHEN a line does not match any known pattern (stray prose, a
  guidance line like `...` left over from the template) THE parser SHALL ignore
  it rather than raising — malformed input degrades to fewer claims, never a
  crash.
- `[MUST]` The system shall define `PROTECTED_FACT_ALIASES` in
  `applyr/constants.py`: a curated `dict[str, list[str]]` of term ↔ equivalent
  forms (seed set: AWS/Amazon Web Services, PostgreSQL/Postgres,
  JavaScript/JS, Kubernetes/K8s, CI/CD/Continuous Integration — extensible,
  not exhaustive at launch).
- `[MUST]` The system shall provide
  `is_evidenced(term: str, claims: list[EvidenceClaim]) -> bool`, matching a term
  against claim text via lowercase substring AND `PROTECTED_FACT_ALIASES`
  expansion (checking every alias form, not just the literal term) — explicitly
  NOT fuzzy or semantic matching, per the RADAR decision to avoid the verifier
  itself hallucinating support.
- `[SHOULD]` `parse_evidence` shall complete in well under 100ms for a
  realistic `cv-master.md` (a few KB) — it runs on every `cv generate` and
  `cv verify` call, not cached (deliberate, see Recovered context).

#### PR3 — Tailoring plan (hardens `_get_tailoring_hints`)

- `[MUST]` `_get_tailoring_hints` in `applyr/cv.py` shall be reimplemented to
  call `parse_evidence` on `cv-master.md` and use `is_evidenced` for the
  highlight/not-included split, replacing the current raw
  `s.lower() in profile_text` substring check.
- `[MUST]` The external contract of `_get_tailoring_hints` (its return shape:
  `(highlight, de_emphasize, not_included)` lists of strings) and the
  `<!-- TAILOR -->` / `<!-- DE-EMPHASIZE -->` / `<!-- NOT INCLUDED -->` HTML
  comment output shall not change — this is an internal grounding upgrade, not
  a new user-facing feature. Existing callers (`cmd_cv_generate`) need no
  changes beyond the function body.
- `[MUST]` Given a tech_stack term with an alias present only in
  `cv-master.md` under its alternate form (e.g. offer says "AWS", master says
  "Amazon Web Services"), When tailoring hints are computed, Then the term
  shall appear in `highlight`, not `not_included` — this is the concrete bug
  the current substring-only check has today (confirmed in diagnosis).
- `[SHOULD]` Given `job_description` is present on the offer (PR1), the
  tailoring computation may additionally cross-reference offer-stated
  requirements pulled from the raw text, not just the structured `tech_stack`
  field — deferred to implementation judgment, not launch-blocking.

#### PR4 — `cv verify` command

- `[MUST]` The system shall add `applyr cv verify <file>` routed in `cli.py`,
  following the same file dispatch as `cv review` (`.md` primary,
  `.html` read-compatible via existing suffix checks in `cv.py`).
- `[MUST]` WHEN `cv verify` runs THE system SHALL resolve the offer via the
  existing `applyr:offer-id` frontmatter marker (same mechanism `cv review`
  already uses) and load that offer's data plus a fresh `parse_evidence` call
  over the current `cv-master.md`.
- `[MUST]` The system shall extract, from the CV file text, candidate factual
  claims in three categories: (a) technology/tool terms — matched against a
  vocabulary built from `PROTECTED_FACT_ALIASES` keys/aliases plus every skill
  token already present in the Evidence Graph; (b) quantitative metrics —
  regex-matched `\d+%`, `\d+x`, `\$\d[\d,]*`; (c) employer/project names and job
  titles — matched against `entry_context` values from the Evidence Graph.
- `[SHOULD]` The system shall additionally extract date ranges
  (`MM/YYYY`–`MM/YYYY` patterns) as a fourth claim category and verify them
  against evidence entry dates. Scoped `[SHOULD]` not `[MUST]`: free-text date
  formatting has more legitimate variation than tech terms or percentages, so
  it carries a higher false-positive risk for a first release — ship without it
  if the PR is otherwise ready, add in a follow-up once the tech/metric/employer
  gate is proven in real use.
- `[MUST]` For every extracted claim, the system shall check groundedness via
  `is_evidenced` (technology terms) or verbatim-in-claims matching (metrics,
  employer names, job titles) against the Evidence Graph.
- `[MUST]` WHEN every extracted claim is grounded THE system SHALL print a PASS
  report, exit code 0, and write the list of verified claim texts (not the
  ephemeral IDs — see Recovered context on why) to `offers.cv_evidence_used` as
  a JSON array.
- `[MUST]` WHEN one or more claims are unsupported THE system SHALL print a
  BLOCKED report listing each unsupported claim with its category, exit code 1,
  and SHALL NOT write to `cv_evidence_used` (a blocked run has nothing verified
  worth persisting).
- `[MUST]` The system shall support `--json` output following the project's
  existing `{"passed": bool, "claims": [...], "unsupported": [...]}`-shaped
  convention (exact keys decided at implementation time, but additive-only per
  `AGENTS.md` — never remove/rename a `--json` key once shipped).
- `[MUST]` `cv verify` shall make no LLM calls and require no agent-executed
  prompt — unlike `cv review`/`cv review-blind`, which print a prompt for the
  calling agent to execute, `cv verify`'s result is directly authoritative and
  final on exit (this is the core distinction: a deterministic gate vs. an LLM
  judgment call).
- `[SHOULD]` `applyr cv pdf` shall refuse to run (or warn loudly) when
  `cv verify` has not been run against the target file — deferred to
  implementation judgment on enforcement strength; not a hard gate at spec time
  because it changes existing user workflow (Step 7 of `AGENT_INSTRUCTIONS.md`
  already runs `cv pdf` automatically after review — wiring `cv verify` into
  that flow is a separate, deliberate decision the user should confirm
  explicitly before it becomes mandatory, not something this spec silently
  imposes).

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | Schema v10→v11 migration: add `job_description`, `cv_evidence_used` columns to `offers` |
| `applyr/commands/core.py` | MODIFY | `add`/`update` accept `job_description` field/flag |
| `applyr/evidence.py` | CREATE | `EvidenceClaim`, `parse_evidence`, `is_evidenced` — deterministic parser |
| `applyr/constants.py` | MODIFY | Add `PROTECTED_FACT_ALIASES` |
| `applyr/cv.py` | MODIFY | Reimplement `_get_tailoring_hints` internals; add `cmd_cv_verify` |
| `applyr/cli.py` | MODIFY | Route `cv verify` subcommand |
| `applyr/tests/test_evidence.py` | CREATE | Parser unit tests (section splitting, bullet extraction, alias matching, malformed input) |
| `applyr/tests/test_cv_verify.py` | CREATE | Command tests (PASS/BLOCKED paths, `--json`, snapshot write) |
| `applyr/tests/test_db.py` | MODIFY | Migration v10→v11 test |
| `docs/adr/011-evidence-based-cv-engine.md` | CREATE | ADR recording this architectural decision (required — this is architecturally significant per `~/.claude/rules/adr-convention.md`) |

### Dependencies

- DB: `offers` table (`applyr/db.py`), migration system (`_run_migrations`,
  `SCHEMA_VERSION`).
- Existing frontmatter offer-id marker mechanism (`cv.py`, used by `cv review`)
  — reused by `cv verify`, not reinvented.
- `cv-master.md` reader (`get_cv_master_path`, existing).
- No new PyPI dependencies (ADR-005, single-CLI/one-dependency rule).
- No LLM API, no network calls (ADR-003).

### Explicit assumptions

- We assume `cv-master.md` roughly follows `cv-master-template.md`'s section
  structure → if a user has heavily customized headings, the parser degrades to
  fewer extracted claims (not a crash), and `cv verify` will report more
  "unsupported" claims than are actually true. Mitigated by the parser being
  permissive (skip unknown patterns) rather than strict.
- We assume the ephemeral evidence-claim ID is never needed outside a single
  `parse_evidence` call → if a future feature needs stable cross-session claim
  identity (e.g. "user manually approved this exact claim once"), that requires
  a new decision, not covered here.
- We assume `cv_evidence_used` as a JSON-in-TEXT column is sufficient for the
  audit use case (human/agent reads it via `show --json`) → if querying across
  offers by evidence claim becomes a real need (e.g. "which CVs used my AWS
  claim"), that's a normalized table, deferred and out of scope.

### Non-functional requirements

- **Determinism**: `parse_evidence`, `is_evidenced`, and all of `cv verify`'s
  claim extraction must be pure/deterministic — same input always produces the
  same output, no LLM calls (ADR-003), consistent with the project's existing
  54-test deterministic suite philosophy.
- **Performance**: `cv verify` and the tailoring-hint computation must stay
  "instant" (ADR-003's existing framing) — no perceptible delay added to
  `cv generate`.
- **Backward compatibility**: schema migration is additive-only; nullable
  columns; existing installed users (PyPI v1.11.1) upgrade transparently on
  next `applyr` invocation, same as every prior migration.

### Edge cases / risks

- **cv-master.md deviates heavily from template structure** → parser extracts
  fewer claims than reality → `cv verify` over-reports unsupported claims
  (false positives, not false negatives — the safer failure direction for a
  truth gate). Mitigation: permissive parsing, `[SHOULD]` document
  recommended structure in `cv-master-template.md`'s existing guidance
  comments (no format change, just doc clarity) if this proves common in
  practice.
- **Alias dict is a fixed seed set** → a term not in `PROTECTED_FACT_ALIASES`
  and not verbatim in the master (e.g. "GCP" vs "Google Cloud Platform" if not
  seeded) is flagged unsupported even if arguably true. Mitigation: the dict is
  a plain Python constant, trivially extensible; document how to extend it in
  `AGENTS.md`.
- **Legitimate paraphrase blocked as "unsupported"** → e.g. master says "Built
  REST APIs with FastAPI", CV says "Developed backend services using FastAPI" —
  "FastAPI" is still matched (substring), but a paraphrased *responsibility*
  claim with no literal keyword overlap could false-positive as unsupported
  ONLY for tech/metric/employer categories that use literal matching. Bounded
  by design: this spec only verifies protected-fact categories (tech terms,
  numbers, employer/title names), not full-sentence claims — stylistic
  rewording of prose is explicitly out of scope (see Out of scope).
- **`cv_evidence_used` grows stale relative to a re-edited `cv-master.md`** →
  it's a snapshot of what was true at verify-time, by design (see Recovered
  context) — must be documented clearly as "verified as of this CV's
  generation," not "still true today," to avoid misleading the user later.

### Task breakdown (execution order — chained PRs, 500-line budget each)

1. [x] **PR1 — Schema + storage** (`db.py`, `core.py`, `cli.py`, tests) [M]
   Migration v10→v11, `job_description` + `cv_evidence_used` columns,
   `add`/`update --job-description`/`show --json` field support.
   Independently mergeable, no behavior change for existing flows.
   Implemented on branch `feat/cc-evidence-graph`; `simplify-lean` found no
   changes needed; ADR-011 written alongside it.
2. **PR2 — Evidence Graph parser** (`evidence.py`, `constants.py`,
   `test_evidence.py`) [M]
   Pure parser + alias matching, fully unit-tested in isolation, not yet wired
   into `cv.py`. Depends on PR1 only for branch base, not functionally.
3. **PR3 — Tailoring plan integration** (`cv.py` `_get_tailoring_hints`
   reimplementation) [S]
   Wires PR2's parser into the existing tailoring-hint code path. Small diff,
   same external contract — lowest-risk PR in the chain.
4. **PR4 — `cv verify` command** (`cv.py` `cmd_cv_verify`, `cli.py`,
   `test_cv_verify.py`) [L, consider splitting extraction vs. reporting if it
   approaches the 500-line budget]
   New command, claim extraction, PASS/BLOCKED gate, `cv_evidence_used`
   snapshot write.
5. **ADR-011** documenting the architectural decision, written alongside PR1
   (architectural context should land before the implementation chain, not
   after).

### Out of scope

- `[WONT]` Changing `cv-master.md`'s file format or requiring structured
  YAML/claim-ID authoring from the user.
- `[WONT]` Any LLM/semantic/fuzzy claim verification (ADR-003; RADAR decision
  favored the alias-dict approach explicitly to avoid this).
- `[WONT]` A persisted, cached Evidence Graph table (`evidence_claims` or
  similar) — rejected in favor of runtime-only parsing + per-CV audit
  snapshot.
- `[WONT]` Full-sentence/responsibility-level claim verification (e.g.
  verifying "led a team of 8" as a leadership claim) — this spec verifies
  protected-fact categories only (tech terms, metrics, employer/title names).
  Broader claim verification is a future spec if this proves valuable.
- `[WONT]` Making `cv verify` a mandatory gate inside `cv pdf` or the
  documented agent workflow (`AGENT_INSTRUCTIONS.md`) — that changes a
  protected, external-agent-facing contract file and needs its own explicit
  decision once `cv verify` has shipped and been used for real.
- `[WONT]` Date-range claim verification in the initial release (downgraded to
  `[SHOULD]`/follow-up, see AC-4.4 rationale).
- `[WONT]` Backfilling `job_description` for offers that already exist in a
  user's database.
