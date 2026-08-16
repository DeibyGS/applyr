# Getting Started

## Install

```bash
pip install applyr
```

Or from source:

```bash
git clone https://github.com/DeibyGS/applyr
cd applyr
pip install -e ".[dev]"
```

## Initialize

```bash
applyr init
```

This creates `~/.applyr/` with:
- `applyr.toml` — configuration
- `jobs.db` — SQLite database
- `cv-master.md` — your professional profile (fill this in)
- `templates/` — CV templates

## Configure

Edit `~/.applyr/applyr.toml` (optional — defaults work):

```toml
[general]
threshold = 65          # Min % to recommend applying
followup_days = 10      # Days before follow-up reminder

[weights]
tech_stack = 30         # Auto-normalized to sum=1.0
education = 15
experience = 15
projects = 20
english = 10
cultural_fit = 10
```

## Fill Your Profile

Edit `~/Documents/applyr/cv-master.md` with your complete professional profile. This is the single source of truth — your AI agent reads it to score offers and generate CVs.

## Connect Your Agent

```bash
applyr setup-agent --agent claude    # or cursor, opencode, generic
```

This generates agent-specific instructions that tell the AI exactly how to use applyr.

## First Offer

Paste a job offer into your AI agent and say "analyze this". The agent will:
1. Check for duplicates
2. Score the offer against your profile
3. Run `applyr add '<json>'`
4. Recommend APPLY or SKIP

Or add manually:

```bash
applyr add '{"title":"Engineer","company":"Acme","tech_stack":"Python, FastAPI","compatibility_pct":75}'
```

## Verify Setup

```bash
applyr doctor      # Check configuration and database health
applyr list        # See your offers
applyr stats       # View conversion funnel
```
