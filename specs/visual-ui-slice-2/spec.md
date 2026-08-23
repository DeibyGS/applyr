# Spec: Visual UI — Slice 2 (design system + agent row + job cards)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **Project constitution:**
  - `docs/visual-ui/AGENTS.md` — invariants for the whole feature: engine unchanged, AI
    coding agent remains the sole reasoner, no Postgres/Redis/Celery/auth/Docker, no
    WebSocket (polling only), **no 3D/Three.js — 2D/CSS + Framer Motion only**, stack =
    FastAPI + existing SQLite + React/TS/Vite + Tailwind + shadcn/ui, loopback-only.
  - `specs/visual-ui/spec.md` (Slice 1, IMPLEMENTED) — what already exists: `ui_intake`
    table + migration, `applyr add --intake-id` linkage, FastAPI backend
    (`/api/health`, `/api/intake[/{id}]`, `/api/jobs[/{id}]`), unstyled React scaffold.
  - ADR-011 — Visual UI is an optional, additive interface; base CLI unaffected.
  - ADR-003 — no LLM calls from the backend; still true here, this slice is pure
    presentation over Slice 1's data.
  - `docs/visual-ui/AGENTS.md` "Frontend structure" (locked 2026-08-23) — feature-based
    domain folders (`features/<domain>/`), `components/ui/` reserved for shadcn only,
    `api/` as the sole HTTP boundary, pure logic colocated with but separate from the
    component that uses it, tests colocated. This is the first slice to populate that
    structure — everything below follows it.
- **Relevant ADRs:** 003, 005, 011. No conflicts.
- **Engram:** no prior decisions on this specific slice found.
- **Corrected assumptions from Step 2 (user-confirmed 2026-08-23):**
  1. No backend/DB schema changes beyond one new tiny read-only endpoint (see below) —
     Recruiter/Matching stats are derived client-side from existing `/api/intake` and
     `/api/jobs` responses.
  2. Recruiter = "Working" (accent-colored badge) while any `ui_intake` row has `status='pending'`;
     shows the real pending count. "Idle" otherwise.
  3. Matching = "Working" while any offer has `status='pending'` (scored, awaiting
     decision); shows the most-recently-created such offer's real company +
     `compatibility_pct`. "Idle" otherwise.
  4. CV / ATS / Application agents always render a "Not connected yet" state —
     desaturated illustration, muted badge, no task text. Nothing about them is
     invented; they activate in a future slice once those flows persist real state.
  5. Typography self-hosted via `@fontsource` packages (no Google Fonts CDN) — Fraunces
     (display) + Inter (body/data). Revised 2026-08-23 after design research (see
     "Design system — revised direction" below): Space Grotesk was the generic default
     for this exact kind of product and was dropped.
  6. Job list becomes real cards this slice (not deferred to the Kanban slice). Clicking
     a card still shows the same information Slice 1's detail view showed (full topic
     breakdown) — restyled, not re-scoped.
  7. shadcn/ui installed via its CLI; generated components committed as local files.
  8. Framer Motion scope: agent-row entrance stagger, hover micro-interactions, status
     badge transitions. No character animation, no scene choreography — the agent row
     itself is the one "signature" risk this slice spends its boldness on.
  9. Dark mode only, no light/dark toggle.
  10. Accessibility floor: responsive to mobile, visible keyboard focus,
      `prefers-reduced-motion` respected.
  11. No Canvas/WebGL anywhere — confirmed with the user 2026-08-23, consistent with
      the existing "no 3D" invariant. The agent row is plain DOM/CSS elements (the PNG
      illustrations) positioned with flexbox/grid, animated via Framer Motion the same
      way any other React component would be.
  12. No emoji, no ad-hoc/hand-drawn icons anywhere in the UI — every icon comes from
      `lucide-react` (already a shadcn/ui dependency, no extra package needed).

### What does it do? (observable behavior, not implementation)

- Opening the dashboard now shows a real visual identity (warm graphite, teal accent,
  Fraunces/Inter) instead of unstyled HTML.
- A horizontal row of 5 illustrated agents greets the user. Recruiter and Matching show
  real, live status and counts pulled from the actual database — never simulated. The
  other 3 visibly exist (so the "full team" concept reads correctly) but are honestly
  marked as not wired up yet.
- The job list is now a grid of cards, color-coded by real compatibility score against
  the user's actual configured thresholds (not a hardcoded guess).
