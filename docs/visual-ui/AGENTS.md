# applyr Visual UI — Feature Guide

> Read this file first whenever the user says "applyr UI", "la interfaz", "la visual",
> or "dashboard" — it means work happens in this worktree/branch, not in the main
> `applyr` repo. If the user says plain "applyr" or "la tool", this file does not apply.

## What this is

A local, single-user visual dashboard for `applyr`. NOT a rewrite, NOT a SaaS. Full
context/rationale for every decision below lives in the chat session dated 2026-08-22/23
that scoped this down from a much larger multi-tenant proposal
(`APPLYR_VISUAL_AGENTS_PROPOSAL.md`, kept as historical reference only — most of its
infra choices were rejected, see "Explicitly rejected" below).

## Non-negotiable invariants

1. **The engine does not change.** `applyr/db.py`, `scoring.py`, `cv.py`,
   `commands/*.py` are reused, never duplicated. The UI is a new, separate, optional
   package that reads/writes the same SQLite DB.
2. **Claude Code / OpenCode / Cursor remains the brain.** The dashboard never calls an
   LLM API directly and never re-implements Matcher/Recruiter scoring logic. It is a
   viewer + intake form.
3. **Data flow for a new offer:**
   ```
   Dashboard: user pastes/uploads offer text
        -> saved as a "pending" row in the existing jobs DB
        -> user tells their AI agent (in a terminal) to process pending offers
        -> agent runs the existing pipeline (applyr add / update, same as today)
        -> Dashboard polls the same DB (TanStack Query, no WebSocket in v1)
        -> UI reflects real state changes only — never simulate/fake agent progress
   ```
4. **No infrastructure beyond a single process.** No Postgres, no Redis, no Celery, no
   Docker Compose, no auth, no multi-tenancy. Single user, local machine, `applyr ui`
   starts one process and that's it.

## Stack (decided — don't re-litigate without a new decision)

| Layer | Choice |
|---|---|
| Backend | FastAPI, single process, embeds/serves the built frontend |
| DB | Existing SQLite via `applyr/db.py` — no new engine, minimal schema additions only if truly needed |
| Real-time | Polling via TanStack Query `refetchInterval` (2-3s). No WebSocket in v1. |
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS + shadcn/ui + Radix UI + Lucide icons |
| Animation | Framer Motion, 2D/CSS only — no Three.js / 3D |
| Client state | Zustand |
| Packaging | `pip install applyr[ui]` — optional extra. Core `applyr` CLI stays dependency-light (stdlib + colorama), do not add FastAPI/React deps to the base install. |

## Frontend structure (locked in 2026-08-23 — read before adding any file)

Feature-based/domain organization, not the old "everything in `components/`" pattern —
this is current React/Vite best practice (Robin Wieruch's 2026 folder-structure guide
is the most-cited reference on this specific question) and is what keeps a growing
multi-slice dashboard debuggable instead of turning into a junk drawer.

```
applyr/ui/frontend/src/
├── main.tsx / App.tsx / index.css   # entry point + thin root composition
├── assets/                          # images (agent illustrations, etc.)
├── api/                             # the ONLY place that calls fetch()
│   ├── client.ts                    # base wrapper (error shape, base URL)
│   ├── intake.ts, jobs.ts, config.ts  # one file per backend resource, typed
├── features/<domain>/               # agents/, jobs/, intake/, kanban/ (later), ...
│   ├── SomeComponent.tsx            # PascalCase, feature-specific UI
│   ├── some-logic.ts                # kebab-case, PURE function, no React/DOM
│   ├── some-logic.test.ts           # colocated, not a separate __tests__ tree
│   └── types.ts
├── components/ui/                   # shadcn-generated primitives ONLY — never
│                                     # hand-write a component directly in here
├── hooks/                           # cross-feature hooks only (rare)
└── lib/                             # small: cn() helper + app-wide constants only
```

Rules (don't relitigate these per-slice — they're decided):

1. **A feature folder owns everything specific to it** — components, pure logic,
   types, tests, colocated. When `jobs` grows (Kanban, detail panel, timeline), it
   grows inside `features/jobs/`, not spread across generic folders.
2. **`components/ui/` is shadcn-only.** App-specific UI always lives in the relevant
   `features/` folder, never here.
3. **`api/` is the only HTTP boundary.** Features import typed functions from `api/`;
   they never call `fetch` directly. Keeps the backend contract centralized and mockable.
4. **Pure logic lives in its own file, separate from the component that uses it** —
   e.g. `agent-status.ts` vs `AgentCard.tsx`. This is what makes it unit-testable with
   Vitest with zero DOM/jsdom setup, and it's why a "styling-only" slice can still ship
   real, fast unit tests instead of skipping tests entirely.
5. **`lib/` stays small on purpose.** If something feels like it belongs in `lib/` but
   is really about jobs or agents specifically, it goes in that feature folder instead.
6. **Naming:** kebab-case for `.ts` files, PascalCase for `.tsx` components, camelCase
   for exported functions/variables.
7. **Tests are colocated**, never a top-level `__tests__/` tree — a feature folder
   should be fully self-contained and movable/deletable as a unit.

## Explicitly rejected (do not add later without a real trigger)

PostgreSQL, Redis, Celery + queues, WebSockets (v1), auth/multi-tenancy, 3D/Three.js,
Docker Compose, OpenTelemetry/Prometheus, an `LLMProvider` abstraction layer (there is
no direct LLM call from the backend — the AI coding agent is the LLM caller, via CLI).
These solve scale/multi-tenant problems that don't exist for a single local user. If a
concrete trigger appears later (e.g. this becomes multi-user), revisit as a new decision,
not a default.

