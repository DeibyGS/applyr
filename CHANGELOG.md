# Changelog

All notable changes to applyr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.11.0] — 2026-08-21

### Changed

- **`company` is now required on `applyr add`**, the same way `title` already was. It used
  to be fully optional, which let an offer be saved with no way to ever match it as a
  duplicate again and nothing for a follow-up or per-company metric to attach to. If a
  posting hides the employer, use a placeholder like `"Empresa Confidencial"` instead of
  omitting the field. Schema v10 backfills any pre-existing empty/NULL `company` with a
  placeholder and adds a `NOT NULL` + non-empty `CHECK` constraint at the database level —
  migrations run automatically on the next `doctor`/DB-touching command, no action needed.

### Fixed

- **Migration chains could silently drop `offer_topics`/`learning_gaps` rows.** All pending
  migrations ran inside one shared transaction, so a `PRAGMA foreign_keys` toggle inside a
  later migration was a silent no-op if an earlier migration in the same chain had already
  opened one (any `UPDATE`/`INSERT` does). A table-rebuild migration under that condition
  would have its `ON DELETE CASCADE` fire on the implicit delete-all `DROP TABLE` performs
  on a table with active FK enforcement — wiping every child row before the parent was even
  dropped. Each migration step now commits on its own, closing that window. No released
  version shipped a migration that hit this path; it was caught in testing before release.

## [1.10.0] — 2026-08-21

### Added

- **Opt-in PyPI update check** — `check_updates = true` in `applyr.toml`'s `[general]`
  section makes `applyr doctor` check PyPI's public JSON API for a newer release (cached
  24h on disk, stdlib `urllib.request` only, 3s timeout) and print one line when a newer
  version is available. Off by default: a fresh `applyr init` makes zero network calls,
  and any failure (no connection, timeout, malformed response) is completely silent —
  `doctor`'s exit code and existing checks are unaffected. See ADR-010, which narrowly
  supersedes ADR-001's "no network call of any kind" clause for this single, auditable,
  non-telemetry case.

## [1.9.0] — 2026-08-19

### Added

- **`applyr export --redact` / `--redact-fields`** — export CSV/JSON/Markdown with
  sensitive fields stripped, so a real export can be shared publicly (e.g. as evidence
  in a blog post) without leaking company identity, contact info, salary, or notes.
  `--redact` alone uses a sensible default field set (including `cv_used` /
  `cover_letter_file`, which are slugged from the company name and would otherwise
  re-leak the identity `company` was just redacted for); `--redact-fields "a,b"`
  redacts exactly that list instead. Numeric columns redact to `null`, not a
  type-corrupting string, determined from the live schema rather than a hardcoded set.

### Fixed