- Clicking a job card still opens the exact same detail information Slice 1 showed,
  now styled consistently with the rest of the app.
- The intake form and pending-intake list are restyled with the same design system.

### Design system — revised direction (2026-08-23)

The original draft (near-black/navy background + one amber accent + Space Grotesk) was
identified, via design research, as the "techno-futurist" default that most AI-product
dashboards already use in 2026 — not a distinctive choice. Revised after researching
current trends (Muzli, AYDesign, Recursion Agency — see chat for full citations) and an
explicit user constraint (no emoji, no ad-hoc icons — Lucide only):

- **Warm graphite, not navy** — background reads warm/near-black rather than
  cool-blue-black, avoiding the generic "AI dark mode" undertone.
- **One saturated accent (teal), not a gold/amber default** — teal reads as
  trustworthy + premium + human per current research, and is uncommon among AI tools
  (which skew purple/blue/violet or amber/gold).
- **Copper reserved for high-value moments only** (a strong match score, the primary
  CTA) — never a secondary color used throughout, keeping the palette calm.
- **Fraunces (serif) for display, not Space Grotesk** — thematically tied to the
  product's actual subject (CVs, cover letters, documents), and a serif-on-dark
  combination doesn't reproduce the cream+serif "editorial" cluster either.

#### Acceptance criteria

#### Design system
- `[MUST]` The system shall apply one shared token set across every Visual UI screen:
  background `#1A1917`, surface `#24221F`, accent `#1F6F5C` (teal), highlight
  `#CB6E45` (copper, reserved for high-value moments only — not a general secondary
  color), text-primary `#F0EDE6`, text-muted `#9B9488`, success `#4FA98A`, warning
  `#D89B5A`, danger `#C96B52`, focus ring `#3FA98B`.
- `[MUST]` Every text/background color pair shall meet WCAG AA contrast (>= 4.5:1 for
  normal text, >= 3:1 for UI-component/focus indicators) against `#1A1917` or
  `#24221F`. Verified 2026-08-23 via a contrast-ratio script during the accessibility
  pass — `highlight`, `danger`, and `ring` were adjusted from their initial design
  values (`#C4653B`, `#B85C4A`, `#1F6F5C`) after failing this check (2.9–4.4:1); the
  rest of the original palette already passed (5.15–15.03:1).
- `[MUST]` The system shall use Fraunces for display/headings and Inter for body/data
  text, both self-hosted via `@fontsource` — zero external font requests.
- `[MUST]` The system shall install shadcn/ui via its CLI; generated component files
  shall be committed to the repo (not fetched at runtime).
- `[MUST]` The system shall use `lucide-react` for every icon in the UI — no emoji,
  no hand-drawn/ad-hoc icon assets anywhere.
- `[SHOULD]` The system should respect `prefers-reduced-motion` by disabling
  non-essential Framer Motion transitions when set.

#### Score thresholds (new, minimal backend addition)
- `[MUST]` WHEN `GET /api/config` is called THE system SHALL return the user's actual
  configured `threshold_apply` and `threshold_maybe` (read from `applyr.toml` via the
  existing `load_config()`), read-only, no write path.
- `[MUST]` The frontend shall color-code compatibility scores using these real
  thresholds (>= threshold_apply -> success color, >= threshold_maybe -> warning color,
  below -> muted/danger color) — never a hardcoded guess at the user's cutoffs.

#### Agent row
- `[MUST]` WHEN the Overview page loads THE system SHALL render all 5 agent cards
  (Recruiter, Matching, CV, ATS, Application) using the normalized illustration assets
  at `applyr/ui/frontend/src/assets/agents/`.
- `[MUST]` WHILE at least one `ui_intake` row has `status='pending'` THE Recruiter card
  SHALL show a "Working" badge and the real pending count.
- `[MUST]` WHILE zero `ui_intake` rows have `status='pending'` THE Recruiter card SHALL
  show an "Idle" badge.
- `[MUST]` WHILE at least one offer has `status='pending'` THE Matching card SHALL show
  a "Working" badge and the most-recently-created such offer's real company name and
  `compatibility_pct`.
- `[MUST]` WHILE zero offers have `status='pending'` THE Matching card SHALL show an
  "Idle" badge.
- `[MUST]` The CV, ATS, and Application agent cards SHALL always render a "Not
  connected yet" state: desaturated illustration, muted badge, no task text.
