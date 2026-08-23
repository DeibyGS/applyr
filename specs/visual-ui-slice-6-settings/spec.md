## Spec: Visual UI — Settings page (Slice 6, read-only)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`docs/visual-ui/AGENTS.md`): engine never changes — reuse
  `applyr/config.py`/`applyr/commands/workflow.py` logic, never reimplement it. No
  WebSocket, no new backend infra. `api/` is the only fetch boundary on the frontend.
  Feature-based structure (`features/<domain>/`). PR base = `feat/cc-visual-ui`.
- Relevant ADRs: ADR-011 (Visual UI as optional additive interface) — no new
  constraints. `GET /api/config`'s existing docstring establishes the project's
  privacy precedent this spec follows: "never the full config file, which can hold
  local filesystem details... with no reason to leave the machine, even over
  loopback."
- Engram: no prior decisions found for "settings page ajustes visual ui weights".
- Corrected assumptions from Step 2: all 7 assumptions presented to the user were
  confirmed as-is (user replied "sigue" — proceed).
- Pre-spec question answers (binding for this spec):
  1. Scope = thresholds + scoring weights (not the full non-sensitive config —
     narrower, more focused option chosen over the broadest one offered).
  2. CV Master status = shown as a status badge only (OK/WARNING), reusing
     `doctor`'s existing `_check_cv_master()` check — never the CV content itself
     (personal data) and never the filesystem path (existing privacy precedent).

### What does it do? (observable behavior, not implementation)
Replaces the `ComingSoon` stub at `/settings` with a real, read-only page showing
the user's current scoring configuration: the `threshold_apply`/`threshold_maybe`
cutoffs, the per-topic scoring weights from `applyr.toml`, and a CV Master health
badge (same OK/WARNING signal `applyr doctor` already reports, no content or file
path exposed). No editing, no form submission — this slice is display-only, matching
the previously agreed sequencing (editable settings need their own concurrency/
validation spec later).

### Acceptance criteria

- `[MUST]` Given a user navigates to `/settings`, When the page loads, Then it
  fetches `GET /api/settings` once (on mount, no polling — matches the Analytics
  slice's precedent: config values don't change on a 2-3s timescale) and renders
  the current thresholds, weights, and CV Master status.
- `[MUST]` The system shall expose `GET /api/settings` in `applyr/ui/api.py`,
  returning: `threshold_apply`, `threshold_maybe` (ints), `weights` (the raw
  integer per-topic weights from `applyr.toml`'s `[weights]` section —
  `config["weights_raw"]`, NOT the normalized decimals `calculate_score` uses
  internally), `cv_master_status` (`"ok"` or `"warning"`), `cv_master_message` (a
  short sanitized string — content-word count or missing-fields reason, NEVER the
  filesystem path).
