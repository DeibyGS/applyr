# CLI Reference

All commands support `--json` (structured output) and `--no-color` (plain text).

## Tracking

### `applyr init`

Set up `~/.applyr/` with config, database, and templates.

```bash
applyr init
```

### `applyr setup-agent [--agent NAME]`

Generate agent-specific instructions.

```bash
applyr setup-agent                # Auto-detect
applyr setup-agent --agent claude # Specify: claude | cursor | opencode | generic
```

### `applyr add '<json>'`

Register a new job offer. JSON can be passed as argument, file path, or stdin.

```bash
applyr add '{"title":"Engineer","company":"Acme"}'
applyr add offer.json
cat offer.json | applyr add -
```

**Required fields:** `title`

**Optional fields:** `company`, `summary`, `date_received`, `date_applied`, `compatibility_pct`, `status`, `canal`, `work_mode`, `location`, `salary_min`, `salary_max`, `salary_period`, `seniority_level`, `role_category`, `tech_stack`, `language`, `cover_letter`, `job_url`, `contact_name`, `contact_role`, `topics`, `notes`

### `applyr list [--status S] [--sort F] [--limit N] [--all]`

List offers. Default: last 50.

```bash
applyr list                          # Last 50
applyr list --status applied         # Filter by status
applyr list --sort compatibility_pct # Sort by score
applyr list --all                    # All offers
applyr list --json                   # JSON output
```

### `applyr show <id>`

Show full offer details including per-topic scores.

```bash
applyr show 1
applyr show 1 --json
```

### `applyr update <id> <status> [--notes '...'] [--canal '...'] [--cv file.html]`

Update offer status. Valid statuses: `pending`, `applied`, `waiting`, `in_process`, `offer`, `rejected`, `discarded`.

`--cv` records which CV was sent, feeding `applyr cv stats`. `cv generate` sets it
automatically; use the flag for offers applied through some other route. Passing an
empty value clears the link.

```bash
applyr update 1 applied
applyr update 1 waiting --notes "Phone screen scheduled"
applyr update 1 applied --cv cv-acme.html
applyr update 1 applied --cv ""          # unlink the CV
```

### `applyr doctor [--json]`

Check configuration, database, CV master, agent instructions, Chrome and scoring
weights. **Exits `1` when a blocking issue is found**, so it can gate a pipeline:

```bash
applyr doctor && applyr cv generate 3
applyr doctor --json    # {"healthy": bool, "issues": int, "checks": [...]}
```

A missing Chrome is reported but does not block — it only stops `cv pdf`.

### `applyr delete <id>`

Remove an offer.

```bash
applyr delete 1
```

### `applyr search <keyword> [--status S]`

Search by company, title, notes, or tech stack.

```bash
applyr search "Python"
applyr search "Acme" --status applied
```

## Analytics

### `applyr pipeline [--min-score N]`

View offers grouped by status.

```bash
applyr pipeline
applyr pipeline --min-score 70
```

### `applyr stats`

Conversion funnel and key metrics.

```bash
applyr stats
applyr stats --json
```

### `applyr gaps [--limit N]`

Skill gap analysis — shows topics that appear in offers but score low.

```bash
applyr gaps
applyr gaps --limit 5
```

### `applyr followups`

Pending and overdue follow-ups.

```bash
applyr followups
applyr followups --json
```

### `applyr trends [--period week|month]`

Application trends over time.

```bash
applyr trends --period week
applyr trends --period month
```

### `applyr summary`

Weekly summary optimized for LLM consumption.

```bash
applyr summary
applyr summary --json
```

### `applyr compare <id1> <id2> [idN...]`

Side-by-side comparison (2-10 offers).

```bash
applyr compare 1 3
applyr compare 1 3 5 7
```

### `applyr plan [--limit N]`

Prioritized learning plan from skill gaps.

```bash
applyr plan
applyr plan --limit 5
```

### `applyr salary [--seniority S] [--category C]`

Salary insights by seniority and category.

```bash
applyr salary
applyr salary --seniority senior
applyr salary --category engineering
```

## CV Pipeline

### `applyr cv generate <id> [--template ats]`

Generate markdown CV from your profile with YAML frontmatter.

```bash
applyr cv generate 1
applyr cv generate 1 --template ats
```

Output: `.md` file (not `.html`). The `cv_used` field stores basename without extension.

### `applyr cv review <file>`

Generate recruiter review prompt with ATS scoring rubric. Accepts `.md` or `.html` files.

```bash
applyr cv review cv.md
applyr cv review cv.md --json
applyr cv review cv.html  # Legacy HTML files still work
```

### `applyr cv pdf <file> [--output file.pdf]`

Convert CV to PDF via Chrome headless. Accepts `.md` or `.html` files.

For `.md` files: renders markdown → ATS-safe HTML → PDF in one invocation.
For `.html` files: renders directly to PDF (legacy support).

```bash
applyr cv pdf cv.md
applyr cv pdf cv.md --output my_cv.pdf
applyr cv pdf cv.html  # Legacy HTML files still work
```

## System

### `applyr doctor`

Check configuration and database health.

```bash
applyr doctor
```

### `applyr export [--format csv|json|md] [--file path]`

Export all data.

```bash
applyr export --format csv
applyr export --format json
applyr export --format md --file export.md
```

### `applyr version`

Show version.

```bash
applyr version
```

## Aliases

| Alias | Command |
|-------|---------|
| `ls` | `list` |
| `st` | `stats` |
| `fu` | `followups` |
| `cmp` | `compare` |
| `sal` | `salary` |

## Global Flags

| Flag | Effect |
|------|--------|
| `--json` | Structured JSON output |
| `--no-color` | Disable colors (also respects `NO_COLOR` env var) |