- `[MUST]` The system shall never render an agent status or task string that is not
  directly derived from a real `/api/intake` or `/api/jobs` response — no placeholder
  percentages, no invented task descriptions.
- `[SHOULD]` The agent row should animate in with a staggered entrance on first render.

#### Job cards
- `[MUST]` WHEN the job list renders THE system SHALL display each offer as a card
  (title, company, status, compatibility_pct with real-threshold color coding) instead
  of a plain list row.
- `[MUST]` Given a job card is clicked, When the detail loads, Then it shows the exact
  same fields Slice 1's detail view showed (full `offer_topics` breakdown) — restyled,
  with no information added or removed.
- `[SHOULD]` Job cards should show `work_mode` and `location` when present, omitted
  when null (never a placeholder like "N/A").

#### Intake form + pending list
- `[MUST]` The intake form and pending-intake list shall be restyled with the shared
  design system and shadcn components, with no change to their Slice 1 behavior
  (same fields, same `POST /api/intake` call, same polling).

#### Assets
- `[MUST]` The 5 agent illustration PNGs shall be compressed/optimized before being
  committed — current combined size (~2.4MB) is too heavy to ship as-is for 5 images
  appearing on every page load.

#### Out-of-scope guardrails
- `[WONT]` The right-side "Oferta actual" detail panel from the reference images —
  deferred to a future slice.
