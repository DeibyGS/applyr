# Mental Model

> How to think about applyr before you change it.

Most wrong changes to this codebase come from a wrong mental model, not from
bad code. This page exists to install the right one.

---

## What applyr is

**A local database with a CLI in front of it.**

That is the whole thing. It stores job applications, computes a weighted score
from numbers you give it, and prints tables or JSON.

## What applyr is not

| It is not | Because |
|-----------|---------|
| An AI tool | It contains zero model calls. `grep -r "openai\|anthropic\|requests" applyr/` returns nothing |
| A CV writer | `cv generate` emits a markdown CV with YAML frontmatter. HTML+PDF is a render step |
| An ATS analyzer | It never parses or scores a job posting. It stores the score somebody else decided |
| A job scraper | It has no network layer at all. Offers arrive as JSON you hand to `applyr add` |
| A web app | No server, no API, no auth. One SQLite file at `~/.applyr/jobs.db` |

## The division of labor

```
  Agent (Claude, Codex, Cursor…)        applyr
  ──────────────────────────────        ──────────────────────────
  Reads the job posting                 —
  Judges the candidate fit          →   Stores the score
  Decides tech_stack = 80           →   Weights it against config
  Writes the CV content             →   Provides the ATS skeleton
  Interprets the trends             ←   Computes the aggregates
```

**The intelligence lives outside. The memory lives inside.**

The useful analogy is version control: git does not write your code, it
remembers it precisely and answers questions about it. Applyr does the same for
job applications. A pull request that makes applyr "smarter" is almost always
pointed in the wrong direction.

This is not a limitation to be fixed — it is the design. See
[`adr/003-no-llm-calls.md`](adr/003-no-llm-calls.md).

---

## Design principles

**Local-first.** Everything lives in `~/.applyr/`. No account, no sync, no
telemetry, no network call. A user's job search history is sensitive; it never
leaves their machine.

**One dependency.** `colorama`, and only for Windows terminal colors. Every
proposed dependency must justify itself against `pip install applyr` staying
instant and unbreakable.

**Explicit over implicit.** Thresholds live in `constants.py`, weights in
config, enums in `db.py`. If a number appears inline in business logic, that is
a bug.

**Stable interfaces.** CLI commands and `--json` keys are contracts. Additive
changes always; renames essentially never.

**Deterministic.** The same inputs and the same config produce the same score,
every time. No randomness, no time-dependent logic in scoring.

**Small modules.** Eight modules, each with one job. When `commands.py` reached
1646 lines it was split into a package — that is the ceiling to watch for.

---

## Anti-patterns

Each of these has a specific reason, not a stylistic preference.

**Opening SQLite outside `db.py`.**
`get_conn()` sets `PRAGMA foreign_keys = ON` and runs the schema-version check.
A raw `sqlite3.connect()` skips both, silently breaking cascade deletes and
letting an outdated client write to a newer database.

**Reimplementing the scoring math.**
`calculate_score()` is the only place weights are applied. A second
implementation drifts from the first, and users get different numbers from
different commands for the same offer.

**Inlining a threshold.**
`if score > 65` hardcodes what the user configured as `threshold`. Read it from
config, or name it in `constants.py`.

**Adding a network call.**
There is no HTTP layer, and adding one changes what applyr fundamentally is.
It needs an ADR first, not a PR.

**Mutating `SCHEMA_SQL` for an existing version.**
Fresh installs get the new shape, existing users get nothing, and the two
diverge with no migration to reconcile them. Bump `SCHEMA_VERSION` instead.

**Printing free text in a `--json` code path.**
Agents parse stdout. Any stray `print()` before the payload turns valid JSON
into a parse error. (Applyr already violates this on error paths — see the
known limitation in [`contracts.md`](contracts.md).)

**Editing `templates/AGENT_INSTRUCTIONS.md` to fit an internal refactor.**
That file is loaded at runtime by external agents on machines you do not
control. It is an end-user contract, not internal documentation.

---

## Reading the codebase

Follow the data, not the file tree:

```
applyr add '<json>'
   └─ cli.py            parses argv, routes to the command
      └─ commands/core.py   validates against VALID_* enums
         ├─ scoring.py      turns topic scores into one number
         │    └─ config.py  supplies the weights
         └─ db.py           writes the row, cascades topics
```

Every command follows the same shape: parse → validate → open connection →
work → close in `finally` → print (table or JSON).

Once you have seen one command in `commands/core.py`, you have seen all of
them. Start there.
