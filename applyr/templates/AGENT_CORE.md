# applyr — Agent Instructions (core)

applyr is a local CLI that tracks job applications and builds ATS-safe CVs. You (the
agent) do the reading and writing; applyr scores, validates and remembers. This is the
short version. Full detail for any step: `applyr guide <step>` (`applyr guide` lists
them). Instructions for one role: `applyr role <name>`.

## Core Principles

1. **cv-master.md is the only source of truth.** Never invent skills, projects,
   metrics or experience.
2. **Prefer omission over guessing.** If the offer lacks a field, omit it.
3. **CLI output is authoritative.** Copy scores, recommendations, confidence and
   verdicts from applyr; never recompute them.
4. **Respect the user's thresholds.** Never override the configured minimums.
5. **The Recruiter is blind.** In `cv review-blind`, never reveal the Matcher's score.
6. **Every CV passes `cv review` and `cv verify`** before it reaches the user.
7. **Evidence beats keywords.** A keyword without evidence is worth less than a real
   experience well explained.

## Privacy

`cv-master.md` holds the user's full history. Reading it puts it in your context, under
your LLM provider's data policy — applyr itself never sends it anywhere. Say this to the
user once.

## Find your place: `applyr next <id>`

Run `applyr next <id> --json` whenever you pick up an offer or are unsure what comes
next. It returns `state`, the exact `command` and a `reason`. It is read-only and
derived from what applyr stores. When `needs_user_confirmation` is true, **stop and
ask the user** before running the command.

## Pipeline

| Step | Command | Guide |
|------|---------|-------|
| 1. Health check, read the profile | `applyr doctor` (exit 1 = fix first) | `health` |
| 2. Check duplicates | `applyr search --company "<name>"` | `duplicates` |
| 3. Score and register (Matcher) | `applyr add '<json with topics>'` | `score` |
| 4. Decide with the user | read `RECOMMENDATION` from `add` | `decide` |
| 5. Blind recruiter read | `applyr cv review-blind <id>`, then `--record <score>` | `recruiter` |
| 5.7 Tailoring strategy (Architect) | write `cv-<company>-plan.md` | `architect` |
| 6. Generate, fill, review | `applyr cv generate <id>`, `applyr cv review <file>` + `--record <score>` | `generate` |
| 6b. Verify grounding | `applyr cv verify <file>` (deterministic, exit 1 = BLOCKED) | `verify` |
| 7. Deliver | `applyr cv pdf <file>` (refuses unverified CVs) | `deliver` |
| After sending | `applyr update <id> applied --canal <channel>` | `deliver` |

Scoring: give each topic a `score`, a `detail` and a `confidence`. **Omit a topic the
offer does not mention — never score it 100.** Put only the offer's *mandatory*
requirements in the `eligibility` block — applyr forces LOW MATCH on a failed one.
Rubric and JSON template: `applyr guide score`.

## Stop and ask the user

- Step 4: whether to apply (always for MAYBE and LOW MATCH; LOW MATCH → suggest
  `applyr update <id> discarded`).
- Step 6: before `cv generate`, unless the blind read was STRONG_MATCH.
- Step 7: before `applyr update <id> applied` — only once they confirm it was sent.
- Never pass `cv pdf --force` unless the user explicitly asks.

## Review loops close only by editing

`cv review` and `cv verify` re-read the file on every call. Re-running them without
editing the file changes nothing. Apply the fixes, then run them again.

## Response format (after scoring)

```
COMPATIBILITY: X% (APPLY >= Y%, MAYBE >= Z%)
CONFIDENCE: <copied from applyr add>
STRENGTHS: ...
GAPS: ... (impact on score)
RECOMMENDATION: <copied from applyr add: APPLY | MAYBE | LOW MATCH>
NEXT ACTION: ...
```

## When something fails

Run `applyr doctor` first. Errors are structured (`--json` → `{"error": {"code", ...}}`):
fix what the message names and retry. More: `applyr guide errors`. ATS formatting rules
for the CV: `applyr guide ats-rules`.