## Git workflow

- **Integration branch:** `feat/cc-visual-ui` — this is the "developer" branch. Never
  merges into `main` until the user explicitly says the feature is ready.
- **Worktree:** `.worktrees/cc-visual-ui` (gitignored, not tracked). Run the dev server
  here (`applyr ui` / `npm run dev`) and leave it running across sessions — the repo root
  worktree stays free for normal `applyr` CLI work/bug fixes on `main`.
- **Sub-PRs (per phase/feature):**
  - Branch off `feat/cc-visual-ui`, name it `feat/cc-visual-ui-<short-name>`
    (e.g. `feat/cc-visual-ui-backend-skeleton`, `feat/cc-visual-ui-kanban`).
  - Open the PR with **base = `feat/cc-visual-ui`**, never `main`. Double-check the base
    branch before creating every PR — this is the #1 way main gets dirtied by accident.
  - Same discipline as always: work-unit commits (code+tests together), PR budget ≤500
    changed lines per sub-PR (split into chained sub-PRs if a phase is bigger), PR body
    follows the usual template.
- **Keeping in sync with main:** periodically (start of a new phase, or before the final
  PR) run, from inside `feat/cc-visual-ui`:
  ```bash
  git fetch origin main
  git merge origin/main
  ```
  Conflict risk should stay low — this feature lives in new files/a new package and only
  *reads* `db.py`, it doesn't modify existing core modules.
- **Final PR:** only when the user explicitly says the feature is ready to present —
  `feat/cc-visual-ui` -> `main`, reviewed like any other PR.
- **Never:** commit directly to `main` from this work, merge `feat/cc-visual-ui` into
  `main` without explicit approval, or open a sub-PR with base `main`.

## Where the technical spec lives

`specs/visual-ui/` (populated via `/sdd`, one spec per phase/slice as we go — not one
giant upfront spec for the whole feature).

## Status

**Slice 1 implemented (2026-08-23)** — `specs/visual-ui/spec.md`, status IMPLEMENTED.
Backend (`applyr/ui/server.py` + `api.py`), `ui_intake` table + migration
(`applyr/db.py`, `applyr/intake.py`), `applyr add --intake-id` linkage
(`applyr/commands/core.py`), `applyr ui` CLI command, `applyr[ui]` optional extra
(`pyproject.toml`), frontend scaffold (`applyr/ui/frontend/`, unstyled), ADR-011. 35
new backend tests (`tests/test_ui_intake.py`, `tests/test_ui_api.py`,
`tests/test_ui_cli.py`), full suite green (756 tests), manual end-to-end pass verified
against a live server: paste offer -> `add --intake-id` -> promoted -> real score
visible via `/api/jobs`, full topic breakdown via `/api/jobs/{id}`.

Known follow-ups (not blockers for this slice, tracked here so they aren't lost):
- Frontend scaffold's `npm audit` flags a moderate esbuild/vite dev-server advisory
  (GHSA-67mh-4wv8-2f99) — fixing needs a vite major bump (5.x -> 8.x), deferred rather
  than absorbed into this slice; low real risk given the loopback-only threat model, but
  should be revisited before this frontend gets built out further.
- Unrelated applyr core bug found while testing (NOT part of this feature, not fixed
  here): running `applyr init`/`setup-agent` with cwd inside the applyr repo itself
  duplicates content into the repo's own root `AGENTS.md` instead of detecting it's
  already current. Saved to Engram (`bug-agents-md-duplication-on-repo-self-init`) for a
  separate fix.

**Slice 2 implemented (2026-08-23)** — `specs/visual-ui-slice-2/spec.md`, status
IMPLEMENTED. Real design system (Tailwind v4 + shadcn/ui CLI, warm graphite palette,
teal accent, Fraunces/Inter self-hosted, `lucide-react` icons only). New
`GET /api/config` endpoint (read-only thresholds). Agent row with the user's 5
real character illustrations (normalized, compressed to WebP, ~2.3MB -> ~274KB);
Recruiter/Matching show real derived status, CV/ATS/Application honestly show "not
connected yet." Job list restyled as cards with real-threshold color coding; job
detail restyled with the same information as Slice 1. Intake form/list restyled.
Frontend restructured into the locked feature-based layout (`api/`, `features/*`,
`components/ui/` shadcn-only). WCAG AA contrast verified via script — 3 initial
palette values (`highlight`, `danger`, `ring`) were adjusted after failing the check.
10 new Vitest unit tests for the pure logic (`agent-status.ts`, `score-color.ts`),
full Python suite green (771 tests). Confirmed visually by the user against their
real data (245 real offers) before merging.

Next: Slice 3 — sidebar navigation shell (Oficina/Ofertas/Agentes/Entrevistas/
Archivador/Analytics/Ajustes), scoped down in chat 2026-08-23: react-router for real
URLs per tab; ships the full 7-tab shell but with real content only in
Oficina/Agentes/Archivador this slice — Ofertas/Entrevistas/Analytics/Ajustes show an
honest "coming soon" state rather than invented data (Analytics needs a new
`GET /api/stats`-style endpoint wrapping the existing `cmd_stats` funnel logic;
Entrevistas can only reflect `status == 'in_process'`, applyr has no real interview
scheduling/date field despite the reference mockup showing one — never fabricate
that); Ajustes is read-only (displays `/api/config`) — an editable settings page that
writes to `applyr.toml` is deliberately deferred to its own future slice given the
concurrency/validation risk of a config-file write endpoint. Each slice still gets its
own `/sdd` spec, not one upfront spec for everything.
