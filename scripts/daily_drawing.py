#!/usr/bin/env python3
"""Fetch goodnight drawings from the Community Archive and process them.

Finds tweets by @danallison containing "You are loved. You are free. Goodnight."
with images, downloads them, and runs the metadata/SVG pipeline.

Uses the Community Archive API v1 (https://github.com/TheExGenesis/community-archive),
which needs a personal key in the CA_API_KEY environment variable.
"""

import os
import re
import time
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Error: requests not installed. Run: pip install requests")

# Community Archive API v1 (https://analytics.community-archive.org/v1).
# Needs a personal key in the CA_API_KEY environment variable
# (create one at https://www.community-archive.org/settings/api-keys).
# The old public Supabase API was retired on 2026-11-19.
CA_API_URL = "https://analytics.community-archive.org/v1"
ACCOUNT_ID = "14213298"  # @danallison's Twitter account ID
SEARCH_PHRASE = "You are loved"
DRAWINGS_DIR = Path("drawings")
METADATA_DIR = Path("_drawings")


def get_latest_local_date(drawings_dir: Path) -> datetime | None:
    """Find the most recent date from filenames in drawings directory."""
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})_')
    dates = []

    if not drawings_dir.exists():
        return None

    for f in drawings_dir.iterdir():
        if f.is_file():
            m = date_pattern.match(f.name)
            if m:
                try:
                    dates.append(datetime.strptime(m.group(1), "%Y-%m-%d"))
                except ValueError:
                    continue

    return max(dates) if dates else None


def get_local_date_counts(drawings_dir: Path) -> dict[str, int]:
    """Get count of images for each date that exists locally."""
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})_')
    counts: dict[str, int] = {}

    if not drawings_dir.exists():
        return counts

    for f in drawings_dir.iterdir():
        if f.is_file():
            m = date_pattern.match(f.name)
            if m:
                date_str = m.group(1)
                counts[date_str] = counts.get(date_str, 0) + 1

    return counts


def ca_headers():
    """Get headers for Community Archive API requests."""
    key = os.environ.get("CA_API_KEY")
    if not key:
        sys.exit("Error: CA_API_KEY is not set (Community Archive API key)")
    return {"Authorization": f"Bearer {key}"}


def ca_get(path: str, params: dict) -> dict:
    """GET a Community Archive API path, retrying on rate limits."""
    for _ in range(10):
        response = requests.get(f"{CA_API_URL}{path}", headers=ca_headers(),
                                params=params, timeout=60)
        if response.status_code in (429, 503):
            time.sleep(int(response.headers.get("Retry-After", "5")))
            continue
        if response.status_code != 200:
            sys.exit(f"Error: Failed to fetch {path}: {response.status_code} {response.text}")
        return response.json()
    sys.exit(f"Error: Gave up on {path} after repeated rate limiting")