- `[MUST]` `GET /api/settings` shall reuse `applyr/commands/workflow.py`'s existing
  `_check_cv_master()` for the CV Master check (never reimplement the "is the
  profile still the blank template" logic) — the API strips the filesystem path out
  of the returned message before responding, since `_check_cv_master()`'s raw
  message includes the local `cv-master.md` path.
- `[MUST]` `GET /api/settings` shall NOT expose `chrome_path`, `output_dir`, `db_path`,
  or any other filesystem path — same boundary `GET /api/config` already draws, this
  endpoint extends that precedent rather than relaxing it.
- `[MUST]` `GET /api/settings` shall NOT query the `offers` table — this endpoint is
  a pure config-file + cv-master-file read, no DB connection needed.
- `[MUST]` Given the frontend receives the weights payload, Then it displays all 6
  topics using the existing `TOPIC_LABELS` display names (`Tech Stack`, `Education`,
  `English`, `Experience`, `Own Projects`, `Cultural Fit`) — labels are duplicated as
  a small frontend constant (backend returns raw topic keys, matching how
  `funnel`/`channels` already return raw keys in the Analytics slice), not fetched
  from a new endpoint.
- `[MUST]` Given `cv_master_status === "warning"`, Then the page shows a visibly
  distinct (non-default) badge state — same "don't bury a health warning" principle
  `doctor`'s own CLI output already follows.
- `[MUST]` The system shall NOT add any new npm dependency — the page is built from
  existing `Card`/`Badge` primitives in `components/ui/`, no charts needed (this is
  config display, not analytics).
- `[MUST]` The system shall NOT add a POST/PATCH endpoint or any write capability in
  this slice — read-only by design, matches the earlier agreed sequencing.
- `[SHOULD]` Pure response-shaping logic (if any beyond a direct pass-through) shall
  be unit-tested; if the endpoint ends up being a thin direct pass-through with no
  branching logic worth isolating, backend tests cover it directly instead (no
  forced frontend pure-function extraction for its own sake).
- `[WONT]` No settings editing / form / save button — future slice, needs its own
  concurrency-and-validation spec (two browser tabs or a CLI edit racing a save).
- `[WONT]` No exposure of `cv-master.md` content, `chrome_path`, `output_dir`,
  `db_path`, or any other filesystem detail.
- `[WONT]` No re-exposure of the other `doctor` checks (Database, Agent
  Instructions, Chrome, CV Output Privacy) — out of scope for this pass.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/api.py` | MODIFY | Add `GET /api/settings` route, reusing `_check_cv_master()` and `load_config()` |
| `applyr/ui/frontend/src/api/settings.ts` | CREATE | Typed fetch function for `/api/settings` (the only HTTP boundary for this feature) |
| `applyr/ui/frontend/src/features/settings/TOPIC_LABELS.ts` | CREATE | Frontend display-label constant mirroring `applyr/config.py`'s `TOPIC_LABELS` |
| `applyr/ui/frontend/src/features/settings/ThresholdsCard.tsx` | CREATE | Displays `threshold_apply`/`threshold_maybe` |
| `applyr/ui/frontend/src/features/settings/WeightsCard.tsx` | CREATE | Displays the 6 per-topic weights with labels |
| `applyr/ui/frontend/src/features/settings/CvMasterStatusBadge.tsx` | CREATE | OK/WARNING badge from `cv_master_status`/`cv_master_message` |
| `applyr/ui/frontend/src/pages/SettingsPage.tsx` | MODIFY | Replace `ComingSoon` stub with real page composing the above |
| `tests/test_ui_api.py` | MODIFY | Backend tests for `GET /api/settings` (happy path, warning CV master, no filesystem paths in response) |
| `specs/visual-ui-slice-6-settings/spec.md` | MODIFY | Traceability matrix + status update once implemented |
| `docs/visual-ui/AGENTS.md` | MODIFY | Append Slice 6 entry to the Status section |

### Dependencies
- APIs / endpoints used: new `GET /api/settings`. No existing endpoints modified.
- DB tables: none — config-file + cv-master-file read only, no `get_conn()` call in
  the new route.
- Reused logic: `applyr.config.load_config()` (for `weights_raw`, `threshold_apply`,
  `threshold_maybe`), `applyr.commands.workflow._check_cv_master()` (for the CV
  Master status/message, path stripped before returning).
- Reused components: `Card`/`CardHeader`/`CardTitle`/`CardContent`, `Badge` from
  `components/ui/`.
- No new npm dependency.

### Explicit assumptions
- We assume raw integer weights (`weights_raw`), not normalized decimals → matches
  what a user actually typed in `applyr.toml`'s `[weights]` section; the normalized
  decimals are an internal scoring-time detail with no obvious meaning to a human
  reading a settings page (e.g. "0.3" vs "30" — the raw integers are what the user
  wrote and would recognize).
- We assume `cv_master_message` needs light backend sanitization (strip the
  filesystem path segment) rather than a wholesale rewrite of `_check_cv_master()`'s
  message format → keeps `doctor`'s CLI message format untouched (no risk of
  drifting the two apart) while still respecting the API's existing path-privacy
  boundary.
- We assume weight topic labels are safe to duplicate as a small frontend constant
  (6 short strings) rather than added to the API response → avoids growing
  `GET /api/settings`'s contract for values that are effectively static English
  labels, consistent with how `FUNNEL_STAGE_LABELS` already works client-side in
  the Analytics slice.

### Non-functional requirements
- Performance: single config-file read, no DB — trivially fast, no perceptible
  latency concern.
- Security/Privacy: no filesystem path of any kind may appear anywhere in the
  `GET /api/settings` response body — covered by a `[MUST]` AC above and a backend
  test asserting no local path substring appears in the response text (same test
  pattern `test_ui_api.py::TestConfig::test_never_exposes_the_full_config_file`
  already uses for `/api/config`).
- Accessibility: WCAG AA already established for the palette; the WARNING badge
  state must not rely on color alone (icon or text label required), consistent with
  the dataviz skill's "status colors never carry meaning alone" rule even though
  this page has no charts.

### Edge cases / risks
- `cv-master.md` missing entirely (never ran `applyr init`) vs. present-but-still-
  the-blank-template — `_check_cv_master()` already distinguishes these
  (`NOT FOUND` vs `WARNING — {reason}`); the API surfaces both as `cv_master_status:
  "warning"` with the specific `cv_master_message` text carried through (still path-
  stripped).
- Zero or negative weights in `applyr.toml` (already a `doctor` "issue" case via
  `_check_weights()`, not reused in this slice per the out-of-scope list) — the
  Settings page just displays whatever raw integers `load_config()` returns,
  including zero/negative; no validation or warning styling for this case in this
  slice (that's `doctor`'s job, not this page's, per the explicit `[WONT]` on
  re-exposing other `doctor` checks).

### Task breakdown (execution order)
1. [x] `GET /api/settings` in `applyr/ui/api.py` + backend tests (happy path, warning
   CV master, path-privacy assertion) [S]
2. [x] `src/api/settings.ts` typed fetch function [S]
3. [x] `topic-labels.ts`, `ThresholdsCard.tsx`, `WeightsCard.tsx`,
   `CvMasterStatusBadge.tsx` — independently small components [M]
4. [x] `SettingsPage.tsx` — wire fetch-on-mount + compose the above [S]
5. [x] Manual verification against real data + traceability matrix + `docs/visual-ui/
   AGENTS.md` Status update [S]

Task sizes: S (<1h) | M (1-3h)

### Out of scope
- `[WONT]` Editing/saving settings (future slice, needs concurrency/validation spec).
- `[WONT]` CV master content exposure.
- `[WONT]` Any filesystem path in the API response.
- `[WONT]` Database/Chrome/Agent-Instructions/CV-Privacy checks from `doctor`.

## Traceability Matrix

| AC | Priority | Description | Verification | Status |
|----|----------|--------------|---------------|--------|
| AC-01 | MUST | Fetch settings once on mount, no polling | `SettingsPage.tsx` `useEffect(..., [])` — empty deps array | PASS |
| AC-02 | MUST | `GET /api/settings` returns thresholds, raw weights, cv_master_status/message | `test_ui_api.py::TestSettingsEndpoint::test_returns_thresholds_and_raw_weights` | PASS |
| AC-03 | MUST | Reuses `_check_cv_master()`, never reimplements the check | `applyr/ui/api.py::get_settings()` imports and calls `_check_cv_master()` directly | PASS |
| AC-04 | MUST | No `chrome_path`/`output_dir`/`db_path`/any filesystem path exposed | `test_never_exposes_a_filesystem_path`, `test_never_exposes_the_full_config_file` | PASS |
| AC-05 | MUST | No `offers` table query | Code review: `get_settings()` has no `get_conn()` call | PASS |
| AC-06 | MUST | Frontend displays all 6 topics with `TOPIC_LABELS` names | `WeightsCard.tsx` + `topic-labels.ts`; manual curl confirms all 6 topics present | PASS |
| AC-07 | MUST | Warning status visibly distinct (icon + text, not color alone) | `CvMasterStatusBadge.tsx` — `CheckCircle2`/`AlertTriangle` icon + "OK"/"Warning" text alongside color | PASS |
| AC-08 | MUST | No new npm dependency | `git diff --stat` — no `package.json` change in this slice | PASS |
| AC-09 | MUST | No POST/PATCH/write capability | Code review: only `@router.get("/api/settings")`, no mutation | PASS |
| AC-10 | SHOULD | Pure logic unit-tested, or direct backend test if no branching worth isolating | Message-sanitization branching in `get_settings()` covered by 5 backend tests (no separate frontend pure-function extraction needed — display components have no branching logic) | PASS |

Full suite: 776/776 Python tests passing (5 new: `TestSettingsEndpoint`), 25/25 Vitest
passing (no new frontend tests needed per AC-10's conditional), `tsc --noEmit` clean.
Manually verified `GET /api/settings` via curl against the user's real config: custom
thresholds (65/55), default weights, `cv_master_status: "ok"` with
`"OK (2057 words of content)"` — no filesystem path in the response. Frontend `/settings`
route confirmed reachable (200) via local dev server. Could NOT visually verify the
rendered page in a browser — no browser-driving/screenshot tool available in this
session; disclosed explicitly rather than assumed. `/simplify-lean` ran twice (backend
`api.py` + `test_ui_api.py`; the 6 new frontend files) — both passes returned "no
changes needed". `/code-review` found 2 minor issues, both fixed: a missing test for
the NOT FOUND path-stripping branch specifically (the existing privacy test only
exercised the "ok" branch) — added
`test_never_exposes_a_filesystem_path_when_cv_master_is_missing`; and `get_settings()`
parsing `applyr.toml` 3 times per request — reduced to 2 by deriving the CV master
path from the already-loaded `config` instead of a redundant second
`get_cv_master_path()` call. 777/777 Python tests passing after fixes.
