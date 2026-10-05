# Spec: Step Handoff Gates — artifact verification between pipeline steps

### Status: APPROVED
### Version: 1.0

Business contract only. No stack, architecture, file names, data schemas, algorithms or
function signatures here — those live in `plan.md`.

## Recovered context

- **Constitution:** the project keeps it at the repo root as `constitution.md` (not
  `docs/constitution.md`). Binding for this feature: *storage layer, not AI service*;
  *agent-native* (`--json` on every command, stable error codes to stderr);
  *no magic numbers in business logic*; **banned:** modifying
  `templates/AGENT_INSTRUCTIONS.md` without human approval, renaming/removing CLI
  commands, renaming/removing `--json` keys, adding LLM API calls.
- **Relevant ADRs:** [003 no-LLM-calls](../../docs/adr/003-no-llm-calls.md) (the agent is
  the brain; applyr never calls an LLM), [007 structured JSON errors]
  (../../docs/adr/007-structured-json-errors.md) (every failure carries a stable `code`),
  [011 evidence-based CV engine](../../docs/adr/011-evidence-based-cv-engine.md) (the
  deterministic grounding gate), [015 CLI-enforced pipeline gates]
  (../../docs/adr/015-cli-enforced-pipeline-gates.md) (the direct predecessor of this
  spec: "the CLI becomes the barrier; the prompt becomes a hint").
- **Governing decision:** [ADR-018 — Step Handoff Gates](../../docs/adr/018-step-handoff-gates.md).
- **Origin:** 2026-10-05, offer #299 (Teros AI). The generated CV's professional summary
  claimed the candidate "builds systems with LLMs and RAG using Python and LangChain".
  His only RAG/LangChain work is one exercise of the master's degree he is still taking.
  `cv verify` returned PASS (63/63), `cv review` returned 86 (READY TO SEND),
  `cv ats-check` 100/100, `cv keywords` 90% — every existing check passed, because none
  of them measures seniority framing. Root cause found afterwards: the agent skipped
  Step 5.7 (the Architect's tailoring plan, which is where "forbidden claims" are
  declared) and no step of the workflow verifies that the previous step produced its
  artifact. The adversarial Fact Checker role — the only prompt listing
  `incorrect_seniority: Level inflated from actual` as a blocker — is named as "Step 6b"
  in the role index but no step of the workflow invokes it; Step 6b runs the
  deterministic `cv verify` instead.
- **Decisions confirmed by Deiby (2026-10-05):**
  - The barrier lives in code, not in prose: `cv generate` refuses when the previous
    step's artifact is missing (replicating the `cv pdf` / `verify_required` pattern).
  - A new `cv gate` command reports the whole artifact checklist; `applyr next` gains the
    `plan` state.
  - The Fact Checker returns as a recorded pipeline step between the CV review and the
    verification step.
  - A deterministic framing lint is in v1: warning only, never a block.
  - No database migration: state is derived from artifacts and the existing review
    history.
  - Hard failures (structured error code, exit 1), not warnings, for missing artifacts.
  - Offers that already have a generated CV are never forced to produce a plan
    retroactively.

## What does it do?

Every step of the CV pipeline that is supposed to leave something behind must leave it,
and the next step proves it before starting. An agent can no longer move from
"decided to apply" to "generate the CV" unless a real tailoring plan exists for that
offer — and that plan must contain at least one forbidden claim, so it cannot be an
empty stamp. Conversely, an agent can no longer deliver a CV that was reviewed but never
adversarially fact-checked: the rendering step refuses until that check has been run and
recorded.

Two read-only commands make the state visible: `cv gate` returns the complete
artifact checklist for an offer (with `--json`), and `applyr next` returns `plan` as the
step that precedes generation. Both derive their answer from what is actually on disk
and in the recorded review history; neither stores a stage of its own.

A new deterministic warning catches the specific class of bug that motivated the
feature: technology terms that appear in the CV's professional summary but that the
profile only ever lists under projects or education. It never blocks — it tells the
writer to reframe.

## Users / actors

- **Deiby (end user):** wants a CV that says exactly what he has done, not what a
  keyword-matching heuristic rewards.
- **The calling agent (Matcher / Architect / Writer / Fact Checker / Recruiter):** runs
  the pipeline by invoking applyr; needs one command that answers "what is missing?".
- **applyr itself:** deterministic gatekeeper; never calls an LLM.

## User stories

- H1: As the calling agent, I want applyr to refuse generation when the Architect's plan
  is missing, so that I cannot silently skip the step that declares forbidden claims.