- `cv ats-check`, `cv bullet-optimize`, and `cv keywords` crashed with a raw
  `UnicodeDecodeError` instead of a clear error when given a binary file (most
  commonly a rendered `.pdf` passed by mistake instead of its `.md`/`.html` source) —
  found auditing a real offer (Zinco, #235) on 2026-08-18. All three now die with an
  actionable message, and `ats-check`/`bullet-optimize` suggest the sibling `.md` or
  `.html` source file when one exists.

### Changed

- `stats`' score-calibration sample floor raised from 3 to 5 resolved offers per band
  — a rate computed from 3-4 offers read as more predictive than it actually is.

## [1.8.0] — 2026-08-16

Found and fixed during a live audit: the user ran applyr end-to-end against 7 real
LinkedIn job offers, and every finding below was independently reproduced against the
real database before being fixed.

### Changed

- **`cv_master` default location** moved from `~/.applyr/cv-master.md` to
  `~/Documents/applyr/cv-master.md`, alongside generated CVs. It's hand-edited often,
  unlike `applyr.toml`/`jobs.db`, so it follows the same reasoning `output_dir` already
  used: visible in a normal file browser without unhiding dotfiles. Backward-compatible —
  `cv_master` is already a standalone `applyr.toml` key, so existing installs keep their
  current path; only a fresh `applyr init` picks up the new default.

### Fixed

- Duplicate-detection's exact-match check (`find_exact()`) had no `ORDER BY`, so when
  multiple offers shared the same title+company, `add --force`'s block message could
  surface an arbitrary stale record instead of the most recent one.
- `cv cover-letter` always wrote in English regardless of the offer's language — now
  matches the language `cv generate` already used.
- `cv cover-letter`'s project-extraction triggered on the word "proyectos" appearing
  anywhere in cv-master.md (including intro prose, before the real `## PROYECTOS`
  section) and never turned back off, so it could pull job-history entries into the
  letter instead of actual projects — now requires a real `## ` section heading and
  turns off on the next one.
- `cv cover-letter` left project descriptions blank when cv-master.md wrote `**Stack:**`
  in bold instead of plain `Stack:`.
- `cv generate`'s `TAILOR` hint suggested prioritizing the offer's raw tech stack without
  checking whether the candidate's profile actually evidenced it, sometimes contradicting
  its own `DE-EMPHASIZE` line on the same topic. It now filters against the profile (same
  check `generate_cover_letter` already applied) and lists the rest under `NOT INCLUDED`
  instead of silently dropping them.

## [1.7.0] — 2026-08-15

### Added

- **`weights_used` snapshot** — every offer now stores the exact weights dict that
  produced its `compatibility_pct`, captured at `add` time. `NULL` for offers scored
  before this release or via an explicit `compatibility_pct` override — never backfilled,
  never guessed. This is what makes it safe to ever change `DEFAULT_WEIGHTS` again: past
  scores stay honestly labeled instead of silently meaning something different.
- **`applyr rescore <id>`** — recomputes an offer's `compatibility_pct` from its
  already-judged topic scores under the *current* weights. Never re-evaluates fit, only
  re-applies the weighting formula — useful after editing `[weights]` or upgrading to a
  new default.
- **`applyr add --json`** — `add` never had a JSON output mode; found by an independent
  adversarial-test pass and fixed the same day. Payload includes `weights_used`,
  `recommendation`, `confidence`, per-topic breakdown, and more.

### Changed

- **`DEFAULT_WEIGHTS` rebalanced**: `tech_stack` 30→35, `experience` 15→35, `projects`
  20→15, `education` 15→5, `english` 10→5, `cultural_fit` 10→5. Reflects that technical
  fit and experience predict job fit more than education for most roles (2025-26
  hiring-practice research). See [ADR 009](docs/adr/009-weight-versioning-and-rebalance.md),
  which supersedes [ADR 004](docs/adr/004-weighted-scoring.md)'s prohibition on changing
  this constant — that prohibition existed specifically because scores carried no record
  of which weights produced them; the `weights_used` snapshot above resolves that.

### Fixed

- `applyr stats`'s score-calibration bands, overall average compatibility, and
  `applyr summary`'s weekly average were all silently mixing `compatibility_pct` values
  computed under different (or unknown) weight configs into one number. All three now
  exclude offers with unknown weights and report how many were excluded.
- A bare `print()` in `add`'s "topic not in config" warning would have corrupted the new
  `--json` payload above; routed through the existing `warn()` helper instead.

Full changes: #65

## [1.6.0] — 2026-08-14

### Added

- **Score calibration in `applyr stats`** — buckets applied offers by score band
  (`threshold_apply`/`threshold_maybe`, the same bands `add`'s recommendation uses) and
  reports the real response/interview/offer rate per band. Answers whether a higher
  compatibility score actually predicts a better outcome, instead of assuming it does.
- **Per-topic `confidence`** (`high` | `medium` | `low`) alongside each topic's score and
  `detail`. `add`/`show` derive one overall confidence from the weakest per-topic value
  provided — never a fabricated default, `unknown` when none was given. Kept out of
  `scoring.py`: confidence is metadata, it never influences `compatibility_pct`.
- **`detail` (evidence) is now an expected norm**, not an afterthought — a scored topic
  with no justification prints a non-blocking warning.
- **PyPI Trusted Publishing** — releases now build, validate, and publish via GitHub
  Actions using OIDC, no API token stored in the repo.
- **Enforced coverage gate** — `pytest --cov` was measured but never gated; CI now fails
  a PR that drops total coverage below 75%.

### Changed

- **Threshold semantics unified.** The legacy `threshold` config key was silently
  disagreeing with `threshold_apply`/`threshold_maybe` in three places (skill-gap
  detection in `add`, `gaps`, and a config-migration edge case that ignored a user's
  custom legacy value entirely). All three now consistently use the real three-state
  system (APPLY ≥80%, MAYBE 60-79%, LOW MATCH <60%).
- **ATS claims reframed as heuristic.** "ATS score" is now "ATS compatibility score"
  everywhere, with an explicit disclaimer: no universal ATS score exists, and most
  recruiters report their ATS does not auto-reject on content — the anxiety around this
  was largely disconnected from how ATS platforms actually behave.

### Fixed

- A backward-compat bug in `config.py`: a user's custom legacy `threshold` value was
  silently ignored in favor of the 80/60 defaults, because the derivation check compared
  the already-merged config (which always had `threshold_apply` from defaults) instead of
  the user's raw file.
- Six duplicate inline enum-validation blocks in `cmd_add`/`cmd_update` consolidated into
  one shared `_validate_enum()` helper — no behavior change, same error shape.

Full changes: #59, #60, #61, #62, #63

## [1.5.3] — 2026-08-13

### Added

- **`search --company <name>`** for exact, case-insensitive company matching — the same
  definition `add`'s duplicate detection already used. Plain `search <keyword>` keeps its
  broad LIKE-based substring search across five fields; the two previously disagreed on
  what counted as "the same company," so following the documented duplicate-check
  workflow (`search` before `add`) could miss or over-match relative to what `add`
  actually blocked on.

### Fixed

- **`doctor` never reported a newer database schema than the installed applyr.** The only
  signal was a bare stderr line from `init_db()`, printed on every other command and
  disconnected from `doctor`'s structured health-check report — a human running `doctor`
  had no way to tell forward-compatibility apart from an actual problem. Added a
  dedicated schema-version check that surfaces as a labeled, non-blocking note.
- **Company name matching ignored diacritics.** "Mática Partners" and "Matica Partners"
  were treated as two different companies by both `add`'s duplicate warning and
  `search --company`, because the comparison only lowercased, never stripped accents —
  company history silently split across spellings. Diacritic-stripping carries none of
  the false-positive risk substring matching would (already rejected for company names —
  see `duplicates.py`); it can only make two spellings of the same company converge,
  never merge two different ones.
- **Generated CV filenames included the full job title**, truncated to 40 characters
  (e.g. `cv-acm-innovacion-y-personas-desarrollador.md`). Filenames are now company-only
  (`cv-acm.md`); a second offer at the same company — normal, not a duplicate — gets an
  automatic id suffix instead of colliding with or silently overwriting the first CV.
- **`cv pdf` never validated the ATS 1-2 page rule** it already states in its own review
  rubric — generation always reported success regardless of length. Added a page-count
  check after generation (parsed from the raw PDF bytes, no new dependency) with a
  non-blocking warning when the limit is exceeded, based on the offer's seniority.
- **`cv review-blind` scored the untailored source profile against finished-document
  criteria.** It reads `cv-master.md` fresh, before any CV is generated or trimmed for
  the offer — but reused the same rubric as `cv review` (which evaluates the tailored,
  generated CV), including "ATS Format Compliance" and "Length & Relevance" (1-2 pages).
  A master profile spanning a full career history will always fail a page-count check it
  was never meant to pass yet, dragging the score down regardless of candidate strength.
  Split into a dedicated rubric for the untailored profile.
- **`--json` printed human text instead of valid JSON on empty results**, breaking the
  "always parseable" contract every agent-facing command promises. Found in `search`; the
  same bug pattern was in six more commands (`list`, `pipeline`, `gaps`, `trends`, `plan`,
  `salary`) — all reached their JSON branch only when rows existed, so an empty result
  fell through to a human-only message regardless of `--json`.

## [1.5.2] — 2026-08-12

### Changed

- **Generated CVs and cover letters default outside `~/.applyr/`.** `output_dir` pointed
  inside the same hidden config directory as the database and `cv-master.md`, so the PDF
  a user needs to attach to a job application required unhiding dotfiles to find in a
  normal file browser. `cv_master`, the database and config stay in `~/.applyr/` — they
  are internal state, edited rarely; the new `CV_HOME` default (`~/Documents/applyr`,
  overridable via `APPLYR_CV_HOME`) is where the deliverable now lands. Existing
  installs are unaffected: `output_dir` is only a default, an `applyr.toml` that already
  sets it keeps doing so.

### Fixed

- **`cv keywords`, `cv cover-letter` and `cv review-blind` stopped finding files the
  moment `output_dir` or `cv_master` diverged from `~/.applyr/`.** All three hardcoded
  `APPLYR_DIR / "cv"` or `APPLYR_DIR / "cv-master.md"` instead of reading the configured
  path, so a custom `output_dir` (already a supported, documented config value) silently
  broke lookup and write for these three commands specifically — `cv generate` and
  `cv pdf` were unaffected, they already read the config correctly. Invisible in this
  project's own dev environment, where a real `cv-master.md` happens to sit at the
  literal `~/.applyr/` default; caught in CI, by the first test to ever exercise
  `cv cover-letter` end to end. Both now route through the same `get_output_dir()` /
  `get_cv_master_path()` helpers `cv generate` already used.

## [1.5.1] — 2026-08-12

### Fixed

- **`applyr response-rate` printed nothing at all.** The command is listed in
  `applyr help`, so silence read as a broken binary rather than an empty
  result. Two faults stacked: it filtered on `applied = 1`, a column no code
  path ever wrote, and its `--json` branch built the payload, returned it, and
  had no caller to print it. Both are fixed, and an empty database now says so
  instead of exiting quietly.
- **The `applied` column was never written.** `update` stamped `date_applied`
  and `follow_up_date` when an offer went out but left the flag at 0, so every
  offer looked unsent to the one query that reads it. It is now derived from
  the status on every update, in both directions — moving an offer back to
  pending or discarded clears it rather than leaving a stale 1.
- **`response_status` was never written either.** Added by the v1.4.0 schema
  and read by the analytics, but set by nothing, so every application counted
  as unanswered no matter what happened to it. Reaching `in_process`,
  `rejected` or `offer` now records the reply.
- **`date_applied` was only stamped for `applied` and `waiting`.** An offer
  taken straight to `rejected` — the reply arrives before the status is ever
  moved — ended up flagged as sent with no send date, and dropped out of the
  metric. Any status that means "this went out" now stamps it.
- **`response-rate --json` changed shape when empty.** It returned `total` on
  an empty database and `total_applications` everywhere else, so an agent
  needed two parsers for one command. The empty payload now carries the same
  keys as a populated one.
- **`doctor` contradicted itself.** It printed "All checks passed." directly
  below a check reading STALE. A note is still not an issue and still does not
  fail the run, but the summary now counts it.
- **The scoring rubric rewarded vague job postings.** `AGENT_INSTRUCTIONS.md`
  told agents to score an unmentioned requirement 100. `education` and
  `english` together carry 25% of the weight, so any posting that simply failed
  to mention them collected 25 free points — a vague ad outscored a detailed
  one describing the same job. The instruction now says to **omit** an
  unmentioned topic, which is what the engine already expected: it sums only
  the weights of the topics it is given, so omitting excludes the topic and
  redistributes its weight rather than counting it as a zero. On a real offer
  this was the difference between 70% (MAYBE) and 59% (LOW MATCH). Four tests
  pin the contract so the engine and the instructions cannot drift apart again.

- **`stats` and `response-rate` disagreed about what a response is.** Three
  definitions of "responded" coexisted, and two of them counted `waiting` —
  the status that means the application is out and nothing has come back, which
  is precisely why `update` schedules a follow-up for it. On a real 206-offer
  database the two commands reported 14% and 9% from identical rows. One
  definition now lives in `db.py` and both read it.
- **`gaps` marked every topic HIGH once the database grew.** Priority keyed off
  a fixed recurrence count (three sightings), so at a couple of hundred offers
  the ranking stopped discriminating — and it ignored how far short each topic
  fell, ranking a 30-point gap level with a 12-point one. Priority is now the
  gap's share of the worst gap, which reads the same at six offers and at six
  hundred, and the list is ordered by total impact so the ranking and the label
  cannot contradict each other.

- **`plan` and `gaps` disagreed about the same numbers.** `plan` ranked
  priority against fixed thresholds (200/100/40); `gaps` ranked it against the
  worst gap. On a real 207-offer database the weakest topic already scored
  415, so `plan` called all six topics CRITICAL while `gaps` spread the same
  six across HIGH/MEDIUM/LOW. Both now share one ranking function.
- **`Biggest weakness` was not always the biggest weakness.** The rule was
  "lowest partial, or else highest missing" — a topic scored 30 and printed
  under "Missing" two lines above could lose to one scored 50, and when
  everything was weak the *least* bad shortfall was reported as the problem.
  A test asserted the old behaviour (Experience 60 over Projects 30, "No
  relevant projects") — it was pinning the bug. Now the lowest score wins,
  wherever it falls.
- **`cv keywords` could not find a CV `cv generate` had just written.** It
  looked for files matching `*offer_<id>*`, a pattern nothing produces —
  `cv generate` names files `cv-<company-slug>.md` and records that name in
  `cv_used`. The command now reads `cv_used` first.
- **`cv keywords` then reported 100% on every CV, always.** Once the lookup
  worked, it matched the offer's required keywords against the *whole*
  generated file — including the YAML frontmatter, which carries a verbatim
  copy of the offer's own `tech_stack`. The offer's keywords were being
  matched against a copy of themselves. A CV mentioning neither AWS nor Redux
  nor Webpack was reported as covering all three, every time, for every CV
  applyr has ever generated. Matching now runs against the document body only.
- **`export` wrote the whole database into whatever directory the shell
  happened to be in.** Every company, score and private note, into the
  current working directory rather than `~/.applyr/`, where every other file
  applyr owns already lives. Run from a project checkout — as anyone working
  on applyr will — it drops an untracked file of personal job-search data one
  `git add .` away from being published.
- **The "database schema is newer" notice broke every `--json` command.** It
  used a bare `print()`, landing on stdout above the JSON payload and breaking
  the parse at character one for exactly the agent callers applyr is built
  for. `warn()` already existed for this; nothing called it.
- **The cover letter could assert a skill the candidate does not have.** It
  took the offer's first three technologies verbatim and wrote "With my
  background in `<them>`" — the candidate's profile was never consulted. On a
  real vacancy it produced "my skills in React.js, Redux, Hooks" for a profile
  with no Redux anywhere. A cover letter is sent to an employer, so this was a
  false claim made on the candidate's behalf — against the tool's own first
  rule, "never invent skills, projects, or experience." Key skills are now the
  overlap between what the offer asks for and what the profile contains.
- **An unrecognised command reported success.** `applyr <typo>` printed an
  error and exited 0, so `applyr <typo> && next-step` ran the next step
  regardless. The `cv` subcommand branch already handled this correctly;
  the top level did not.
- **Missing required arguments reported success, seventeen times over.**
  `show`, `update`, `delete`, `search`, `compare`, `gaps save`, and every `cv`
  subcommand printed a usage line and exited 0 — a command that did nothing
  reported having succeeded. `compare` proved it was an oversight: with no
  arguments it exited 0, with one argument (still not enough) it exited 1.
  Explicit `--help` still exits 0; only the missing-argument path changed.
- **`--sort` silently ignored anything it did not recognise.** Only raw
  database column names worked — `--sort compatibility_pct` sorted the list,
  `--sort score` returned it unsorted with no indication, and neither name
  was documented anywhere. `score` and `date` are now accepted aliases;
  anything else is a clear error.
- **`--limit -5` returned the entire database.** SQLite reads a negative
  `LIMIT` as unbounded, and `--all` was already built on that same accident
  (passing `-1` on purpose). `--all` now passes `0`, which existing code
  already treated as "no `LIMIT` clause," and a negative user-supplied
  `--limit` is rejected.
- **`followups` kept chasing offers that had already answered.** It checked
  `follow_up_done`, a column nothing in applyr ever sets, so the filter
  excluded nothing. Verified on a real database: an offer rejected three
  weeks earlier still listed as an OVERDUE follow-up. It now filters on
  `status IN ('applied', 'waiting')` — the two statuses that mean a reply is
  still owed.
- **`followups --json` broke on the one result it most needs to handle
  cleanly.** The "nothing pending" branch always printed the human sentence
  regardless of `--json`, hitting exactly the same class of bug already fixed
  in `response_rate`.
- **`setup-agent` could detect one config file and write to another.**
  `.claude/CLAUDE.md` and `.cursor/rules` are both valid detection signals,
  but the write target ignored which one was matched and always fell back to
  the top-level default. A project already using the nested file got a
  second, empty file created at the root while its real config — the one the
  agent actually reads — was left untouched.

### Changed

- Schema v7 backfills `applied` and `response_status` from the status on
  existing databases. `date_applied` is deliberately left alone — there is no
  honest way to invent a send date that was never recorded.
- `SENT_STATUSES` moved to `db.py` beside `VALID_STATUSES` and is now shared
  with `cv_stats`, so the column and the CV rates cannot drift apart.
- `SORT_FIELDS` in `commands/core.py` maps accepted `--sort` values to their
  column; `--sort` errors on anything outside that mapping instead of
  silently defaulting.

## [1.5.0] — 2026-08-11

### Added

- **`setup-agent --global`.** Writes the instructions to the agent's canonical
  per-user path — `~/.claude/CLAUDE.md`, `~/.cursorrules`,
  `~/.config/opencode/AGENTS.md` — so one run covers every project instead of
  the current directory only. It requires an explicit `--agent`: auto-detection
  reads the working directory, which says nothing about user-wide config.
  `generic` has no canonical global path and is rejected.

### Fixed

- **`setup-agent --agent opencode` wrote a file OpenCode never reads.** The
  target was `.opencode/instructions.md`, but OpenCode loads `AGENTS.md` at the
  project root and `~/.config/opencode/AGENTS.md` user-wide. The applyr contract
  therefore never reached the agent, silently. The target is now `AGENTS.md`,
  and a leftover `.opencode/instructions.md` raises a deprecation warning.
- **`cv ats-check` reported tables that were not there.** Every line containing
  a pipe counted as a markdown table row, so the `|` separators in contact
  details and project URLs — which the ATS rules themselves prescribe — were
  flagged as a layout the parser would choke on. Only rows that *start* with a
  pipe count now.
- **Generated CVs spilled onto a second page.** The default ATS CSS is tighter
  (10pt, 1.3 line-height, reduced padding), so a complete CV with three projects
  fits on one page, as the template intends.
- **`add --help` hid accepted fields.** `language` and `salary_period` are part
  of the `add` schema but were missing from the help output.
- **Distributed instructions carried two version stamps.** `agent_instructions`
  stamps the file at write time precisely so a release can never ship a template
  claiming the wrong version, yet the template itself stored a second stamp,
  frozen at `1.2.0`. Every written copy ended up with a correct marker and a
  stale one below it. The stored stamp is gone; the written one remains the only
  source. Staleness detection was unaffected — it only ever read the first line.

## [1.4.0] — 2026-08-10

### Fixed

- **`cv keywords` crashed on existing offers.** The null check was inverted
  (`if not offer is None`), so a present offer slipped past the guard and died
  with an internal error instead of an answer; a missing offer reported
  "found" and crashed on `dict(None)`. The check now reads `if offer is None`
  and fails with a clear `not_found` code.
- **`cv review-blind` read stale config keys.** Verdicts were computed from
  `general.threshold` (the legacy 65% default) and a nonexistent
  `maybe_threshold`, so they could disagree with the rest of applyr. It now
  reads `threshold_apply` (default 80) and `threshold_maybe` (default 60), the
  keys used since v1.0.0.
- **Two `cv ats-check` handlers were registered.** The duplicate definition at
  the end of `cv.py` shadowed nothing but confused readers; removed, one
  handler remains.

### Changed

- **A lone `applyr.toml` no longer counts as initialized.** `_is_initialized()`
  checks only that `jobs.db` exists, so a user who copied the example config
  still gets the "Getting started" onboarding instead of a bare usage string.
- **`applyr init` ships the full cv-master template.** The rich packaged
  template (`templates/cv-master-template.md`) was dead code — `init` wrote a
  bare stub from `core.py`. It is now loaded via `_cv_master_template_text()`
  with the packaged file as source of truth and the stub as fallback. Sections
  keep their `...` placeholders so the "unfilled profile" guard on `cv
  generate` keeps working on a fresh template.
- **`setup-agent` warns on an empty profile.** `_warn_if_profile_empty()` runs
  before writing agent instructions and surfaces a missing or unfilled
  `cv-master.md` at setup time, instead of letting the first failure appear
  mid-application.

### Tests

- 8 regression tests added covering every fix above (418 total).

## [1.3.0] — 2026-08-09

### Added

- **ATS compatibility checking** — `ats.py` with `validate_ats_format()` and
  `match_keywords()`, ruled by `ats_rules.json`.
  - `applyr cv ats-check <file>` — ATS score (0-100) and per-issue detail
  - `applyr cv keywords <id>` — keyword extraction and matching
- **Recruiter experience** — `applyr cv bullet-optimize <file>` (bullet quality
  analysis against `bullet_patterns.json`) and `applyr cv cover-letter <id>`
  (tailored cover letters from `cover_letter.md`).
- **Analytics** — `applyr cv compare <v1> <v2>` (ATS score delta, keyword
  coverage, word count) and `applyr response-rate` (overall, by status, and
  monthly trends), backed by a new `response_status` column (migration v5).
- **`constitution.md`** — project-level constraints for AI agents.

### Tests

- 31 tests added across `test_ats.py`, `test_analytics.py`,
  `test_cover_letter.py`, `test_cv_bullets.py` (412 total).

## [1.2.0] — 2026-08-09

### Added

- **Blind recruiter review** — `applyr cv review-blind <id>` evaluates an offer
  without the pre-computed compatibility score, simulating an outside reviewer.
- **Gap tracking** — new `learning_gaps` table (migration v5) and
  `applyr gaps save | list | stats` commands to record and monitor the skill
  gaps applyr detects.
- **Two-agent workflow** — `AGENT_INSTRUCTIONS.md` updated to orchestrate a
  reviewing agent and a writing agent.

### Tests

- 25 tests added for gaps and review-blind (381 total).

## [1.1.0] — 2026-08-09

### Added

- **`language` field on offers** (`en`, `es`): the language a CV is written in is
  a fact about the vacancy, so it is recorded with the offer rather than passed
  as a flag at generation time. `cv generate` writes the skeleton's headings in
  that language and tells the filling agent to use it throughout.
  - Falls back to `[cv] language` in `applyr.toml` (default `en`) when an offer
    does not declare one, so offers recorded before this release keep working.
  - Schema v4. `applyr show` displays it; `add` rejects a language applyr has no
    headings for, rather than silently producing an English CV.

### Fixed

- **`doctor` and `cv generate` accepted an unfilled cv-master.md.** Both judged
  the file by size (< 100 bytes meant "empty") and the template `init` writes
  weighs 94 — replacing the placeholder name with a real one was enough to make
  both report a filled profile. They now read the file: a section still holding
  the template's `...` placeholder is unfilled at any size. The check never
  matches section names, so profiles in any language pass.
- **Generated CVs mixed languages.** The skeleton hardcoded English headings
  while the agent wrote content in the language of the offer, delivering Spanish
  bullets under "Work Experience" — incoherent to the recruiter and invisible to
  an ATS scanning for "EXPERIENCIA".

## [1.0.0] — 2026-08-08

### Added

- **Three-state recommendation**: APPLY (>=80%), MAYBE (60-79%), LOW MATCH (<60%)
  - Configurable thresholds in `applyr.toml` (`threshold_apply`, `threshold_maybe`)
  - Backward compatible: old `threshold` still works
  - Colored output with icons: ✅ APPLY, ⚠️ MAYBE, ❌ LOW MATCH

- **Skill-level breakdown**: Strong (>=80%), Partial (50-79%), Missing (<50%)
  - Shown in `cmd_add` and `cmd_show` output
  - Icons: ✓ Strong, △ Partial, ✕ Missing

- **"Why you match" summary**: Top 3 strong topics + biggest weakness
  - Executive summary after recommendation
  - Helps user understand strengths and gaps quickly

- **CV tailoring hints**: HTML comments in generated CVs
  - Highlights skills to emphasize based on job requirements
  - Shows what to de-emphasize (low-scoring topics)
  - Tailoring summary in `cv generate` output

- **Score breakdown**: Weighted contribution per topic
  - Shows "Technical skills 80% × 30% weight = 24.0 contribution"
  - Explains why the total score is what it is

- 33 new tests for recommendation, breakdown, and tailoring logic

### Changed

- `cmd_add` output now shows recommendation, breakdown, and "Why you match"
- `cmd_show` output now shows breakdown, score breakdown, and recommendation
- `cv generate` output now shows tailoring summary

## [0.9.0] — 2026-08-08

### Changed

- **BREAKING: `cv generate` outputs `.md` instead of `.html`.** CVs are now
  drafted as markdown files with YAML frontmatter (offer_id, topic_scores,
  cv_master, date). The agent reads and edits markdown directly — no more
  stripping HTML tags to find the editable content

- **`cv_used` stores basename without extension.** The `offers.cv_used` column
  now stores `cv-acme-engineer` instead of `cv-acme-engineer.html`. Existing
  `.html` values are migrated via schema v2→v3

- **`cv review` and `cv pdf` accept both `.md` and `.html` files.** The commands
  dispatch by file extension. Legacy HTML files continue to work unchanged

### Added

- **`applyr/md_render.py`**: Narrow markdown→ATS-HTML converter. Supports
  headings (h1-h6), paragraphs, unordered lists, bold, italic, and links.
  Rejects tables, images, and ATX closing headings with stable error codes

- **ADR 008**: Documents rationale for markdown-first pipeline

- Schema migration v2→v3: strips `.html` extension from `cv_used` values

- 11 tests for `md_render` module, 2 tests updated for markdown output

### Fixed

- `cv_used` no longer stores file extensions, preventing double-extension
  bugs when agents pass the value to `cv review` or `cv pdf`

## [0.8.4] — 2026-08-08

### Fixed
- **Commands no longer recreate a missing database.** Running `applyr list` (or any
  command other than `init`) against a missing `jobs.db` now fails with a clear error
  message instead of silently recreating the database. This was a regression from
  session 11 that made `doctor` always exit 0

### Removed
- **`skill_gaps` table dropped.** The table was write-only since v0.5.0 — `cmd_add`
  wrote to it, but `_live_skill_gaps()` derives gaps from `offer_topics` and ignores
  the table entirely. Schema migrated from v1 to v2 with `DROP TABLE IF EXISTS`

### Changed
- **Python 3.11 now supported.** `requires-python` lowered from `>=3.12` to `>=3.11`.
  CI matrix expanded to test on 3.11, 3.12, and 3.13

### Added
- 115 tests for `cli.py` routing (AC-2.1 … AC-2.7), coverage 0% → 92%
- Regression guard tests ensuring no command recreates a missing database
- Migration test verifying `skill_gaps` table is dropped on upgrade

## [0.8.3] — 2026-08-08

`setup-agent` copies applyr's instructions into other projects' AI config, so a
stale local copy never stayed local — it propagated outdated guidance everywhere
it was run.

### Fixed
- **`AGENT_INSTRUCTIONS.md` no longer goes stale forever.** `init` wrote
  `~/.applyr/AGENT_INSTRUCTIONS.md` only when it was missing, and
  `_get_agent_instructions()` preferred that local copy unconditionally. Upgrading
  applyr therefore changed nothing: `setup-agent` kept emitting whatever the first
  install happened to ship. Instructions are now stamped with the applyr version
  that wrote them, and a stale copy is bypassed in favour of the packaged one

### Added
- **`doctor` reports instruction drift** as a `note` — visible, but not blocking.
  A stale copy does not invalidate the setup, because `setup-agent` already serves
  the packaged version, so it must not gate `applyr doctor && applyr cv generate`
- 23 tests covering stamping, staleness comparison and the distribution rules

### Notes
- The local file is **never rewritten**. It is the user's and may carry hand
  edits; silently overwriting it would be the mirror image of the bug being fixed.
  To refresh it, delete it and run `applyr init`
- A copy stamped by a *newer* applyr (the user downgraded) counts as current.
  Warning about the future is noise
- The stamp is applied when the file is written, not stored in the shipped
  template, so a release cannot ship a template claiming the wrong version

## [0.8.2] — 2026-08-07

`doctor` was the command v0.8.1 told every agent to run first, and it could not
fail. Two defects made it report a healthy setup no matter what.

### Fixed
- **`applyr doctor` exits `1` when the setup is unhealthy.** It always exited `0`,
  including while printing "3 issue(s) found", so `applyr doctor && applyr cv
  generate 3` built a CV from an empty profile without hesitating. This was
  already a contract violation: `docs/contracts.md` states that a command
  reporting a problem and exiting `0` is a bug. Chrome stays non-blocking — a
  missing PDF renderer does not invalidate the setup
- **`doctor` no longer recreates the database it is checking.** Every command
  except `init` ran `init_db()` before routing, so by the time the health check
  looked, a deleted `jobs.db` had been silently recreated and its `NOT FOUND`
  branch was unreachable. `doctor` is now excluded from that auto-init and
  observes the real state

### Added
- **`applyr doctor --json`** — `{"healthy", "issues", "checks": [...]}`, with a
  `status` of `ok`, `issue` or `note` per check. Agents read this command first;
  now they can parse it instead of scraping text
- 8 tests for `doctor`, which had none. `commands/workflow.py` coverage went from
  11% to 49%, and total from 32% to 35%

### Changed
- `docs/contracts.md` distinguishes a failed invocation from a command whose job
  is to render a verdict, and records that `doctor` must never mutate what it
  inspects — the ambiguity is what let both defects look acceptable
- `cmd_doctor` split into one function per check, clearing its
  `too-many-branches` and `too-many-statements` warnings (pylint 9.36 → 9.41)

## [0.8.1] — 2026-08-07

### Added
- **The test suite now runs in CI.** The `test` job only ever smoke-tested the
  CLI, so the unit tests never ran on a pull request — which is how seven of the
  eight bugs found in the v0.8.0 audit reached a release from modules with no
  coverage. `pytest --cov` now runs on 3.12 and 3.13
- **Coverage measurement** via `pytest-cov`, configured in `pyproject.toml`.
  Baseline is 32%: `cli.py` 0%, `commands/analytics.py` 7%,
  `commands/workflow.py` 11%. No `fail_under` gate yet — the floor gets set once
  those modules are covered
- Regression tests for `update --cv`, which had none

### Changed
- **`AGENT_INSTRUCTIONS.md` now opens with `applyr doctor`.** The health check
  already detected an unfilled `cv-master.md`, but the documented flow never ran
  it, so the check existed and nobody reached it. `doctor` is now step 1 of both
  setup and the per-offer workflow, and the entry point for error recovery
- **`applyr update <id> <status> --cv ""` stores `NULL` instead of `""`.**
  Clearing already worked; the empty string just left two different values
  meaning "no CV" in the database. Whitespace-only values clear too

## [0.8.0] — 2026-08-07

Thirteen bugs found by running one real job application end to end — register
offer, score, generate CV, review, PDF — then exercising every analytics
command and error path. Seven of the first eight lived in modules that had no
test coverage at all.

### Changed
- **`cv generate` refuses to overwrite an existing CV.** Regenerating used to
  replace finished, hand-tailored content with an empty skeleton, with no undo.
  Pass `--force` to opt in
- **`cv generate` rejects an unfilled `cv-master.md`.** The guard existed only
  in `doctor`, so generation succeeded and left the agent nothing to fill the
  placeholders from — a silent failure that could go unnoticed for weeks
- **`delete` requires `--force` when no terminal is attached.** It used to
  raise a bare `EOFError` traceback instead of a structured error
- Generated CVs no longer embed topic scores. Candid self-assessment shipped
  inside the file sent to the recruiter. `cv review` now resolves scores from
  the database through an `applyr:offer-id` marker, falling back to the old
  inline block for CVs generated by earlier versions
- The generated `applyr.toml` ships `cv_master` and `output_dir` uncommented
  and documented. Both were supported but invisible, so the CV workflow could
  not start and never said why

### Fixed
- Generated CVs spilled onto a second page. Chrome stacks its own default page
  margin on top of the body padding; the ATS template now sets
  `@page { margin: 0 }` and owns its margins
- `update <id> applied` never recorded `date_applied`, so `summary` always
  reported zero applications, the default `list` sort had nothing to sort on
  and follow-ups never came due. `COALESCE` preserves the first date across
  later transitions
- Skill gaps are derived from `offer_topics` instead of the `skill_gaps` table.
  That table is an append-only counter nothing decrements, so deleted offers
  inflated it forever and `plan` could recommend studying a topic that only
  ever existed in a test
- `_strip_html_tags` restarted from the original HTML when removing `<script>`,
  undoing the stylesheet removal and pushing the entire CSS into the review
  prompt. It now also strips HTML comments
- The config template hardcoded `~/.applyr`, which overrode the
  `APPLYR_HOME`-derived default and wrote generated CVs outside an isolated
  install. It now interpolates the real directory
- User-facing messages in `init`, `setup-agent` and the Chrome error print the
  actual path instead of a literal `~/.applyr`
- `applyr add --help` parsed `--help` as JSON instead of showing usage
- CV filenames keep only `[a-z0-9-]`; "Full Stack (JS)" produced names that
  needed shell quoting

### Added
- `tests/test_cv.py` and `tests/test_commands.py` — 24 regression tests, one
  per fix above, covering `cv.py`, `commands/core.py` and `commands/analytics.py`
- `.gitignore` now excludes `cv/` and `*.pdf`: this is a public repository and
  generated CVs carry personal data

## [0.7.0] — 2026-08-07

### Fixed
- Chrome failure paths in `cv pdf` called `sys.exit(1)` directly and printed to stdout, so they emitted nothing in `--json` mode and mixed diagnostics into parsed output. They now report through `die()` with a `chrome_failed` code and Chrome's stderr in `details`
- Removed unused imports left behind across `cv.py`, `commands/core.py`, `commands/analytics.py` and `commands/workflow.py`

### Added
- `applyr cv stats` — compare CVs by response rate (any reply, including rejections) and interview rate (reached `in_process` or `offer`). Flags samples below `--min-sample` as noise and reports offers with no CV recorded
- `applyr cv generate` now records the generated filename in `cv_used`, so CV tracking populates itself
- `--cv` flag on `applyr update`, to record a CV for offers applied to outside the `cv generate` flow
- `applyr/cv_stats.py` with 17 tests
- Structured JSON errors: with `--json`, failures emit `{"error": {"code", "message", "details"}}` on stderr so agents can branch on a stable code instead of matching English prose. See [ADR 007](docs/adr/007-structured-json-errors.md)
- `docs/adr/007-structured-json-errors.md`
- 15 tests for error routing, JSON mode and code stability

### Fixed
- Several error paths printed a message and returned instead of exiting, so commands like `applyr show abc` reported a failure but exited `0` — scripts and agents read that as success. All failure paths now exit `1`

## [0.6.0] — 2026-08-07

### Changed
- **BREAKING:** all error and warning output now goes to **stderr** instead of stdout. stdout carries data only, so `applyr <cmd> --json` emits either a valid JSON document or nothing. Scripts that captured stdout to read error text must now capture stderr (`2>&1`). See [ADR 006](docs/adr/006-errors-to-stderr.md)
- `applyr add` now blocks on near-identical offers at the same company, not only on exact title matches. `"Backend Engineer (Remote)"` is detected as a variant of `"Backend Engineer"`

### Added
- `--force` flag on `applyr add` to insert despite a detected duplicate — previously an exact duplicate had no escape
- `applyr add` reports previous offers at the same company without blocking, since applying to several roles at one company is normal
- `applyr/errors.py` — `error()`, `warn()`, `die()` helpers
- `applyr/duplicates.py` — title normalization and similarity matching, with work-mode qualifiers (`Remote`, `Hybrid`, `m/f/d`) stripped before comparison
- 23 tests for duplicate detection

### Documentation
- `docs/adr/` — 6 Architecture Decision Records: local-first, SQLite, no LLM calls, weighted scoring, single CLI, errors-to-stderr
- `docs/mental-model.md` — what applyr is and is not, design principles, anti-patterns
- `docs/agent-workflow.md` — reading order, definition of done, common tasks, when to stop and ask
- `docs/contracts.md` — stable contracts, invariants, extension points and the migration procedure
- "Forbidden Changes" section in `AGENTS.md`, expanded with the reason for each rule
- Linting instructions in `AGENTS.md` and `llms.txt` with the exact command CI runs

### Fixed
- `applyr/__init__.py` reported `0.5.0` while `pyproject.toml` declared `0.5.1`, so `applyr version` did not match the installed release. Both are now `0.6.0`
- Documentation stated `offers` had 28 columns and the database 3 tables — it has 31 columns and 4 tables (`offers`, `offer_topics`, `skill_gaps`, `schema_version`)
- Documentation described `scoring.py` as a pure function with no I/O — `calculate_score()` reads user config via `load_config()`, which tests must isolate with `APPLYR_HOME`
- `llms.txt` claimed no linter was configured — CI has run pylint since v0.4.0

## [0.5.1] — 2026-08-07

### Fixed
- Version bump to 0.5.1 (0.5.0 was already published on PyPI)

## [0.5.0] — 2026-08-07

### Changed
- **BREAKING:** Split `commands.py` (1646 lines) into `commands/` package (core, analytics, workflow)
- README redesigned with progressive disclosure, visual flow, scannable layout

### Added
- 54 pytest tests for scoring, config, db, validators
- Badges and AI Development Benchmark in README

### Fixed
- Duplicate detection before adding offers
- Threshold recommendation in `applyr doctor`
- Input validations across all commands
- Templates packaging in wheel

## [0.4.1] — 2026-08-06

### Added
- `applyr cv review <file.html>` — generates recruiter prompt with ATS scoring rubric
- Topic key validation in `cmd_add` — warns on unknown keys
- Full rewrite of `AGENT_INSTRUCTIONS.md` (scoring rubric, 4-step CV flow, error recovery)

## [0.4.0] — 2026-08-06

### Added
- `constants.py` — centralized magic numbers, thresholds, column widths
- `colors.py` — colorama wrapper with `NO_COLOR` support
- `--json` flag on all data commands
- Schema migration system in `db.py`
- `applyr doctor` — configuration and database health check

### Changed
- **First dependency:** colorama >= 0.4.6
- Exit codes now follow conventions (0=ok, 1=error)
- Error messages include actionable hints

### Fixed
- 18 bugs found during production quality audit

## [0.3.0] — 2026-08-06

### Added
- `applyr compare <id1> <id2> [idN...]` — side-by-side ASCII table (2-10 offers)
- `applyr plan [--limit N]` — prioritized learning plan from skill gaps
- `applyr salary [--seniority S] [--category C]` — salary stats by seniority/category
- `applyr setup-agent` — configure AI agent (claude, cursor, opencode, generic)
- Aliases: `cmp=compare`, `sal=salary`

### Changed
- `VALID_SENIORITY` expanded: added `trainee`, `entry_level`

## [0.2.1] — 2026-08-06

### Added
- Getting-started message for new users
- Quick-start section in README
- AI Development Benchmark documentation

## [0.2.0] — 2026-08-06

### Added
- Initial public release
- 17 commands, 28-column SQLite schema
- ATS CV generation with Chrome headless PDF
- Weighted compatibility scoring (6 topics)
- `--json` output for agent integration
- Published on PyPI as `applyr`

[0.5.1]: https://github.com/DeibyGS/applyr/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/DeibyGS/applyr/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/DeibyGS/applyr/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/DeibyGS/applyr/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/DeibyGS/applyr/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/DeibyGS/applyr/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/DeibyGS/applyr/releases/tag/v0.2.0
