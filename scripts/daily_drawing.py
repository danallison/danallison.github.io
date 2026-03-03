#!/usr/bin/env python3
"""Fetch goodnight drawings from the Community Archive and process them.

Finds tweets by @danallison containing "You are loved. You are free. Goodnight."
with images, downloads them, and runs the metadata/SVG pipeline.

Uses the Community Archive Supabase API (https://github.com/TheExGenesis/community-archive)
which provides free access to archived Twitter data.
"""

import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Error: requests not installed. Run: pip install requests")

# Community Archive Supabase API
# Public anon key from https://github.com/TheExGenesis/community-archive/blob/main/docs/api-doc.md
# This key is intentionally public and provides read-only access to archived Twitter data.
SUPABASE_URL = "https://fabxmporizzqflnftavs.supabase.co/rest/v1"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZhYnhtcG9yaXp6cWZsbmZ0YXZzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjIyNDQ5MTIsImV4cCI6MjAzNzgyMDkxMn0.UIEJiUNkLsW28tBHmG-RQDW-I5JNlJLt62CSk9D_qG8"
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


def get_local_dates(drawings_dir: Path) -> set[str]:
    """Get set of all dates that already have images locally."""
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})_')
    dates = set()

    if not drawings_dir.exists():
        return dates

    for f in drawings_dir.iterdir():
        if f.is_file():
            m = date_pattern.match(f.name)
            if m:
                dates.add(m.group(1))

    return dates


def supabase_headers():
    """Get headers for Supabase API requests."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def fetch_goodnight_tweets(since_date: datetime) -> list[dict]:
    """Fetch goodnight tweets from Community Archive Supabase API."""
    print("Fetching tweets from Community Archive...")

    # Format date for Supabase query
    since_str = since_date.strftime("%Y-%m-%dT00:00:00+00:00")

    # Query tweets table
    params = {
        "account_id": f"eq.{ACCOUNT_ID}",
        "created_at": f"gte.{since_str}",
        "full_text": f"ilike.*{SEARCH_PHRASE}*",
        "order": "created_at.desc",
        "limit": "100",
    }

    response = requests.get(
        f"{SUPABASE_URL}/tweets",
        headers=supabase_headers(),
        params=params,
        timeout=30,
    )

    if response.status_code != 200:
        sys.exit(f"Error: Failed to fetch tweets: {response.status_code} {response.text}")

    tweets = response.json()
    print(f"Found {len(tweets)} goodnight tweets since {since_date.strftime('%Y-%m-%d')}")

    # Fetch media for each tweet
    results = []
    for tweet in tweets:
        tweet_id = tweet.get("tweet_id")
        if not tweet_id:
            continue

        # Query tweet_media table for this tweet
        media_response = requests.get(
            f"{SUPABASE_URL}/tweet_media",
            headers=supabase_headers(),
            params={"tweet_id": f"eq.{tweet_id}", "media_type": "eq.photo", "limit": "1"},
            timeout=30,
        )

        if media_response.status_code == 200:
            media_list = media_response.json()
            if media_list:
                media_url = media_list[0].get("media_url")
                if media_url:
                    results.append({
                        "id": str(tweet_id),
                        "created_at": tweet.get("created_at"),
                        "image_url": media_url,
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


def git_commit(dates: list[str]):
    """Commit changes with descriptive message."""
    if len(dates) == 1:
        msg = f"Add drawing {dates[0]}"
    else:
        msg = f"Add {len(dates)} drawings ({min(dates)} to {max(dates)})"

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

    # Get existing dates to skip
    existing_dates = get_local_dates(DRAWINGS_DIR) if not force else set()

    # Fetch tweets with media
    tweets = fetch_goodnight_tweets(start_date)

    if not tweets:
        print(f"No new drawings since {start_date.strftime('%Y-%m-%d')}")
        return

    # Process each tweet
    downloaded_dates = []
    tweet_info = {}  # date -> tweet_id mapping

    for tweet in tweets:
        # Parse tweet date
        created_at = tweet.get("created_at", "")
        try:
            tweet_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = tweet_date.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        if date_str in existing_dates:
            print(f"Skipping {date_str} (already exists)")
            continue

        # Download image
        filename = f"{date_str}_1.jpg"
        dest_path = DRAWINGS_DIR / filename

        print(f"Downloading {filename}...")
        download_image(tweet["image_url"], dest_path)

        downloaded_dates.append(date_str)
        tweet_info[date_str] = tweet["id"]
        existing_dates.add(date_str)  # Prevent duplicates within same run

    if not downloaded_dates:
        print("No new drawings to download")
        return

    print(f"Downloaded {len(downloaded_dates)} new drawings")

    # Run pipeline
    print("Generating metadata...")
    run_pipeline()

    # Update frontmatter with tweet URLs
    print("Adding tweet URLs to metadata...")
    for date_str, tweet_id in tweet_info.items():
        md_path = METADATA_DIR / f"{date_str}_1.md"
        if md_path.exists():
            tweet_url = f"https://x.com/danallison/status/{tweet_id}"
            update_frontmatter_with_tweet(md_path, tweet_url)
            print(f"Updated {md_path.name}")

    # Commit if requested
    if commit:
        print("Committing changes...")
        git_commit(downloaded_dates)

    print("Done!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch goodnight drawings from Community Archive")
    parser.add_argument("--since", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--force", action="store_true", help="Re-download even if exists")
    parser.add_argument("--commit", action="store_true", help="Commit changes")
    args = parser.parse_args()

    daily_drawing(since=args.since, force=args.force, commit=args.commit)
