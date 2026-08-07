# ADR 007 — Structured JSON errors on stderr

**Status:** Accepted
**Date:** 2026-08-07
**Extends:** [ADR 006](006-errors-to-stderr.md)

## Context

[ADR 006](006-errors-to-stderr.md) moved all error output to stderr, so a
failing `--json` command no longer corrupts stdout. It explicitly left one
thing undecided:

> Not a full structured-error contract. A `--json` failure still produces plain
> text on stderr, not a JSON error object.

That leaves an agent able to detect *that* a command failed — non-zero exit,
empty stdout — but forced to regex plain English to learn *why*. The
distinction matters: "offer not found" should make an agent list offers and
retry, while "invalid status" should make it correct a value. Both currently
look like an opaque string that changes whenever the wording is edited.

Error wording is not a contract. Error *codes* can be.

## Decision

When a command runs with `--json`, errors are emitted on **stderr** as a single
JSON object:

```json
{
  "error": {
    "code": "not_found",
    "message": "offer #42 not found.",
    "details": {"offer_id": 42}
  }
}
```

Without `--json`, the output is unchanged human-readable text.

`code` is a stable snake_case identifier and part of the public contract.
`message` is human-readable and may be reworded at any time. `details` is
optional and additive.

stdout still carries data only, preserving ADR 006's invariant intact. The
agent contract is: check the exit code; on failure, parse stderr.

Mode is set once in `cli.py` via `errors.set_json_mode()`, mirroring how
`colors.init_colors()` already works. This is deliberate global state in the
presentation layer — the alternative is threading an `as_json` flag through
every `die()` call site in the codebase, which is noise at 38 call sites and
easy to forget at the 39th.

## Consequences

### Positive

- Agents branch on a stable `code` instead of matching English prose.
- Error messages become freely rewordable without breaking consumers.
- `details` carries the offending value, so an agent can correct it without
  re-parsing the message.
- Fully backward compatible: without `--json` nothing changes, and `--json`
  previously produced no useful stderr contract to break.

### Negative

- **Error codes are now a contract.** Renaming or removing one is breaking, and
  they belong in `contracts.md` alongside the enums.
- Global mode state in `errors.py`, which sits against the project's "no global
  state" convention. Accepted for the same reason `colors.py` already does it:
  output formatting is a process-wide property, not a per-call one.
- Two output paths for every error, so a malformed `details` payload could
  raise during error handling. Values are restricted to JSON-serializable
  primitives to avoid it.

### Neutral

- Not every call site carries a specific code. Un-annotated errors emit
  `"code": "error"`, which is honest rather than falsely precise, and can be
  refined incrementally without a breaking change.

## Alternatives considered

**JSON errors on stdout.** Rejected. It would let an agent parse a single
stream unconditionally, but it contradicts ADR 006 two days after publishing
it, and would mean stdout sometimes carries data and sometimes carries an
error — exactly the ambiguity ADR 006 removed. An agent that must check the
exit code anyway gains nothing.

**Threading `as_json` into every error call.** Rejected as noise. It would be
explicit rather than global, but it touches 38 call sites, and the 39th written
later would silently emit text in JSON mode.

**Exit codes per error class.** Rejected as insufficient rather than wrong.
POSIX gives a small integer space, the mapping would need documenting anyway,
and it carries no room for `details`. Nothing here prevents adding it later.

## Notes

Both this and ADR 006 came out of one bug: the invariant "`--json` output goes
to stdout with nothing else mixed in" was written into `contracts.md` from
assumption, then found false. ADR 006 made it true for stdout; this one makes
the failure path useful rather than merely harmless.

Related: [ADR 003](003-no-llm-calls.md), [ADR 006](006-errors-to-stderr.md),
[`../contracts.md`](../contracts.md).