def fetch_account_tweets(since_date: datetime, until_date: datetime | None = None) -> list[dict]:
    """Fetch all of the account's original tweets since a date, oldest first.

    Walks 30-day windows so long ranges stay within the API's query budget.
    """
    until_date = until_date or (datetime.utcnow() + timedelta(days=1))
    tweets = []
    win_start = since_date
    while win_start < until_date:
        win_end = min(win_start + timedelta(days=30), until_date)
        cursor = None
        while True:
            params = {
                "order": "asc",
                "limit": "200",
                "exclude_retweets": "true",
                "since": win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "until": win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if cursor:
                params["cursor"] = cursor
            page = ca_get(f"/accounts/{ACCOUNT_ID}/tweets", params)
            tweets.extend(page.get("data") or [])
            cursor = page.get("next_cursor")
            if cursor is None:
                break
        win_start = win_end
    return tweets


def first_photo_url(tweet: dict) -> str | None:
    """Return the first photo URL attached to a tweet, if any."""
    for m in tweet.get("media") or []:
        if m.get("media_type", "photo") == "photo" and m.get("media_url"):
            return m["media_url"]
    return None


def fetch_goodnight_tweets(since_date: datetime) -> list[dict]:
    """Fetch goodnight drawing tweets (with photos) since a date, newest first."""
    print("Fetching tweets from Community Archive...")
    tweets = [
        t for t in fetch_account_tweets(since_date)
        if SEARCH_PHRASE.lower() in (t.get("full_text") or "").lower()
    ]
    print(f"Found {len(tweets)} goodnight tweets since {since_date.strftime('%Y-%m-%d')}")

    results = []
    for tweet in sorted(tweets, key=lambda t: t["created_at"], reverse=True):
        image_url = first_photo_url(tweet)
        if tweet.get("tweet_id") and image_url:
            results.append({
                "id": str(tweet["tweet_id"]),
                "created_at": tweet.get("created_at"),
                "image_url": image_url,
            })
    return results


def download_image(url: str, dest_path: Path):
    """Download image from URL to destination path."""
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        sys.exit(f"Error: Failed to download image from {url}")
    dest_path.write_bytes(response.content)


def update_frontmatter_with_tweet(md_path: Path, tweet_url: str):
    """Add tweet URL to markdown frontmatter."""
    content = md_path.read_text()

    # Insert tweet URL after date line
    if "tweet:" not in content:
        content = content.replace(
            "tags:",
            f"tweet: {tweet_url}\ntags:"
        )
        md_path.write_text(content)


def run_pipeline():
    """Run generate-metadata and to-svg commands."""
    scripts_dir = Path(__file__).parent
    cli_path = scripts_dir / "cli.py"

    # Generate metadata
    subprocess.run([
        sys.executable, str(cli_path),
        "generate-metadata",
        "--source", str(DRAWINGS_DIR),
        "--dest", str(METADATA_DIR),
        "--layout", "drawing"
    ], check=True)

    # Convert to SVG (may fail if tools not installed, that's OK)
    result = subprocess.run([
        sys.executable, str(cli_path),
        "to-svg"
    ])
    if result.returncode != 0:
        print("Warning: SVG conversion failed (imagemagick/potrace may not be installed)")


def git_commit(pagenames: list[str]):
    """Commit changes with descriptive message."""
    if len(pagenames) == 1:
        msg = f"Add drawing {pagenames[0]}"
    else:
        # Extract dates for range display
        dates = sorted(set(p.rsplit("_", 1)[0] for p in pagenames))
        if len(dates) == 1:
            msg = f"Add {len(pagenames)} drawings ({dates[0]})"
        else:
            msg = f"Add {len(pagenames)} drawings ({dates[0]} to {dates[-1]})"

    subprocess.run(["git", "add", str(DRAWINGS_DIR), str(METADATA_DIR), "svgs/"], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)


def daily_drawing(since: str | None = None, force: bool = False, commit: bool = False):
    """Main function to fetch and process drawings."""
    DRAWINGS_DIR.mkdir(exist_ok=True)

    # Determine start date
    if since:
        start_date = datetime.strptime(since, "%Y-%m-%d")
    else:
        latest = get_latest_local_date(DRAWINGS_DIR)
        if latest:
            start_date = latest
        else:
            # Default to 30 days ago if no drawings exist
            start_date = datetime.now() - timedelta(days=30)

    print(f"Looking for tweets since {start_date.strftime('%Y-%m-%d')}...")

    # Get existing date counts (how many images per date)
    date_counts = get_local_date_counts(DRAWINGS_DIR) if not force else {}
    existing_dates = set(date_counts.keys())  # Snapshot of dates to skip

    # Fetch tweets with media
    tweets = fetch_goodnight_tweets(start_date)

    if not tweets:
        print(f"No new drawings since {start_date.strftime('%Y-%m-%d')}")
        return

    # Process each tweet (oldest first so suffixes are chronological)
    downloaded_files = []
    tweet_info = {}  # pagename -> tweet_id mapping

    for tweet in reversed(tweets):
        # Parse tweet date
        created_at = tweet.get("created_at", "")
        try:
            tweet_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = tweet_date.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        # Skip dates that already have images locally (unless --force)
        if date_str in existing_dates:
            print(f"Skipping {date_str} (already exists)")
            continue

        # Determine next available suffix for this date (handles multiple tweets same day)
        current_count = date_counts.get(date_str, 0)
        suffix = current_count + 1
        pagename = f"{date_str}_{suffix}"
        filename = f"{pagename}.jpg"
        dest_path = DRAWINGS_DIR / filename

        print(f"Downloading {filename}...")
        download_image(tweet["image_url"], dest_path)

        downloaded_files.append(pagename)
        tweet_info[pagename] = tweet["id"]
        date_counts[date_str] = suffix  # Track for next image on same date

    if not downloaded_files:
        print("No new drawings to download")
        return

    print(f"Downloaded {len(downloaded_files)} new drawings")

    # Run pipeline
    print("Generating metadata...")
    run_pipeline()

    # Update frontmatter with tweet URLs
    print("Adding tweet URLs to metadata...")
    for pagename, tweet_id in tweet_info.items():
        md_path = METADATA_DIR / f"{pagename}.md"
        if md_path.exists():
            tweet_url = f"https://x.com/danallison/status/{tweet_id}"
            update_frontmatter_with_tweet(md_path, tweet_url)
            print(f"Updated {md_path.name}")

    # Commit if requested
    if commit:
        print("Committing changes...")
        git_commit(downloaded_files)

    print("Done!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch goodnight drawings from Community Archive")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Re-download even if exists")
    parser.add_argument("--commit", action="store_true", help="Commit changes")
    args = parser.parse_args()

    daily_drawing(since=args.since, force=args.force, commit=args.commit)
