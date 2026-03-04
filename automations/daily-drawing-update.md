# Automation

## Task: Daily Drawing Update

The purpose of this automation task is to find the most recent drawing posted on Twitter by @danallison that has the text "You are loved. You are free. Goodnight.", download the image to the `drawings` directory with the correct filename and date following the `YYYY-MM-DD_title.jpg` format, running the `generate_image_metadata` and `convert_to_svg` scripts via cli.

---

## Spec

### Overview

A Python script that fetches "goodnight" drawing tweets since the last local drawing, downloads images, and runs the existing processing pipeline.

### Data Source: Community Archive

Uses the [Community Archive](https://github.com/TheExGenesis/community-archive) Supabase API, which provides free access to archived Twitter data.

- **API Base**: `https://fabxmporizzqflnftavs.supabase.co/rest/v1`
- **tweets table**: Query by `account_id=14213298`, filter by "You are loved" in `full_text`
- **tweet_media table**: Query by `tweet_id` to get image URLs
- No authentication required (uses public anon key)

### Workflow

1. **Scan local** - Find the most recent date in `drawings/` directory (parse `YYYY-MM-DD` from filenames)
2. **Fetch** - Query Community Archive API for all matching tweets since that date
3. **Filter** - Skip any tweets whose date already has an image in `drawings/`
4. **Download** - For each new tweet, save image to `drawings/YYYY-MM-DD_1.jpg`
5. **Generate metadata** - Run `./scripts/cli.py generate-metadata --source drawings/ --dest _drawings/ --layout drawing`
6. **Add tweet URLs** - Update each generated `.md` file's frontmatter with `tweet: https://x.com/danallison/status/{tweet_id}`
7. **Convert to SVG** - Run `./scripts/cli.py to-svg`
8. **Commit (optional)** - If `--commit` flag passed, commit changes with message "Add N drawings (YYYY-MM-DD to YYYY-MM-DD)"

Note: `substack_post` is added manually and not handled by this automation.

### CLI Interface

```bash
# Basic usage - fetch all new since last drawing date
./scripts/cli.py daily-drawing

# With auto-commit
./scripts/cli.py daily-drawing --commit

# Backfill from a specific date
./scripts/cli.py daily-drawing --since 2024-01-01

# Force re-download even if date exists locally
./scripts/cli.py daily-drawing --force
```

| Flag | Description |
|------|-------------|
| `--commit` | Commit changes after processing |
| `--since YYYY-MM-DD` | Override start date (ignore local drawings) |
| `--force` | Re-download even if date already exists locally |

### GitHub Action

```yaml
# .github/workflows/daily-drawing.yml
name: Daily Drawing Update
on:
  schedule:
    - cron: '0 12 * * *'  # Noon UTC daily
  workflow_dispatch: {}   # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install requests
          sudo apt-get update && sudo apt-get install -y imagemagick potrace
      - name: Configure git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
      - name: Fetch and process drawings
        run: ./scripts/cli.py daily-drawing --commit
      - name: Push changes
        run: git push || echo "Nothing to push"
```

### Error Handling

Fail fast with clear, actionable error messages. No automatic retries.

| Scenario | Behavior |
|----------|----------|
| API request fails | Exit: "Error: Failed to fetch tweets: {status} {text}" |
| No new tweets found | Print: "No new drawings since YYYY-MM-DD" |
| Empty drawings directory | Fetch last 30 days of matching tweets |
| Image download fails | Exit: "Error: Failed to download image from {url}" |
| SVG conversion fails | Log warning, continue (images still usable) |

### Dependencies

- `requests` - HTTP client for API and image download
- Existing: `imagemagick`, `potrace` (for SVG conversion)

---

## Setup

### Local Setup

```bash
# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install requests

# Run
./scripts/cli.py daily-drawing
```

No API keys required - uses the public Community Archive API.

Note: `.venv/` is gitignored.

### Files

| File | Description |
|------|-------------|
| `scripts/daily_drawing.py` | Core logic for fetching and processing |
| `scripts/cli.py` | CLI with `daily-drawing` subcommand |
| `.github/workflows/daily-drawing.yml` | GitHub Action for daily automation |