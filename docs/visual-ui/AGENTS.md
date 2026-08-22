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

Setup only so far: worktree + integration branch created (2026-08-23). No implementation
yet. Next step: `/sdd` for the first vertical slice (see chat session for the agreed
slice-by-slice approach — backend skeleton + minimal data model + upload endpoint +
polling, before any visual polish).
