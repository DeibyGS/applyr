# Spec: Visual UI — Slice 1 (backend skeleton + intake + polling read API)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **Project constitution:**
  - ADR-002 (SQLite) — one `jobs.db`, accessed only through `applyr/db.py`. This slice
    reuses that file and that module; no second database.
  - ADR-003 (No LLM calls) — applyr never calls an LLM API. This slice's backend does
    not either: it only persists what the human/agent already decided.
  - ADR-005 (Single CLI, stdlib-only) — the base `applyr` CLI stays exactly as-is,
    zero new required dependencies. This slice adds a **second, optional** interface
    (`pip install applyr[ui]`) rather than replacing or bending the CLI. Documented as
    a new ADR (ADR-011, part of this slice) rather than treated as silently exempt.
  - `docs/visual-ui/AGENTS.md` — invariants for the whole Visual UI feature: engine
    unchanged, AI coding agent remains the sole reasoner (no `LLMProvider`), no
    Postgres/Redis/Celery/auth/Docker, polling not WebSocket for v1, stack = FastAPI +
    existing SQLite + React/TS/Vite, packaged as `applyr[ui]`.
- **Relevant ADRs:** 002, 003, 005 (above). No prior ADR conflicts with this slice.
- **Engram:** no prior decisions found for this feature (first session).
- **Corrected assumptions from Step 2 (user-confirmed 2026-08-23):**
  1. No auth; `applyr ui` binds `127.0.0.1` only.
  2. `applyr add` gets a new optional `--intake-id <id>` flag. When present, in the
     same transaction as the existing add logic, it flips the matching `ui_intake` row
     to `status='promoted'` and stores the resulting `offer_id`. Backward compatible —
     omitting the flag changes nothing about today's `add` behavior.
  3. `ui_intake` lives in the same `jobs.db`, added via the existing
     `schema_version`-driven migration mechanism in `db.py`.
  4. API errors are JSON: `{"error": true, "code": "...", "message": "..."}` with an
     appropriate HTTP status (400/404/422/500).
  5. No pagination on `GET /api/jobs` in this slice.
  6. FastAPI/uvicorn are imported lazily, only inside the `ui` command path — importing
     `applyr.cli` without `[ui]` installed must not fail.
  7. New package at `applyr/ui/` (not a top-level `web/`), so
     `[tool.setuptools.packages.find] include = ["applyr*"]` picks it up unchanged.
  8. `applyr ui` is wired into the existing flat `elif` dispatch in `cli.py`.
  9. CORS restricted to localhost origins (Vite dev server port).
  10. No edit/delete of intake rows from the UI in this slice.
  11. ADR-011 created, documenting this as an additive exception to ADR-005, not a
      reversal of it.

### What does it do? (observable behavior, not implementation)

- A user can start a local API server with `applyr ui`, which prints the URL it is
  listening on and does not touch any existing CLI behavior.
- A user (via a minimal React scaffold, run separately with `npm run dev` in this
  slice) can paste raw job-offer text into a form and submit it; it is saved and shows
  up in a "pending intake" list.
- Separately, in a terminal, the user tells their AI coding agent (Claude Code /
  OpenCode / Cursor) to process pending offers. The agent reads the pending intake
  text the same way it reads any pasted offer today, scores it, and runs
  `applyr add '<json>' --intake-id <id>` — exactly today's `add` workflow, plus one
  flag.
- Once that command succeeds, the corresponding intake row is marked `promoted` and
  linked to the new offer. The next time the frontend polls, the offer appears in the
  job list with its real score and full topic breakdown — never a simulated or
  guessed value.
- Existing `applyr add` usage without `--intake-id` (i.e. every current user and every
  existing test) behaves identically to today.

### Acceptance criteria

#### Data model
- `[MUST]` The system shall create a table `ui_intake` (`id`, `raw_text` NOT NULL
  non-empty, `source_note` nullable, `status` default `pending`, `offer_id` nullable FK
  to `offers(id)` ON DELETE SET NULL, `created_at`, `promoted_at` nullable) via the
  existing `schema_version` migration mechanism.
- `[MUST]` WHEN the database is opened at a schema version below this slice's version
  THE system SHALL apply the `ui_intake` migration exactly once and record the new
  schema version — matching the existing migration pattern in `db.py`.
- `[MUST]` Given an existing `jobs.db` at the current schema version with real offers
  in it, When `applyr` (any command) runs after upgrade, Then all existing offers,
  topics, and gaps are unchanged and readable.

