# ADR 008 — MD-first CV pipeline

**Status:** Accepted
**Date:** 2026-08-08
**Supersedes:** None (new decision)

## Context

The CV pipeline currently generates HTML as its primary artifact. Agents read
HTML markup that `_strip_html_tags` (`cv.py:395`) discards anyway — the markup
is pure overhead in the token cost of `cv review`.

The locked single-column CSS is non-negotiable for ATS safety. The offer→CV
link must remain intact: `cv review` resolves topic scores from the DB via the
`applyr:offer-id` marker (`cv.py:443`). A/B tracking of v0.7.0 (`cv stats`,
`offers.cv_used`) must keep working.

No new runtime dependency (ADR 005). No LLM calls (ADR 003).

## Decision

The CV pipeline becomes markdown-first:

1. `cv generate` produces `cv-<slug>.md` with YAML frontmatter (offer id +
   offer context). Topic scores stay out of the file (`cv.py:190-193`) — they
   carry candid self-assessment that must not reach the recruiter.

2. `cv review` parses markdown directly, without passing through
   `_strip_html_tags`.

3. `cv pdf` accepts `.md` files and renders markdown → ATS-safe HTML → PDF in
   one invocation.

4. Read compatibility is preserved: `.html` files continue to work for `cv
   review` and `cv pdf` (dispatch by extension). Only `cv generate` output
   changes.

5. `offers.cv_used` stores the basename **without extension**, and a migration
   strips the extension from existing values so `cv stats` keeps grouping the
   same CV across `.md`, `.html` and `.pdf`.

6. A new `applyr/md_render.py` module provides a narrow markdown→HTML converter.
   It supports exactly the subset the CV template produces: headings, paragraphs,
   unordered lists, bold, italic, links, and horizontal rules. Unsupported
   syntax causes `die()` with a stable error code naming the line, rather than
   emitting silently wrong HTML.

## Consequences

### Positive

- **Lowest token cost.** The generated draft is ≥40% smaller in bytes than the
  equivalent HTML skeleton — this is the primary motivation.
- **Single source of truth.** One format for drafts; HTML+PDF is a render
  target, not an editable artifact.
- **Editing ergonomics.** Markdown is native to agents; HTML is not.
- **ATS safety enforced centrally.** One render path at PDF time, not two
  parallel paths to keep aligned.
- **No new dependencies.** The converter is hand-rolled, narrow, and deterministic.

### Negative

- **One-off migration.** Existing `.html` CVs and their `cv_used` values need
  the extension-stripping migration (AC-3.10). Paid once, at a pre-1.0 version
  where breaking a CLI contract is cheapest.
- **Hand-rolled md→HTML.** Where correctness bugs will hide. Mitigated by
  keeping the supported subset deliberately narrow and refusing unsupported
  syntax loudly.
- **Breaking change.** `cv generate` output changes from `.html` to `.md`.
  Documented in CHANGELOG with migration guidance.

### Neutral

- Existing `.html` CVs are not converted. They render and review as they are.
  The `.md` path is forward-only.

## Alternatives considered

**B. MD alongside HTML, behind `--format md`.** Rejected. The default path
stays expensive, and "two paths indefinitely" is the shape that later rots —
the HTML branch would keep every bug the MD branch fixes.

**C. Keep HTML, strip it before the agent reads it.** Rejected. It leaves the
draft and the artifact in two formats with no single source of truth, which is
the actual defect.

**D. Slim the HTML template.** Rejected. It reduces the symptom and keeps the
agent editing markup.

Option A is chosen because it has the lowest token cost, the best editing
ergonomics, and a single maintenance path. The cost is a one-off migration,
paid once.

## Notes

- ADR 005 (single CLI, one dependency) rules out adding `markdown` or `mistune`
  from PyPI for the md→HTML step.
- ADR 003 (no LLM calls) rules out "let a model convert the markdown."
- The converter's narrow scope (headings, paragraphs, ul, bold, italic, links,
  hr) is a deliberate constraint, not a limitation to be expanded later. Tables
  in particular are ATS-hostile and must stay unsupported.

Related: [ADR 003](003-no-llm-calls.md), [ADR 005](005-single-cli.md),
[`../contracts.md`](../contracts.md).
