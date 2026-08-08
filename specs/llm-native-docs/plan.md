# Technical Plan: Applyr LLM-Native Documentation

## Spec Reference
Implements: `specs/llm-native-docs/spec.md`

## Architecture Overview

All changes are documentation-only — no application code is modified. Files are organized into 4 independent PRs, each under 400 lines, to keep reviews manageable and allow parallel execution where possible.

The key insight: Applyr already has good code and a solid README. What's missing is the **agent-facing layer** (AGENTS.md, llms.txt) and the **contributor-facing layer** (CONTRIBUTING.md, examples/, docs/).

## Component Breakdown

### PR-A: Agent-Facing Docs (AGENTS.md + llms.txt)
- **Responsibility:** Make agents understand the project in <60 seconds
- **Files:** `AGENTS.md`, `llms.txt`
- **AC Coverage:** AC-1, AC-2, AC-E1, AC-E2

### PR-B: Contributor Docs (CONTRIBUTING.md + CHANGELOG.md)
- **Responsibility:** Make humans able to contribute correctly
- **Files:** `CONTRIBUTING.md`, `CHANGELOG.md`
- **AC Coverage:** AC-3, AC-6

### PR-C: Executable Examples
- **Responsibility:** Show working code for all major use cases
- **Files:** `examples/basic_usage.py`, `examples/add_offer.py`, `examples/cli_usage.sh`
- **AC Coverage:** AC-4

### PR-D: Organized Documentation
- **Responsibility:** Detailed reference docs for deep dives
- **Files:** `docs/getting-started.md`, `docs/architecture.md`, `docs/cli-reference.md`, `docs/troubleshooting.md`
- **AC Coverage:** AC-5, AC-7, AC-8

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Doc format | Markdown | Agents read markdown natively, GitHub renders it |
| Diagram syntax | Mermaid | GitHub renders inline, agents understand it |
| Example language | Python 3.12+ | Matches project requirement |
| Changelog format | Keep a Changelog | Industry standard, agents recognize it |

## AC Coverage Map

| AC | PR | Files |
|----|-----|-------|
| AC-1 | A | AGENTS.md |
| AC-2 | A | llms.txt |
| AC-3 | B | CONTRIBUTING.md |
| AC-4 | C | examples/* |
| AC-5 | D | docs/* |
| AC-6 | B | CHANGELOG.md |
| AC-7 | D | docs/getting-started.md |
| AC-8 | D | docs/architecture.md |
| AC-E1 | A | AGENTS.md |
| AC-E2 | A | AGENTS.md |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Docs drift from code | Medium | Medium | Include doc updates in PR checklist |
| Too verbose for agents | Low | High | Enforce <500 lines per file, test with agent |
| Examples become outdated | Medium | Low | Pin examples to current version, add version note |

## PR Budget

| PR | Files | Est. Lines | Under 400? |
|----|-------|-----------|------------|
| A | 2 | ~250 | Yes |
| B | 2 | ~200 | Yes |
| C | 3 | ~150 | Yes |
| D | 4 | ~400 | Yes |
| **Total** | **11** | **~1000** | — |
