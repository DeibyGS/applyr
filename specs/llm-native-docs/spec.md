# Spec: Applyr LLM-Native Documentation

Status: APPROVED
Version: 1.0
Last updated: 2026-08-07

## Overview

Make Applyr maximally understandable by AI coding agents (Claude Code, Cursor, OpenCode, Codex) through targeted documentation files that agents read automatically, without changing any application logic.

## Context

Applyr is a CLI job tracker that works **WITH** AI agents, not **THROUGH** them. It has no LLM API integration — and that's correct. The goal is not to add LLM features, but to make agents understand the project instantly when they encounter it.

### What Applyr IS
- Python 3.12+ CLI tool
- SQLite local storage
- Chrome headless for PDF generation
- Works with AI agents via `AGENT_INSTRUCTIONS.md`

### What Applyr is NOT
- An LLM-powered tool
- A project that calls OpenAI/Anthropic APIs
- A project with src/cli/models/services architecture

## Files to Create/Modify

| File | Action | Reason |
|------|--------|--------|
| `AGENTS.md` | CREATE | Agent-facing contributor guide |
| `llms.txt` | CREATE | Quick agent summary |
| `CONTRIBUTING.md` | CREATE | Human contributor guide |
| `CHANGELOG.md` | CREATE | Version history |
| `examples/basic_usage.py` | CREATE | Minimal usage example |
| `examples/add_offer.py` | CREATE | Programmatic offer registration |
| `examples/cli_usage.sh` | CREATE | CLI examples |
| `docs/getting-started.md` | CREATE | Setup guide |
| `docs/architecture.md` | CREATE | Architecture + Mermaid diagram |
| `docs/cli-reference.md` | CREATE | All commands documented |
| `docs/troubleshooting.md` | CREATE | Common errors + fixes |

## User Stories

### Primary
As an AI agent, I want to understand Applyr's architecture, conventions, and commands in <60 seconds so that I can modify code correctly without hallucinating patterns.

### Secondary
As a human contributor, I want clear contribution guidelines so that I can submit PRs that follow project conventions.

## Boundaries

**Always do:**
- Keep all docs in English (agents read English better)
- Keep files under 500 lines each
- Cross-reference between docs

**Never do:**
- Add LLM API dependencies (OpenAI, Anthropic, etc.)
- Change application logic
- Add runtime dependencies
- Modify the existing AGENT_INSTRUCTIONS.md (it's for end-users, not contributors)

## Acceptance Criteria

### AC-1: AGENTS.md exists at project root [MUST]
Given an AI agent opens the applyr repository
When it reads `AGENTS.md`
Then it understands: project purpose, architecture, file responsibilities, conventions, how to add features, what not to modify

### AC-2: llms.txt exists at project root [MUST]
Given an AI agent needs a quick summary
When it reads `llms.txt`
Then it gets: purpose, install, run, architecture, entry points, testing — all in <200 lines

### AC-3: CONTRIBUTING.md exists [MUST]
Given a contributor wants to submit a PR
When it reads `CONTRIBUTING.md`
Then it knows: setup, test commands, lint commands, branch naming, commit format, PR checklist

### AC-4: examples/ directory with executable examples [MUST]
Given an agent or human wants to understand usage
When they read `examples/`
Then they find: working code snippets for all major use cases

### AC-5: docs/ directory with organized documentation [SHOULD]
Given an agent needs detailed information
When it reads `docs/`
Then it finds: getting started, architecture, CLI reference, troubleshooting — each <300 lines

### AC-6: CHANGELOG.md following Keep a Changelog [SHOULD]
Given an agent needs version history
When it reads `CHANGELOG.md`
Then it sees: all versions with changes, in standard format

### AC-E1: Agent can install and run without human help [MUST]
Given a fresh clone of applyr
When an agent follows AGENTS.md
Then it can: install deps, run tests, build, verify all pass

### AC-E2: Agent can add a new command without hallucinating [MUST]
Given an agent needs to add `applyr foo`
When it follows AGENTS.md "How to add a command" section
Then it knows: which file to edit, what pattern to follow, how to register it in cli.py

## Out of Scope
- Adding LLM API integration
- Changing application architecture
- Adding new features to applyr itself
- Modifying existing AGENT_INSTRUCTIONS.md (end-user facing)
- Adding new dependencies