- H2: As the end user, I want a checklist command that shows which pipeline artifacts
  exist for an offer, so that a skipped step shows up as a missing artifact instead of a
  polished CV.
- H3: As the end user, I want the adversarial fact check recorded before the PDF can be
  rendered, so that inflated seniority claims are at least forced into the open.
- H4: As the writer, I want a deterministic warning when the professional summary claims
  a technology the profile only has in projects or education, so that I reframe it as
  learning or project work instead of professional experience.
- H5: As the end user, I want offers that already have a CV to keep working, so that
  adding this gate does not strand 24 existing CVs.

## Boundaries

**Always do:**
- Derive every gate result from artifacts and recorded data at call time — never trust a
  stored "done" flag (an edited file must re-fail).
- Keep the failure structured: stderr message + stable `code` + exit 1, per ADR 007.
- Keep applyr deterministic: no LLM call is added anywhere (ADR 003).
- Keep the framing lint advisory: it never changes a pass/fail verdict.

**Ask first (do not proceed unilaterally):**
- Adding a database column, table or migration for step state.
- Making any existing warning upgrade to a hard block.
- Changing the meaning or the name of an existing pipeline state.

**Never do:**
- Make the gate depend on a claim the agent makes about having worked; only on
  artifacts a tool can read.
- Force a plan or a fact-check onto offers whose CV was generated before this feature.
- Block a delivery on the framing lint.
- Add a bypass flag that leaves no trace (every bypass must be visible on the offer).

## Acceptance criteria

#### The Architect's plan becomes a required artifact
- `[MUST]` AC-01: WHEN generation is requested for an offer with no valid plan for that
  offer, THE system SHALL refuse with exit 1 and a stable structured error code, and
  SHALL NOT write a CV file.
- `[MUST]` AC-02: WHEN generation is requested for an offer whose plan is valid, THE
  system SHALL generate the CV exactly as it does today.
- `[MUST]` AC-03: THE system SHALL consider a plan valid only when it exists for the
  requested offer AND declares at least one forbidden claim; a plan with an empty
  forbidden-claims list SHALL be treated as missing.
- `[MUST]` AC-04: WHEN generation is explicitly forced, THE system SHALL generate the CV
  AND append a dated, human-readable line to the offer's notes naming the bypass, so
  that it is visible when the offer is shown later.
- `[MUST]` AC-05: WHEN an offer already has a generated CV, THE system SHALL NOT require
  a plan for it — neither generation, nor the checklist, nor `next` SHALL strand it.
- `[SHOULD]` AC-06: WHEN a valid plan exists but was written for a different offer, THE
  system SHALL treat it as missing for this one.

#### Visibility: `cv gate` and `next`
- `[MUST]` AC-07: THE `cv gate` command SHALL report, for one offer, each CV-pipeline
  step and whether its artifact exists, is valid, or is not applicable, and SHALL exit 1
  when a required artifact is missing.
- `[MUST]` AC-08: `cv gate --json` SHALL return the same information as a machine-
  readable object, with a stable shape and no human-readable-only text.
- `[MUST]` AC-09: WHEN a scored offer with no CV and no valid plan is asked for its next
  step, THE system SHALL return `plan` as the next step, positioned after the blind
  review and before generation, with the exact command to run.
