# Spec: PyPI Update Check (opt-in)

### Status: APPROVED
### Version: 1.0
### Target release: TBD (minor — additive, non-breaking)

---

## Recovered context

- **constitution.md**: `[general]` config keys follow the `threshold_apply`/`threshold_maybe`
  pattern (default in `constants.py`, read via `load_config()`, documented inline in
  `TOML_TEMPLATE`). No global state — config loaded per-call. Constants belong in
  `constants.py`, no magic numbers in business logic. `--json` keys are never renamed or
  removed. PR budget 500 lines (this repo caps some specs at 400 — see `scoring-confidence`
  spec — but no override found for this feature; default 500 applies).
- **ADR 001 (Local-first storage)**: states "No account, no server, no sync, no telemetry,
  no network call of any kind" — written to protect sensitive job-search data (an employer
  discovering an employee is interviewing) and to guarantee offline operation ("works
  offline, including on a plane"). **Direct conflict**: this feature requires an outbound
  HTTP call to `pypi.org`. Resolved in this session: the call carries no user data (a plain
  GET to a public JSON endpoint, equivalent to visiting the PyPI package page), and is
  **opt-in, default off** — offline-by-default is preserved for every user who does not
  explicitly enable it. This requires a new **ADR-010** superseding ADR-001 with a narrow,
  documented exception. ADR-010 is part of this spec's task breakdown (Task 6).
- **ADR 003 (No LLM calls)**: not touched — this feature calls PyPI's REST API, not an LLM.
- **constitution.md banned patterns**: "Never add LLM API calls" — not violated (PyPI JSON
  API is not an LLM). No banned pattern covers non-LLM network calls, because until now none
  existed anywhere in the codebase (verified: `grep` for `urllib`/`requests`/`http` across
  `applyr/*.py` found no existing network call site).
- **Engram**: no prior decisions found for "applyr update check" or "applyr pypi version".
- **Prior session finding** (this conversation): `applyr` has zero existing mechanism to
  learn about newer releases. The only existing version-comparison code is
  `agent_instructions.py`'s `_as_tuple()`/`is_stale()`, which compares the local
  `AGENT_INSTRUCTIONS.md` stamp against the *installed* `__version__` — an entirely
  different comparison (local file vs. installed package, not installed vs. published).
- **Corrected assumptions from Step 2 of this conversation**: default is **OFF**, not ON as
  first proposed — changed after the ADR-001 conflict was surfaced and the user chose the
  opt-in resolution over opt-out.

## What does it do? (observable behavior)

Today, a user who installed `applyr` via `pip install applyr` has no way to learn a new
version was published short of manually running `pip list --outdated` or checking PyPI/GitHub.

This feature adds an **opt-in** check: when `check_updates = true` is set in
`~/.applyr/applyr.toml`'s `[general]` section, running `applyr doctor` queries PyPI's public
JSON API for the latest published version, compares it against the installed `__version__`,
and — if newer — prints one extra line in the health-check report with the new version and
the upgrade command. The check is cached for 24h on disk so repeated `doctor` runs don't hit
the network every time. Any failure (no connection, timeout, malformed response, PyPI down)
is completely silent: the rest of `doctor`'s report and its exit code are unaffected.

Default is `false` — a fresh `applyr init` never makes a network call unless the user opts in.

## Acceptance criteria

### Config

- [MUST] The system shall add `check_updates = false` to `[general]` in `TOML_TEMPLATE`
  (`config.py`), with an inline comment explaining what it does and that it is off by
  default because `applyr` is local-first (ADR-001/ADR-010).
- [MUST] The system shall add `DEFAULT_CHECK_UPDATES = False` to `constants.py`, following
  the placement/naming convention of `DEFAULT_THRESHOLD_APPLY` etc.
- [MUST] WHEN a user's `applyr.toml` predates this feature (no `check_updates` key), THE
  system SHALL treat it as `false` — `load_config()` merges the constant default the same
  way it already does for every other `[general]` key.
- [WONT] No CLI flag to override the config value for this iteration (e.g. no
  `--check-updates`). The config file is the only control surface.

### Network call & caching

- [MUST] WHEN `check_updates` is `true` AND `applyr doctor` runs, THE system SHALL check
  for a cached result at `~/.applyr/update_check.json` before making any network call.
- [MUST] WHEN the cache file is absent, unreadable, or older than 24h, THE system SHALL
  issue one `GET` request to `https://pypi.org/pypi/applyr/json` via `urllib.request`
  (stdlib only — no new dependency) with a short timeout (`socket` default via
  `urllib.request.urlopen(..., timeout=3)`), and SHALL write the result (or the failure
  state, see below) back to the cache file with a fresh timestamp.
- [MUST] WHEN the cache file is present and younger than 24h, THE system SHALL read the
  cached `latest_version` and SHALL NOT make a network call.
- [MUST] The cache file shall store `{"latest_version": "<str>", "checked_at": "<ISO8601>"}`.
- [SHOULD] A failed check (network error, timeout, non-200, malformed JSON) shall still
  update `checked_at` in the cache (with `latest_version` unchanged or absent) so a
  persistently unreachable PyPI does not retry on every single `doctor` call within the
  same 24h window.

### Failure behavior (silent by design)

- [MUST] WHEN the network request raises `URLError`, `TimeoutError`, or the response body
  is not valid JSON, THE system SHALL catch the exception, skip the update-check section of
  the report entirely, and SHALL NOT call `die()`, `warn()`, or add an `issue`/`note` entry
  — `doctor`'s exit code and existing checks are completely unaffected.
- [MUST] The system shall never raise an uncaught exception out of the update-check code
  path — it is wrapped so a bug in this feature cannot break `doctor` itself.
- [WONT] No retry/backoff logic beyond the 24h cache TTL. A single attempt per cache window.

### Reporting

- [MUST] WHEN `check_updates` is `true` AND a newer version is found (installed version
  tuple < latest version tuple, compared via the same integer-tuple parsing pattern as
  `agent_instructions.py::_as_tuple`), THE system SHALL print one additional line in
  `doctor`'s human-readable report: `Update : vX.Y.Z available (pip install --upgrade applyr)`,
  placed after the existing checks and before the summary line.
- [MUST] WHEN `check_updates` is `false` (the default), THE system SHALL make no network
  call and SHALL NOT print any update-related line — behavior is byte-identical to `doctor`
  before this feature existed.
- [MUST] WHEN `check_updates` is `true` and no newer version is found (or the check failed
  silently), THE system SHALL NOT print any update-related line — the feature is additive
  only when there is something to report.
- [MUST] In `--json` mode, WHEN `check_updates` is `true` and a newer version is found, THE
  system SHALL add an optional top-level key `"update_available": "<latest_version>"` to the
  existing JSON object — no existing key is renamed or removed (constitution.md rule).
- [MUST] In `--json` mode, WHEN there is nothing to report (disabled, no newer version, or
  silent failure), THE system SHALL NOT include the `update_available` key at all (not
  `null`) — consistent with `confidence` being `NULL`-only-when-omitted in
  `scoring-confidence`'s precedent, and keeps `--json` output stable for agents that don't
  know the key.
- [MUST] The update-check line/key shall never affect `doctor`'s exit code — only the
  existing `issues` list (unrelated to this feature) determines `sys.exit(1)`.

### ADR

- [MUST] A new ADR (`docs/adr/010-<slug>.md`) shall be written, superseding ADR-001 with a
  narrow, explicit exception: an opt-in, default-off, non-telemetry version check against a
  public endpoint. It shall document why (user asked "how do users learn about updates",
  ADR-001's "no network call" promise was found to conflict), the alternatives considered
  (opt-in default-off — chosen; opt-out default-on — rejected because it breaks
  offline-by-default for all users, not just those who want the feature; do-nothing —
  rejected because it does not solve the user's problem), and the consequences (positive:
  users who want it can learn about updates; negative: the tool's "zero network calls, ever"
  claim in README/docs, if any, must be corrected to "zero network calls unless explicitly
  opted in").

## Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/constants.py` | MODIFY | Add `DEFAULT_CHECK_UPDATES = False` and `PYPI_UPDATE_CHECK_URL`, `UPDATE_CHECK_CACHE_TTL_HOURS` constants |
| `applyr/config.py` | MODIFY | Add `check_updates` to `TOML_TEMPLATE` and to the `[general]` defaults merged in `load_config()` |
| `applyr/update_check.py` | CREATE | New module: cache read/write, network call, version comparison — isolated so `doctor` stays readable and the network code is unit-testable in isolation (mockable `urlopen`) |
| `applyr/commands/workflow.py` | MODIFY | `cmd_doctor()`: call `update_check.check_for_update(config)` after existing `checks`, append to human report and to the `--json` dict when applicable |
| `docs/adr/010-<slug>.md` | CREATE | Supersede ADR-001 with the opt-in exception (see ADR AC above) |
| `docs/adr/001-local-first.md` | MODIFY | Add a note pointing to ADR-010 as the superseding decision (ADRs are immutable in content but a "superseded by" pointer is standard per this repo's own `docs/adr/README.md` convention — verify convention before editing) |
| `tests/test_update_check.py` | CREATE | Unit tests for `update_check.py`: cache hit/miss, TTL expiry, network failure (mocked), version comparison, disabled-by-default |
| `tests/commands/test_doctor.py` or equivalent | MODIFY | Integration test: `doctor` output unchanged when `check_updates=false` (default); shows update line when enabled + mocked newer version available |
| `applyr.toml` docs / README (if it documents "no network calls") | MODIFY | Correct any blanket "fully offline" claim to reflect the new opt-in exception |

## Dependencies

- **External API**: `https://pypi.org/pypi/applyr/json` (PyPI's public JSON API, no auth,
  no rate-limit concerns at this call volume — one request per user per 24h at most).
- **DB tables**: none — this feature does not touch SQLite at all.
- **Stdlib only**: `urllib.request`, `json`, `pathlib`, `datetime` — no new dependency,
  consistent with the project's stdlib-only philosophy.
- **Reused code**: version-tuple comparison follows the exact pattern of
  `agent_instructions.py::_as_tuple` (do not import it directly — that module is for the
  AGENT_INSTRUCTIONS stamp, a different concern; duplicate the small parsing function in
  `update_check.py` to keep the two concerns decoupled, per constitution's "no global state"
  spirit — confirm this call during implementation rather than importing across concerns).

## Explicit assumptions

- We assume PyPI's JSON API response shape includes `info.version` for the latest version →
  if PyPI changes this shape, the parse fails, which is caught by the "malformed JSON" /
  `KeyError` silent-failure path (AC above), not a crash.
- We assume a 3-second timeout is enough to avoid `doctor` feeling "hung" on a slow/absent
  connection → if this proves too aggressive in practice (false negatives on slow networks),
  it is a config-free constant (`UPDATE_CHECK_CACHE_TTL_HOURS`'s sibling in `constants.py`)
  that can be tuned without a spec change.
- We assume the user runs `doctor` at least occasionally after opting in → if they never run
  `doctor` again, they never see the notice; this is accepted as consistent with "opt-in
  surfaces only in `doctor`" (Step 1 answer), not a bug.

## Non-functional requirements

- **Performance**: when disabled (default), zero added latency to `doctor` — no network
  code path is even entered. When enabled and cache is warm (<24h), zero added latency
  (local file read only). When enabled and cache is cold, adds at most ~3s (timeout ceiling)
  to `doctor`'s runtime, only once per 24h.
- **Privacy**: the GET request sends no user-identifying data beyond what any HTTP request
  inherently carries (IP, User-Agent) — no telemetry payload, no offer data, no CV data, no
  analytics. This is the crux of the ADR-010 exception and must not scope-creep into
  anything richer later without its own spec.
- **Security**: uses HTTPS only (`https://pypi.org/...`); no arbitrary URL is ever
  constructed from user input.

## Edge cases / risks

- **User enables `check_updates` then goes fully offline for weeks** → every `doctor` run
  attempts (and silently fails) the network call once per 24h window; no user-visible
  degradation beyond the (already-accepted) timeout ceiling on the first call of each window.
- **PyPI returns a pre-release or yanked version as "latest"** → out of scope for this
  iteration; the JSON API's `info.version` already reflects PyPI's own notion of "current
  release" and this feature trusts it as-is. `[WONT]` handle pre-release filtering.
- **User downgrades applyr on purpose** (e.g. testing an old version) → `is_stale`-style
  logic in `agent_instructions.py` explicitly avoids warning about "the future"; this
  feature's comparison (`installed < latest`) naturally has the same property — a downgrade
  still correctly shows "update available" pointing at the version the user left, which is
  correct behavior here (unlike the AGENT_INSTRUCTIONS case, there is no "warning about the
  future" risk since PyPI's "latest" is never behind the installed version in a normal flow).
- **Corporate/CI environment with no outbound internet and `check_updates` accidentally
  left on** → fully covered by the silent-failure AC; `doctor` must keep working as a CI
  gate (`python-package.yml` calls it) regardless.

## Task breakdown (execution order)

1. Add `DEFAULT_CHECK_UPDATES`, `PYPI_UPDATE_CHECK_URL`, `UPDATE_CHECK_CACHE_TTL_HOURS` to
   `constants.py`; add `check_updates` to `config.py` (`TOML_TEMPLATE` + defaults merge) [S]
2. Create `applyr/update_check.py`: cache read/write, `urlopen` call with timeout, version
   tuple comparison, all wrapped so no exception escapes; pure functions where possible for
   testability [M]
3. Write `tests/test_update_check.py`: mock `urlopen`, cover cache-hit/miss/TTL-expired,
   network failure, malformed JSON, disabled-by-default, newer-version-found,
   no-newer-version [M]
4. Wire into `cmd_doctor()` in `workflow.py`: human report line + `--json` key, verify
   `check_updates=false` path is byte-identical to current output (regression test) [S]
5. Update/add `tests/commands/test_doctor.py` coverage for the two states above [S]
6. Write `docs/adr/010-<slug>.md` superseding ADR-001; add "superseded by" pointer to
   ADR-001 per repo convention (check `docs/adr/README.md` for how prior supersessions were
   recorded, if any exist) [S]
7. Update README / any "fully offline" claim to reflect the opt-in exception [S]
8. Run `/simplify-lean` (new module + ≥30 lines changed) [S]
9. Traceability matrix + drift check (SDD Step 6) before PR [S]

## Out of scope

- `[WONT]` No automatic check outside `applyr doctor` (e.g. no check on every command).
- `[WONT]` No CLI flag to force/skip the check per-invocation.
- `[WONT]` No self-update (`applyr` never runs `pip install` on the user's behalf) — this
  only informs, never acts.
- `[WONT]` No pre-release/yanked-version filtering.
- `[WONT]` No retry/backoff beyond the 24h cache window.
- `[WONT]` No telemetry of any kind — this feature must never grow into "phone home" beyond
  the single "what's the latest version" query.
