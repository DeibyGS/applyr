# Agent Workflow

> The order of operations for an AI agent changing this codebase.

---

## Before writing code

Read in this order. Stop as soon as you have what you need — do not load all
five for a typo fix.

1. **[`mental-model.md`](mental-model.md)** — what applyr is and is not. Prevents
   changes that are well-implemented and conceptually wrong.
2. **[`../AGENTS.md`](../AGENTS.md)** — conventions, forbidden changes, how to add
   a command.
3. **[`contracts.md`](contracts.md)** — whether what you are about to touch is a
   public contract. **Always read this before any refactor or rename.**
4. **[`architecture.md`](architecture.md)** — module responsibilities and data flow.
5. **[`adr/`](adr/)** — why a decision was made, before you propose reversing it.

Never restate a number, enum value or file size from these docs into new code
or documentation without checking the source. Several such claims were wrong
until recently; assume the code is the truth and the docs are a summary.

## Choosing where to work

| Change | Location |
|--------|----------|
| CRUD command | `applyr/commands/core.py` |
| Analytics or report | `applyr/commands/analytics.py` |
| Export or system command | `applyr/commands/workflow.py` |
| Shared display helper | `applyr/commands/_helpers.py` |
| Scoring rule | `applyr/scoring.py` |
| Threshold or magic number | `applyr/constants.py` |
| Enum of allowed values | `applyr/db.py` |
| Schema change | `applyr/db.py` — via `MIGRATIONS`, never in place |
| Config option | `applyr/config.py` |
| Colored output | `applyr/colors.py` |
| CV or document template | `applyr/templates/` |

## Implementing

1. Locate the nearest existing command and copy its shape — connection in a
   `try`, `conn.close()` in `finally`, `as_json: bool = False` parameter.
2. Validate inputs against the `VALID_*` tuples in `db.py`. Do not invent new
   accepted values without adding them to the enum.
3. Keep numbers out of the logic. Name them in `constants.py`.
4. Export the function in `commands/__init__.py`.
5. Add the routing branch in `cli.py`, matching the surrounding `elif` style.
6. Support `--json` if the command returns data an agent would consume.

## Validating

Run all four. They are fast and CI enforces the first two.

```bash
pytest                                          # 54 tests, ~0.1s
pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801 --fail-under=7.0
applyr doctor                                   # config + DB health check
pip install -e . && applyr version              # install still works
```

If you added a command, also smoke-test it end to end against a scratch
database rather than your real one:

```bash
APPLYR_HOME=/tmp/applyr-test applyr init
APPLYR_HOME=/tmp/applyr-test applyr <your-command>
```

`APPLYR_HOME` is the isolation mechanism for anything touching config or the
database — in tests too. Without it you read and write the developer's real
job search data.

---

## Definition of done

A change is finished when every box is true. An unchecked box is unfinished
work, not a follow-up.

- [ ] `pytest` passes
- [ ] `pylint` passes at `--fail-under=7.0`
- [ ] New behavior has a test; fixed bugs have a regression test
- [ ] No public contract in `contracts.md` was broken, or an ADR explains why
- [ ] No hardcoded numbers introduced
- [ ] `--json` output added if the command returns data
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Docs updated where the change makes an existing statement false
- [ ] Every factual claim written into docs was verified against the source
- [ ] Diff stays under 400 changed lines, or is split into chained PRs

## Common tasks

### Add a CLI command
Files: `commands/<area>.py`, `commands/__init__.py`, `cli.py`, `tests/`,
`CHANGELOG.md`, `llms.txt` command table, `docs/cli-reference.md`.

### Add a scoring topic
Files: `TOPIC_LABELS` (`config.py`), `DEFAULT_WEIGHTS` (`constants.py`), TOML
template (`config.py`), `tests/test_scoring.py`, `contracts.md` topic list.
Note that adding a topic changes scores for existing users — weights are
normalized to sum 1.0, so every other topic's share shrinks.

### Add a schema column
Files: `db.py` (`SCHEMA_VERSION`, `MIGRATIONS`, `SCHEMA_SQL`), `tests/test_db.py`,
`contracts.md` column count, plus every doc stating the column count.
Migrations are additive only.

### Add a config option
Files: `config.py` (`_build_defaults` and the TOML template),
`applyr.toml.example`, `tests/test_config.py`, `contracts.md`.
Defaults must keep working with no config file present.

### Add an enum value
Files: the `VALID_*` tuple in `db.py`, `contracts.md` enum table, and any
`--help` text listing the options. Adding is safe; removing orphans rows.

---

## When to stop and ask

Open a question instead of a PR when the change would:

- break anything listed as a stable contract
- add a runtime dependency
- add a network call or an LLM API call
- alter `DEFAULT_WEIGHTS` or the scoring formula
- require a schema migration that drops or renames a column
- reverse a decision recorded in `adr/`

These need a human decision and an ADR, in that order.