- `[MUST]` AC-10: WHEN the plan already exists, `next` SHALL skip `plan` and return
  generation as the next step (today's behaviour is unchanged).
- `[SHOULD]` AC-11: WHILE an offer is mid-pipeline, `cv gate` SHALL also report the
  steps that are already satisfied, so a single call answers "where am I and what is
  missing".

#### The Fact Checker returns as a recorded step
- `[MUST]` AC-12: WHEN the recorded CV review has reached the ready-to-send verdict, THE
  system SHALL make the adversarial fact check the next required step, before
  verification.
- `[MUST]` AC-13: THE system SHALL derive the fact-check verdict from a recorded
  0-100 score using a named configuration constant — never from a verdict supplied by
  the agent.
- `[MUST]` AC-14: WHEN rendering the PDF for a CV that has no passing fact-check record
  newer than the file, THE system SHALL refuse with exit 1 and a stable structured error
  code, and SHALL NOT write the PDF.
- `[MUST]` AC-15: WHEN rendering is explicitly forced, THE system SHALL render AND append
  a dated bypass line to the offer's notes, exactly as the verification bypass does.
- `[MUST]` AC-16: WHEN an offer's recorded fact check did not pass, `next` SHALL return
  the fact check as the next step and SHALL NOT advance to verification.
- `[SHOULD]` AC-17: THE fact-check record SHALL live in the existing review history, and
  `cv gate` SHALL report it like any other artifact.

#### Deterministic framing lint
- `[MUST]` AC-18: WHEN the CV's professional summary names a technology that the profile
  lists but never under professional experience, THE system SHALL print a warning naming
  the technology and the section where the profile actually has it.
- `[MUST]` AC-19: THE framing warning SHALL NOT change the verification verdict, the
  exit code, or whether a PDF can be rendered.
- `[SHOULD]` AC-20: THE lint SHALL only consider technologies, never project names,
  employers, degrees or certifications.
- `[WONT]` AC-21: THE lint SHALL NOT decide whether a claim is honest — that judgement
  belongs to the recorded Fact Checker step.

#### Agent instructions and roles
- `[MUST]` AC-22: THE workflow instructions SHALL name the plan, the fact check and the
  checklist command in the steps where they are required, in the order they must run.
- `[MUST]` AC-23: EACH of the five shipped role prompts SHALL instruct the agent to run
  the checklist command before starting that role's own work.
- `[MUST]` AC-24: THE instructions SHALL state that a bypass must leave a trace on the
  offer, and SHALL NOT suggest skipping a gate.

#### Error handling
- `[MUST]` AC-E1: Given the plan file is missing, When generation is requested, Then
  the command exits 1 with a code an agent can branch on and a message naming the
  command that creates the plan.
- `[MUST]` AC-E2: Given the plan file exists but is unreadable or malformed, When
  generation is requested, Then the command fails with a distinct code rather than
  treating it as a valid plan.
- `[MUST]` AC-E3: Given an unknown offer id, When `cv gate` runs, Then it fails with the
  same "offer not found" behaviour as the other `cv` subcommands.
- `[MUST]` AC-E4: Given no CV file is linked to the offer, When `cv gate` runs, Then it
  reports generation and every later step as pending rather than crashing.
- `[MUST]` AC-E5: Given a CV with no embedded offer id, When rendering is requested,
  Then behaviour is unchanged from today (refused without `--force`).

## Edge cases

- **Offers already past generation** (24 CVs exist): all new requirements report as
  not-applicable, never as missing. `next` must not regress them to an earlier step.
- **A plan written for another offer** at the same company: rejected for this one —
  two offers at one company are two different tailoring decisions.
- **Plan edited after generation**: harmless; the gate only guards entry into
  generation, and a regenerated CV simply requires a plan that still exists.
- **File edited after a recorded review**: the recorded fact check older than the file
  does not count, same staleness rule the review already uses.
- **Two offers sharing a CV filename**: out of scope — the existing offer-id-in-file
  link already resolves this.
- **Agent runs `--force` on every call**: permitted but fully visible — every bypass is
  appended to the offer's notes, and `cv gate` keeps reporting the artifact as missing.
- **Empty or template plan** (headers with no content): treated as missing (AC-03).
- **Profile with no professional experience section**: the framing lint reports nothing
  rather than flagging every technology.
- **`NO_COLOR` / `--json`**: gate output must obey both like every other command.

## Out of scope

- `[WONT]` Storing step state in the database — no column, no migration (confirmed).
- `[WONT]` Making applyr judge honesty: no LLM call is ever added (ADR 003); the fact
  check remains a prompt the agent executes and records.
- `[WONT]` Re-running or re-recording reviews for offers that already have a CV.
- `[WONT]` Any change to scoring, thresholds, recommendation bands or `compatibility_pct`.
- `[WONT]` Enforcing the framing lint as a hard block, or scoring it.
- `[WONT]` Applying the gates to the pre-CV steps (scoring, blind review) — those
  already leave records.
- `[WONT]` Gate or checklist for the Visual UI's own pipeline stage column (ADR 013
  ownership).

## Completion criteria

- Every `[MUST]` AC has a passing automated test.
- Manual demo on a fresh offer: no plan → generation refused → plan written →
  generation succeeds → review recorded → fact check required → verify → PDF.
- Manual demo of retrocompat: `next` and `cv gate` on an offer that already has a CV
  never demand a plan.
- `pylint applyr/ --disable=... --fail-under=7.0` and the full test suite pass locally
  and on CI (3.11, 3.12, 3.13).
- ADR-018 written and linked from this spec.

## Open questions

- None — all clarifying questions were answered by Deiby on 2026-10-05 (see
  *Decisions confirmed by Deiby*).
