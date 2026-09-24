# Plan: CLI-Enforced Pipeline Gates

### Affected files
| File | Action | Reason | PR |
|------|--------|--------|----|
| `docs/adr/015-cli-enforced-pipeline-gates.md` | CREATE | Governing decision | 0 |
| `docs/adr/README.md` | MODIFY | ADR index | 0 |
| `applyr/cv.py` | MODIFY | Extract `_verify_cv()` from `cmd_cv_verify`; gate + `--force` in `cmd_cv_pdf` | 1 |
| `applyr/commands/core.py` | MODIFY | `score_source` validation + deprecation warning in `cmd_add` | 1 |
| `applyr/cli.py` | MODIFY | `--force` on `cv pdf` | 1 |
| `examples/*.py`, `examples/cli_usage.sh`, `llms.txt` | MODIFY | Add `score_source: "manual"` to manual-score examples | 1 |
| `tests/test_cv_pdf.py`, `tests/test_commands.py` | MODIFY | AC-01..07, AC-E1..E3 | 1 |
| `tests/test_cli_routing.py` | MODIFY | `--force` reaches `cmd_cv_pdf` | 1 |
| `docs/contracts.md` | MODIFY | New `verify_required` error code | 1 |
| `docs/getting-started.md` | MODIFY | Manual-score example (AC-07) | 1 |
| `applyr/cv.py` | MODIFY | `--record` for `cmd_cv_review` / `cmd_cv_review_blind` | 2 |
| `applyr/pipeline_next.py` | CREATE | Pure `derive_next()` + history read/append helpers | 2 |
| `applyr/commands/workflow.py` | MODIFY | `cmd_next` (I/O wrapper around `derive_next`) | 2 |
| `applyr/cli.py` | MODIFY | `next` command, `--record` flags, help text | 2 |
| `applyr/templates/AGENT_INSTRUCTIONS.md` | MODIFY | Document `next`, `--record`, pdf gate | 2 |
| `tests/test_pipeline_next.py` | CREATE | AC-08..21, AC-E4..E7 | 2 |
| `applyr/constants.py` | MODIFY | `CV_REVIEW_*` verdict bands and iteration cap | 2 |
| `applyr/commands/__init__.py` | MODIFY | Export `cmd_next` | 2 |
| `docs/contracts.md` | MODIFY | New `history_corrupt` error code | 2 |
| `CHANGELOG.md` | MODIFY | Unreleased entry, each PR | 1, 2 |

### Dependencies
- DB: `offers.cv_iteration`, `offers.cv_iteration_history`, `offers.notes`, `offers.status`,
  `offers.cv_used`, `offer_topics`. No new columns, `SCHEMA_VERSION` unchanged (14).
- Reused: `_extract_offer_id_from_md`, `get_output_dir`, the `cv_used` → file resolver
  (`cv.py` ~L1531, factored into a helper that `next` reuses), `recommendation_for`,
  `die()` structured errors, `warn()`.

### Design
- **`_verify_cv(cv_path) -> VerifyResult`** (offer_id, results, unsupported, passed,
  evidence_density). Pure except for reading cv-master and the offer's `tech_stack`.
  Reports "cannot verify" cases as data instead of dying (see next point).
  `cmd_cv_verify` keeps printing and the `cv_evidence_used`
  snapshot; `cmd_cv_pdf` calls it before rendering.
- The pdf gate has to turn "cannot verify at all" into `verify_required` (or, with
  `--force`, a warning) instead of dying. `_verify_cv` therefore returns
  `{"unverifiable": <code>}` for `no_offer_id`, `not_found` and `cv_master_missing`,
  and `cmd_cv_verify` keeps dying with those same codes at the call site. (Found in
  review: dying on a missing cv-master.md made `--force` unable to render.)
- **History**: `read_history(raw) -> list` (raises a structured `history_corrupt` error on
  invalid JSON or a non-list value) and `append_history(conn, offer_id, entry)`, which
  updates the history and `cv_iteration` (only for `cv_review`) in one `UPDATE`.
- **`derive_next(offer, topics_count, history, cv_path, pdf_path, verify_result, config)
  -> dict`**: pure function with no I/O, so every AC is unit-testable without Chrome or
  real files. `cmd_next` gathers the inputs (mtimes, live verify only when the state
  reaches `verify`) and prints text or JSON:
  `{"offer_id", "state", "command", "reason", "needs_user_confirmation", "warnings": []}`.
- "Manual score" in `next` = `compatibility_pct` > 0 with no topic rows.

### Explicit technical assumptions
- File mtimes are a trustworthy "edited after" signal on a local single-user disk.
  If false (clock skew, a copied file) → the worst case is one extra review or PDF
  request, never a skipped gate.
- `cv_iteration_history` is NULL for every existing offer (the column has never been
  written). NULL → empty list.

### Non-functional
- `next` runs in under 1 s on a typical CV. Verify runs at most once per call.
- No new dependency, no LLM call (ADR 003).

### Risks
- Agents or scripts that render unverified CVs break → the message names both
  `cv verify` and `--force`, and the change goes in the CHANGELOG under **Changed**.
- The PR 1 refactor of `cmd_cv_verify` changes verify output → the existing
  `tests/test_cv_verify*.py` run unchanged as the regression net.
