# ADR 006 — Error output goes to stderr

**Status:** Accepted
**Date:** 2026-08-07
**Supersedes:** nothing. First ADR written before the change it describes.

## Context

Until v0.6.0 applyr wrote everything to stdout. Error messages, hints and data
shared one stream, and stderr was never used.

For a human this is invisible — the terminal shows both streams anyway. For the
primary consumer it is a defect. Per [ADR 003](003-no-llm-calls.md), agents call
applyr and parse `--json` output from stdout. When a command invoked with
`--json` failed validation, the output looked like this:

```
$ applyr add '{"title":""}' --json
Error: 'title' is required.
```

The agent receives text where it expected a JSON document, and gets a
`JSONDecodeError`. It cannot distinguish "the command failed" from "the output
is malformed", and the actual reason for the failure is unreachable through a
JSON parser.

This was documented as a known limitation in `docs/contracts.md` rather than
fixed silently, because fixing it changes observable behavior.

## Decision

All error output goes to **stderr**. stdout carries data only.

Two helpers in the new `applyr/errors.py`:

```python
def error(message: str) -> None:   # write to stderr, keep going
def die(message: str, code: int = 1) -> NoReturn:   # write to stderr, exit
```

This covers error messages and the indented hint lines that follow them
(`  Hint: ...`, `  Example: ...`). A hint left on stdout would corrupt a JSON
payload exactly as the error line did.

Usage text printed when a command is invoked with no arguments stays on stdout
and exits `0` — that is help, not an error.

Exit codes are unchanged: `1` on failure, `0` on success.

## Consequences

### Positive

- `applyr <cmd> --json` now emits either a valid JSON document on stdout or
  nothing, with the reason on stderr. Agents can parse one and read the other.
- Shell redirection behaves as expected: `applyr list --json > out.json` leaves
  a clean file, and `2>/dev/null` silences errors without silencing data.
- Errors and their hints stay together on one stream instead of being split.
- Standard Unix behavior, so it needs no explanation to anyone who has used a
  CLI before.

### Negative

- **Breaking for anyone capturing stdout to see errors.** A script doing
  `output=$(applyr add ... 2>&1)` keeps working; one doing
  `output=$(applyr add ...)` and grepping for `Error:` no longer sees it.
- Error text no longer appears in a piped log that captures only stdout.

### Neutral

- Interactive use is unchanged — the terminal interleaves both streams.
- Not a full structured-error contract. A `--json` failure still produces plain
  text on stderr, not a JSON error object. That would be a further change and
  is not decided here.

## Alternatives considered

**Route errors to stderr only when `--json` is passed.** Rejected. It fixes the
agent case while leaving behavior inconsistent between two invocations of the
same command, and any future output mode would need the same special-casing.
Harder to document than the general rule.

**Emit a JSON error object on stdout when `--json` is set.** Rejected for now.
It is arguably the better long-term answer for agents, but it is a bigger
contract — every error site would need a stable machine-readable `code`. Doing
stderr first is a prerequisite either way and does not block it later.

**Leave it and document it.** Rejected. That was the state after
[PR #22](https://github.com/DeibyGS/applyr/pull/22), and it puts the burden on
every agent to work around a defect applyr can fix once.

## Notes

The bug was found while writing `docs/contracts.md`: the invariant "`--json`
output goes to stdout with nothing else mixed in" was written from assumption,
then contradicted by `grep -rn stderr applyr/`, which returned nothing outside
of Chrome subprocess handling. The invariant was aspirational; this ADR makes
it true.

Related: [ADR 003](003-no-llm-calls.md), [`../contracts.md`](../contracts.md).