- `[WONT]` Kanban board — deferred to its own slice.
- `[WONT]` Timeline / activity log view — deferred.
- `[WONT]` Canvas/WebGL, 3D, character animation/choreography.
- `[WONT]` Light mode / theme toggle.
- `[WONT]` A notification system (the reference's bell icon) — out of scope; if shown
  at all, it is a static, non-interactive count, not a real feature.

### Affected files

| File | Action | Reason |
|---|---|---|
| `applyr/ui/api.py` | MODIFY | Add `GET /api/config` (read-only thresholds) |
| `applyr/ui/frontend/package.json` | MODIFY | Add tailwindcss, postcss, autoprefixer, framer-motion, @fontsource/fraunces, @fontsource/inter, shadcn deps |
| `applyr/ui/frontend/tailwind.config.ts` | CREATE | Design tokens as Tailwind theme extension |
| `applyr/ui/frontend/postcss.config.js` | CREATE | Required by Tailwind |
| `applyr/ui/frontend/components.json` | CREATE | shadcn CLI config |
| `applyr/ui/frontend/src/index.css` | MODIFY | Tailwind directives + CSS variables |
| `applyr/ui/frontend/src/lib/utils.ts` | CREATE | shadcn's `cn()` helper (only generic thing in `lib/`) |
| `applyr/ui/frontend/src/components/ui/*` | CREATE | shadcn-generated primitives only: button, card, badge |
| `applyr/ui/frontend/src/api/client.ts` | CREATE | Base fetch wrapper (error shape, base URL) — replaces slice 1's `api.ts` |
| `applyr/ui/frontend/src/api/intake.ts` | CREATE | Typed intake endpoint calls |
| `applyr/ui/frontend/src/api/jobs.ts` | CREATE | Typed jobs endpoint calls |
| `applyr/ui/frontend/src/api/config.ts` | CREATE | Typed `/api/config` call |
| `applyr/ui/frontend/src/features/agents/agent-status.ts` | CREATE | Pure derivation logic: intake/jobs -> agent status (unit-testable, no DOM) |
| `applyr/ui/frontend/src/features/agents/agent-status.test.ts` | CREATE | Unit tests for the data-driven status derivation |
| `applyr/ui/frontend/src/features/agents/AgentCard.tsx` | CREATE | One agent's illustration + badge + task text |
| `applyr/ui/frontend/src/features/agents/AgentRow.tsx` | CREATE | Composes 5 AgentCards, entrance animation |
| `applyr/ui/frontend/src/features/agents/types.ts` | CREATE | Agent status/domain types |
| `applyr/ui/frontend/src/features/jobs/score-color.ts` | CREATE | Pure function: score + real thresholds -> color band |
| `applyr/ui/frontend/src/features/jobs/score-color.test.ts` | CREATE | Unit tests for threshold-based color banding |
| `applyr/ui/frontend/src/features/jobs/JobCard.tsx` | CREATE | Replaces the plain job list row |
| `applyr/ui/frontend/src/features/jobs/JobList.tsx` | CREATE | Grid composition of JobCards |
| `applyr/ui/frontend/src/features/intake/IntakeForm.tsx` | CREATE | Extracted + restyled from App.tsx |
| `applyr/ui/frontend/src/features/intake/PendingIntakeList.tsx` | CREATE | Extracted + restyled from App.tsx |
| `applyr/ui/frontend/src/App.tsx` | MODIFY | Thin composition of feature components, new layout |
| `applyr/ui/frontend/src/assets/agents/*.webp` | MODIFY | Converted from PNG to WebP (q88, alpha preserved) — ~2.3MB combined -> ~274KB |
| `applyr/ui/frontend/vitest.config.ts` | CREATE | Minimal Vitest setup for pure-logic unit tests |
| `tests/test_ui_api.py` | MODIFY | Add tests for `GET /api/config` |
| `docs/visual-ui/AGENTS.md` | MODIFY | Status update once this slice ships |

### Dependencies

- New frontend deps: `tailwindcss`, `postcss`, `autoprefixer`, `framer-motion`,
  `@fontsource/fraunces`, `@fontsource/inter`, shadcn's own deps
  (`class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, relevant
  `@radix-ui/*` primitives per component added), `vitest` (dev dep, unit tests only).
- No new Python deps.
- `GET /api/config` reads `applyr.toml` via the existing `load_config()` — no new
  storage.

### Explicit assumptions

- We assume `load_config()` is cheap enough to call per-request (it already is — every
  existing CLI command does this) → if that ever changes, cache at the app level.
- We assume the 5 illustration assets' current single "working" pose is sufficient for
  both the "Working" and "Idle" visual states (Idle = same image, muted/reduced
  opacity, not a distinct pose) → if that reads oddly in practice, a distinct idle pose
  is a future-slice addition, not a blocker now.

### Non-functional requirements

- **Performance:** total agent illustration payload after optimization should be
  meaningfully under the current ~2.4MB (target: each PNG under ~150KB, or convert to
  WebP if that lands smaller without visible quality loss).
- **Accessibility:** visible focus rings on all interactive elements; agent status
  conveyed through both color and text (never color alone); `prefers-reduced-motion`
  disables the entrance stagger and hover transforms.
- **Security:** `GET /api/config` returns only `threshold_apply`/`threshold_maybe` —
  never the full config file (which could contain a `chrome_path` or other local
  filesystem detail irrelevant and unnecessary to expose over HTTP, even on loopback).

### Edge cases / risks

- **Risk:** hardcoding score color bands instead of reading real thresholds would
  misrepresent the user's own configured cutoffs (this user's are 65/55, not a generic
  default) → mitigated by the new `/api/config` endpoint, not a guess.
- **Risk:** shipping 2.4MB of illustrations un-optimized would make the dashboard feel
  slow on first load → mitigated by an explicit compression task before committing.
- **Risk:** a "Not connected yet" state for 3 of 5 agents could look like a bug rather
  than an honest boundary if not visually deliberate → mitigate with a clear, calm
  treatment (desaturation + a plain-language badge), not an error-red warning.

### Task breakdown (execution order)

1. [x] Tailwind v4 (`@tailwindcss/vite`) + design tokens (CSS variables) + shadcn CLI init [M]
2. [x] Self-hosted fonts wired in (`@fontsource/fraunces`, `@fontsource-variable/inter`) [S]
3. [x] Compress the 5 agent illustrations — converted PNG->WebP, ~2.3MB -> ~274KB [S]
4. [x] `GET /api/config` backend endpoint + test [S]
5. [x] `agent-status.ts` + `score-color.ts` pure logic modules + Vitest setup + unit tests [M]
6. [x] `AgentCard` + `AgentRow` components (5 states incl. "not connected") + entrance animation [L]
7. [x] `JobCard` + `JobList` + `JobDetail` using real threshold color coding [M]
8. [x] `IntakeForm` + `PendingIntakeList` restyle with shadcn components [S]
9. [x] `App.tsx` recomposition + `api/` layer (client.ts, intake.ts, jobs.ts, config.ts) [S]
10. [x] Accessibility pass — found and fixed 3 WCAG AA contrast failures (`highlight`,
    `danger`, `ring`) via a contrast-ratio script; keyboard-operable job cards;
    `prefers-reduced-motion` respected [M]
11. [x] Manual visual verification: both servers run against the user's real data (245
    offers); confirmed by the user directly in browser [S]
12. [x] Update `docs/visual-ui/AGENTS.md` Status section [S]

## Traceability Matrix

| AC | Priority | Description | Verified by | Status |
|---|---|---|---|---|
| Design tokens | [MUST] | Shared token set across screens | `src/index.css` `:root`; visual confirmation | PASS |
| Fraunces/Inter | [MUST] | Self-hosted, zero external font requests | `vite build` output shows fonts bundled locally, no CDN `<link>` | PASS |
| shadcn via CLI | [MUST] | Components committed as local files | `src/components/ui/*.tsx` present, git-tracked | PASS |
| Lucide only, no emoji | [MUST] | Every icon via `lucide-react` | `Lock`/`ArrowLeft` imports in AgentCard/JobDetail; no emoji anywhere in `src/` | PASS |
| `GET /api/config` | [MUST] | Real thresholds, no write path | `tests/test_ui_api.py::TestConfig` (3 tests) | PASS |
| Score color from real thresholds | [MUST] | No hardcoded guess | `score-color.test.ts` (4 tests, incl. a differing-thresholds case) | PASS |
| 5 agent cards render | [MUST] | Recruiter/Matching/CV/ATS/Application, real assets | `agent-status.test.ts` "always returns exactly 5" + visual confirmation | PASS |
| Recruiter working/idle | [MUST] | Real pending-intake-derived | `agent-status.test.ts` (2 tests) | PASS |
| Matching working/idle | [MUST] | Real most-recent-pending-offer-derived | `agent-status.test.ts` (2 tests) | PASS |
| CV/ATS/Application not_connected | [MUST] | Never invented activity | `agent-status.test.ts` "always not_connected regardless of data" | PASS |
| No invented agent status | [MUST] | Structural — `deriveAgentStatuses` only reads its two arguments | Code review (no other data source touched) | PASS |
| Job cards replace plain list | [MUST] | Title/company/status/score, color-coded | `JobCard.tsx`; visual confirmation | PASS |
| Job detail unchanged information | [MUST] | Same fields as Slice 1, restyled | `JobDetail.tsx` renders all `JobDetailType` fields incl. full `topics[]` | PASS |
| Intake form/list restyled, same behavior | [MUST] | Same `POST /api/intake` call, same polling | `IntakeForm.tsx`/`PendingIntakeList.tsx` reuse `@/api/intake` unchanged | PASS |
| Illustrations compressed | [MUST] | Too heavy to ship as-is | ~2.3MB PNG -> ~274KB WebP (measured) | PASS |

Every `[MUST]` AC has verification. `[SHOULD]` items (entrance stagger, reduced-motion,
work_mode/location shown-when-present) were implemented and spot-checked but have no
dedicated automated test — acceptable for this slice per the "pure logic gets unit
tests, visual/presentational behavior gets manual verification" split stated in the
spec's own design.

### Drift check

- **Scope drift:** the frontend structure convention (`docs/visual-ui/AGENTS.md`
  "Frontend structure") was written *during* this slice, not before it — the user
  asked for it mid-implementation. Applied retroactively to every file in this slice
  (nothing was left in the old flat layout). Documented as a locked convention for all
  future slices, not just this one.
- **Coverage gap:** none found for `[MUST]` ACs.
- **Behavior drift:** none — implementation matches the spec's revised design-system
  section (Fraunces/teal/copper, not the original Space Grotesk/amber/navy draft).
- **Out-of-scope guardrails:** verified — no Kanban, no timeline, no right-side detail
  panel, no Canvas/WebGL, no light mode, no notification system, no editable settings.

### Adversarial verification

Not run. This slice's risk category is presentation/design-system, not
auth/money/data-integrity/migration/state-machine/idempotency — none of the triggers in
the project's high-risk-change list apply. `GET /api/config` is a new read-only
endpoint with no write path and no sensitive full-file exposure (covered by its own 3
unit tests, including one specifically asserting the full config is never leaked).

### Out of scope

- `[WONT]` "Oferta actual" right-side detail panel, Kanban, timeline — later slices.
- `[WONT]` Canvas/WebGL, 3D, character animation.
- `[WONT]` Light mode.
- `[WONT]` Real notification system.
- `[WONT]` Idle/working distinct illustration poses per agent (single pose + opacity
  treatment covers both states this slice).