#### Intake API
- `[MUST]` WHEN `POST /api/intake` is called with a non-empty `raw_text` THE system
  SHALL create a `ui_intake` row with `status='pending'` and return its id and
  `created_at`.
- `[MUST]` IF `raw_text` is missing or empty/whitespace-only THEN the system SHALL
  respond `422` with the standard JSON error shape, and SHALL NOT create a row.
- `[MUST]` WHEN `GET /api/intake` is called THE system SHALL return all `ui_intake`
  rows ordered newest-first, and SHALL support an optional `?status=pending|promoted`
  filter.
- `[MUST]` WHEN `GET /api/intake/{id}` is called with an id that does not exist THE
  system SHALL respond `404` with the standard JSON error shape.

#### `add --intake-id` linkage
- `[MUST]` WHEN `applyr add '<json>' --intake-id <id>` succeeds AND `<id>` refers to a
  `ui_intake` row with `status='pending'` THE system SHALL, in the same transaction as
  the offer insert, set that row's `status='promoted'`, `offer_id=<new offer id>`, and
  `promoted_at=now`.
- `[SHOULD]` IF `--intake-id <id>` refers to a `ui_intake` row that does not exist THEN
  the system SHALL fail the whole `add` (no offer created, no partial state) with a
  clear error naming the missing intake id.
- `[SHOULD]` IF `--intake-id <id>` refers to a row already `status='promoted'` THEN the
  system SHALL fail the whole `add` rather than silently re-linking or creating a
  duplicate offer.
