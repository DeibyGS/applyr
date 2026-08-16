# Troubleshooting

## Common Errors

### "could not initialize database: ... Try running: applyr init"

The database doesn't exist yet. Run:

```bash
applyr init
```

### "Error: ID must be an integer"

You passed a non-numeric ID. IDs are integers:

```bash
applyr show 1      # correct
applyr show abc    # wrong
```

### "Error: period must be 'week' or 'month'"

```bash
applyr trends --period week   # correct
applyr trends --period daily  # wrong
```

### "Error: format must be 'csv', 'json', or 'md'"

```bash
applyr export --format json   # correct
applyr export --format xml    # wrong
```

### "Error: Chrome/Chromium not found"

applyr needs Chrome for PDF generation. Options:

1. Install Google Chrome
2. Set the path explicitly in `~/.applyr/applyr.toml`:
   ```toml
   [cv]
   chrome_path = "/usr/bin/chromium-browser"
   ```
3. Set the environment variable:
   ```bash
   export CHROME_BIN=/usr/bin/chromium-browser
   ```

### "Warning: could not parse applyr.toml: ..."

Your TOML file has a syntax error. Check it:

```bash
python -c "import tomllib; tomllib.load(open('$HOME/.applyr/applyr.toml', 'rb'))"
```

Or delete it and reinitialize:

```bash
rm ~/.applyr/applyr.toml
applyr init
```

### "Error: company+title already exists"

Duplicate detection caught a match. Check existing offers:

```bash
applyr search "Company Name"
applyr show <id>
```

To force-add anyway, use a slightly different title or company name.

### "Error: cv-master.md is too small (<100 chars)"

Your profile is empty or too short. Edit `~/Documents/applyr/cv-master.md` with your complete professional profile.

## Health Check

Run `applyr doctor` to diagnose common issues:

```bash
applyr doctor
```

This checks:
- Database exists and is accessible
- Config file is valid TOML
- cv-master.md exists and is large enough
- Chrome is available for PDF generation

## Getting More Help

- **GitHub Issues:** https://github.com/DeibyGS/applyr/issues
- **Run with --json:** Most commands support `--json` for structured output
- **Check the log:** If something fails silently, try `--json` to see the raw response