- `[MUST]` Given `applyr add '<json>'` is called WITHOUT `--intake-id` (today's usage),
  When it runs, Then behavior is byte-for-byte identical to before this slice —
  existing tests for `cmd_add` must pass unmodified.

#### Jobs read API
- `[MUST]` WHEN `GET /api/jobs` is called THE system SHALL return all `offers` rows
  (core columns: id, title, company, status, compatibility_pct, work_mode, location,
  seniority_level, role_category, created_at, date_applied) with no pagination.
- `[MUST]` WHEN `GET /api/jobs/{id}` is called with a valid id THE system SHALL return
  the full offer row plus its full `offer_topics` breakdown (topic, score, detail,
  confidence for each scored topic).
- `[MUST]` WHEN `GET /api/jobs/{id}` is called with an id that does not exist THE
  system SHALL respond `404` with the standard JSON error shape.
- `[MUST]` The system shall never compute or alter `compatibility_pct` or any topic
  score in the UI backend — these are read-only mirrors of what `applyr add`/`update`
  already wrote via the existing scoring path.

#### `applyr ui` command
- `[MUST]` WHEN `applyr ui` is run without the `[ui]` extra installed THE system SHALL
  print a clear error naming the missing dependency and how to install it
  (`pip install applyr[ui]`), and SHALL exit non-zero — no traceback.
- `[MUST]` WHEN `applyr ui` starts successfully THE system SHALL bind to `127.0.0.1`
  (default port `8000`, overridable with `--port`) and print the URL.
- `[MUST]` Given `applyr.cli` is imported without `[ui]` installed (i.e. every existing
  install), When any other command runs, Then it behaves identically to before this
  slice — importing `applyr.ui` must not happen at module load time.
- `[SHOULD]` The system should respond to `GET /api/health` with `200` once the server
  is up, for smoke-testing `applyr ui` itself.

#### Frontend scaffold
- `[SHOULD]` Given the backend is running, When a user opens the Vite dev server and
  submits the intake form, Then the new row appears in a "pending" list within one
  polling interval (2-3s), without a page reload.
- `[SHOULD]` Given an intake row has been promoted (via the agent's `add --intake-id`),
  When the frontend's next poll runs, Then the corresponding job appears in the job
  list with its real `compatibility_pct` — no placeholder or simulated score at any
  point.
- `[COULD]` A bare job detail view showing the topic breakdown returned by
  `GET /api/jobs/{id}`.
- `[WONT]` Any styling beyond making the round trip legible (no Tailwind/shadcn/Framer
  Motion in this slice — that's the visual-polish slice, later).

#### Out-of-scope guardrails
- `[WONT]` WebSocket, Celery, Redis, Postgres, Docker Compose, auth, multi-tenancy,
  LLMProvider abstraction — per `docs/visual-ui/AGENTS.md`, not revisited here.
- `[WONT]` Editing or deleting `ui_intake` rows from the API/UI.
- `[WONT]` Kanban, filing cabinet, timeline, agent "office" visuals — later slices.

### Affected files

| File | Action | Reason |
|---|---|---|
| `applyr/db.py` | MODIFY | Add `ui_intake` table + migration (schema v10→v11) |
| `applyr/intake.py` | CREATE | CRUD helpers (`create_intake`, `list_intake`, `get_intake`, `mark_intake_promoted`) — mirrors the `duplicates.py` convention (db.py stays schema/migrations-only, this module owns the queries) rather than living inside `db.py` as originally sketched |
| `applyr/commands/core.py` | MODIFY | `cmd_add` accepts optional `intake_id`; on success, calls `mark_intake_promoted` in the same transaction |
| `applyr/cli.py` | MODIFY | Parse `--intake-id` on `add`; add `ui` subcommand dispatch (lazy import of `applyr.ui`) |
| `applyr/ui/__init__.py` | CREATE | Package marker, no FastAPI import at module level |
| `applyr/ui/server.py` | CREATE | FastAPI app factory, uvicorn runner used by `applyr ui`, `/api/health` |
| `applyr/ui/api.py` | CREATE | Routes: `/api/intake` (POST, GET), `/api/intake/{id}` (GET), `/api/jobs` (GET), `/api/jobs/{id}` (GET) |
| `applyr/ui/frontend/*` | CREATE | Vite + React + TS scaffold: intake form, pending list, job list, job detail (unstyled) |
| `pyproject.toml` | MODIFY | Add `[project.optional-dependencies] ui = ["fastapi>=0.110", "uvicorn>=0.29"]` |
| `docs/adr/011-visual-ui-optional-interface.md` | CREATE | ADR: additive exception to ADR-005, scope and boundaries |
| `docs/visual-ui/AGENTS.md` | MODIFY | Update "Status" section once this slice ships |
| `tests/test_ui_intake.py` | CREATE | `ui_intake` CRUD, migration idempotency, `add --intake-id` linkage (happy path + both `[SHOULD]` failure cases) |
| `tests/test_ui_api.py` | CREATE | FastAPI endpoint tests via `httpx`/`TestClient`: intake create/list/get, jobs list/detail, 404s, 422s |

### Dependencies

- New runtime deps (optional extra only): `fastapi`, `uvicorn`.
- New dev/test dep: `httpx` (FastAPI `TestClient` requires it) — add under existing
  `dev` extra or a new `ui-dev` extra; decide at implementation time based on whether
  CI installs `[ui]` for the backend test job.
- DB: `jobs.db`, existing `offers`/`offer_topics` tables (read-only from the UI
  backend) + new `ui_intake` table (read/write).
- No external APIs, no network calls beyond localhost.

### Explicit assumptions

- We assume the existing `add` transaction in `cmd_add`/`db.py` is a single atomic
  unit already (insert offer + insert topics) → if false, the `--intake-id` linkage
  must be added to whatever the actual outermost transaction boundary is, not assumed.
- We assume dozens, not thousands, of `ui_intake`/`offers` rows at any time → if a user
  somehow accumulates thousands, unpaginated `GET /api/jobs` degrades gracefully in
  this slice (it is a personal tool at n=1), but should be revisited before it's ever
  not true.

### Non-functional requirements

- **Performance:** `GET /api/jobs` on a database with 500 offers responds in < 200ms
  on a typical dev laptop (SQLite read, no N+1 — one query, not one-per-row).
- **Security:** server binds `127.0.0.1` only; CORS allow-list restricted to
  `http://localhost:5173` (Vite default) and `http://127.0.0.1:5173`; no secrets, no
  auth token, matches "local single-user tool" threat model documented in the guide.
- **Compatibility:** installing `applyr` without `[ui]` must show zero behavior change
  — verified by running the full existing test suite with `fastapi`/`uvicorn` absent.

### Edge cases / risks

- **Risk:** a migration that runs against a real `jobs.db` with months of user data
  (this is a live tool with real applications tracked) could corrupt it if written
  carelessly. → Mitigation: follow the exact transaction-isolation pattern already
  fixed in PR #75 (v1.11.0) for the `company NOT NULL` migration; write a migration
  test against a copy of a realistic fixture DB before touching any real file.
- **Risk:** `--intake-id` pointing at an already-promoted or nonexistent row could
  silently create an orphaned offer with no linkage, confusing the dashboard. →
  Mitigated by the `[SHOULD]` ACs above (fail the whole `add`, no partial state).
- **Risk:** forgetting to lazy-import `applyr.ui`/FastAPI means every existing user's
  `pip install applyr` (no extras) starts failing at import time. → Mitigation: an
  explicit AC above + a CI job that runs the existing smoke test suite with `[ui]`
  NOT installed.
- **Risk:** scope creep into visual polish before the round trip is proven. →
  Mitigation: `[WONT]` list above is deliberately strict for this slice.

### Task breakdown (execution order)

1. [x] `ui_intake` migration + schema_version bump + `applyr/intake.py` CRUD helpers + migration test [M]
2. [x] `cmd_add` / `cli.py`: `--intake-id` flag, linkage logic, both failure-path ACs, existing `add` tests still pass unmodified [M]
3. [x] `applyr/ui/server.py` + `applyr/ui/api.py`: FastAPI app, all endpoints, JSON error shape, `/api/health` [M]
4. [x] `applyr ui` CLI subcommand + lazy-import guard + missing-dependency error message (no `--host` override — security NFR, see spec) [S]
5. [x] `pyproject.toml` `[ui]` extra + confirm `pip install -e .` (no extra) still imports cleanly [S]
6. [x] Backend tests: `tests/test_ui_intake.py`, `tests/test_ui_api.py`, `tests/test_ui_cli.py` [M]
7. [x] Frontend scaffold: intake form + pending list + job list + job detail, polling via `fetch` + `setInterval` (plain polling, no TanStack Query yet — deferred to a later slice) [L]
8. [x] ADR-011 (`docs/adr/011-visual-ui-optional-interface.md`) [S]
9. [x] Update `docs/visual-ui/AGENTS.md` Status section [S]
10. [x] Manual end-to-end pass against a live server (isolated `APPLYR_HOME`): paste offer → `add --intake-id` → promoted, real score visible in `/api/jobs`, full topic breakdown in `/api/jobs/{id}`, 404s verified [S]

## Traceability Matrix

| AC ID | Priority | AC Description | Test File | Implementation File | Status |
|-------|----------|-----------------|-----------|----------------------|--------|
| AC-DM-1 | [MUST] | Creates `ui_intake` via schema_version migration | test_db.py:714 `test_creates_ui_intake_table` | db.py MIGRATIONS (10,11) | PASS |
| AC-DM-2 | [MUST] | Migration applies exactly once, version recorded | test_db.py:731 `test_migration_idempotent` | db.py `_run_migrations` | PASS |
| AC-DM-3 | [MUST] | Existing offers/topics/gaps unchanged after upgrade | test_db.py:775 `test_offers_and_topics_are_unaffected` | db.py MIGRATIONS (10,11) | PASS |
| AC-IN-1 | [MUST] | POST /api/intake with raw_text creates pending row | test_ui_api.py:28 `test_create_intake` | ui/api.py `post_intake` | PASS |
| AC-IN-2 | [MUST] | Blank/missing raw_text -> 422, no row created | test_ui_api.py:35,42 | ui/api.py `post_intake` | PASS |
| AC-IN-3 | [MUST] | GET /api/intake lists newest-first, supports ?status filter | test_ui_api.py:47,54 | ui/api.py `get_intake_list` | PASS |
| AC-IN-4 | [MUST] | GET /api/intake/{id} 404 on missing id | test_ui_api.py:69 `test_get_intake_404` | ui/api.py `get_intake_one` | PASS |
| AC-LK-1 | [MUST] | `add --intake-id` promotes the row in the same transaction | test_ui_intake.py:136 `test_promotes_the_intake_row_on_success` | commands/core.py `cmd_add` + intake.py `mark_intake_promoted` | PASS |
| AC-LK-2 | [SHOULD] | Nonexistent intake id fails the whole `add`, no partial state | test_ui_intake.py:154 `test_missing_intake_id_fails_the_whole_add` | commands/core.py `cmd_add` | PASS |
| AC-LK-3 | [SHOULD] | Already-promoted intake id fails the whole `add` | test_ui_intake.py:169 `test_already_promoted_intake_id_fails_the_whole_add` | commands/core.py `cmd_add` | PASS |
| AC-LK-4 | [MUST] | `add` without `--intake-id` is byte-identical to before | test_ui_intake.py:147 `test_add_without_intake_id_is_unaffected` (+ full pre-existing add suite, unmodified) | commands/core.py `cmd_add` | PASS |
| AC-JB-1 | [MUST] | GET /api/jobs returns core columns, no pagination | test_ui_api.py:106 `test_list_jobs_core_fields_no_topics` | ui/api.py `get_jobs` | PASS |
| AC-JB-2 | [MUST] | GET /api/jobs/{id} returns full row + topic breakdown | test_ui_api.py:121 `test_job_detail_includes_full_topic_breakdown` | ui/api.py `get_job_detail` | PASS |
| AC-JB-3 | [MUST] | GET /api/jobs/{id} 404 on missing id | test_ui_api.py:116 `test_job_detail_404` | ui/api.py `get_job_detail` | PASS |
| AC-JB-4 | [MUST] | UI backend never computes/alters scores | (structural — `get_jobs`/`get_job_detail` are read-only SELECTs, no write path exists) | ui/api.py | PASS |
| AC-CMD-1 | [MUST] | `applyr ui` without `[ui]` extra: clean error, exit non-zero, no traceback | test_ui_cli.py:46 `test_missing_ui_extra_prints_clean_error_not_a_traceback` | cli.py `elif cmd == "ui"` | PASS |
| AC-CMD-2 | [MUST] | `applyr ui` binds 127.0.0.1, `--port` overridable | test_ui_cli.py:16,25,34 | cli.py `elif cmd == "ui"` + ui/server.py `run` | PASS |
| AC-CMD-3 | [MUST] | `import applyr.cli` never requires fastapi/uvicorn | test_ui_cli.py:72 `test_importing_cli_does_not_require_fastapi` | ui/server.py (lazy imports only) | PASS |
| AC-CMD-4 | [SHOULD] | GET /api/health returns 200 | test_ui_api.py:19 `test_health_ok` | ui/api.py `health` | PASS |
| AC-FE-1 | [SHOULD] | Intake form submission shows up in pending list within one poll | Manual E2E pass (2026-08-23, see Status in docs/visual-ui/AGENTS.md) — no automated frontend test this slice | ui/frontend/src/App.tsx | PASS (manual) |
| AC-FE-2 | [SHOULD] | Promoted intake shows real score in job list on next poll | Manual E2E pass (2026-08-23) | ui/frontend/src/App.tsx | PASS (manual) |

Every `[MUST]` AC has a test and passes. `[SHOULD]` frontend ACs (AC-FE-1/2) are
verified manually rather than with an automated frontend test — no frontend test
runner (Vitest/RTL) was added in this slice; introducing one is deferred to whichever
slice needs it, per the "no scope beyond what the task requires" principle.

## Drift check (Step 6b)

- **Scope drift:** `applyr/intake.py` exists as a new module instead of the CRUD living
  inside `db.py` as the spec's original Affected Files table sketched — documented and
  corrected in that table during implementation (mirrors the existing `duplicates.py`
  convention). No other file outside the Affected Files table was touched, except:
  - `.gitignore` (added `node_modules/` — needed once the frontend scaffold existed,
    not foreseen when the spec was written, purely additive/no behavior change).
- **Coverage gap:** none found — every `[MUST]` AC maps to a passing test above.
- **Behavior drift:** the `--host` CLI override sketched informally in early scoping
  conversation was deliberately *not* implemented — see the security NFR and
  AC-CMD-2/`test_no_host_override_is_exposed`. This is a scope-narrowing correction
  caught during implementation, documented here rather than silently applied.
- **Out-of-scope guardrails**: verified — no WebSocket, Celery, Redis, Postgres, Docker,
  auth, or LLM calls anywhere in the diff.

## Adversarial verification (Step 6d)

Run 2026-08-23, fresh context, contract = this spec's ACs verbatim (Data model, `add
--intake-id` linkage, Jobs read API sections). **Verdict: PASS.** 9 hypotheses attacked
(nonexistent/already-promoted `--intake-id`, transaction atomicity, `add`-without-flag
regression, concurrent double-promotion under `threading.Barrier`-forced races x15
runs, migration data loss/double-apply, `/api/jobs` pagination, backend recomputing
scores, 404 shape) — 0 broken. Added `tests/test_visual_ui_slice1_adversarial.py` (12
tests). Full suite: 768 passing.

Residual risk (documented, not fixed as a defect): the double-promotion race
protection is incidental to statement ordering in `cmd_add` (the offers INSERT runs
before `mark_intake_promoted`'s pending-check SELECT, in the same transaction —
SQLite serializes writers from the first write statement) rather than an explicit
lock. A code comment now guards against reordering this in a future refactor. Full
report saved to Engram (`adversarial:applyr:visual-ui-slice-1`).

### Out of scope

- `[WONT]` Kanban board, filing cabinet, timeline, "office" agent visuals, animations.
- `[WONT]` WebSocket real-time updates (polling only, per the guide).
- `[WONT]` Auth, multi-user, Postgres, Redis, Celery, Docker Compose.
- `[WONT]` Editing/deleting intake rows, bulk actions, search/filters on the job list.
- `[WONT]` Production frontend build / serving the built frontend from FastAPI — this
  slice runs frontend and backend as two separate dev processes.
