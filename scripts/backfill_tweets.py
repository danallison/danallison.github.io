#!/usr/bin/env python3
"""Backfill tweet URLs for drawing pages that don't have them.

Fetches all goodnight tweets from the Community Archive, downloads their
images, and matches them to local drawing files using image comparison.
"""

import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Error: requests not installed. Run: pip install requests")

from daily_drawing import (
    ACCOUNT_ID,
    DRAWINGS_DIR,
    METADATA_DIR,
    SEARCH_PHRASE,
    fetch_account_tweets,
    first_photo_url,
    update_frontmatter_with_tweet,
)

# How many days before/after the drawing date to search for matching tweets
SEARCH_WINDOW_DAYS = 2
# RMSE threshold for considering two images a match
RMSE_THRESHOLD = 0.15


# Photo URL for each goodnight tweet, filled by fetch_all_goodnight_tweets().
_PHOTO_URLS: dict[str, str] = {}


def fetch_all_goodnight_tweets() -> list[dict]:
    """Fetch all goodnight tweets from the Community Archive, oldest first."""
    print("Fetching all tweets from Community Archive (this walks the full history)...")
    all_tweets = [
        t for t in fetch_account_tweets(datetime(2006, 3, 1))
        if SEARCH_PHRASE.lower() in (t.get("full_text") or "").lower()
    ]
    for t in all_tweets:
        url = first_photo_url(t)
        if url:
            _PHOTO_URLS[str(t["tweet_id"])] = url
    print(f"  Got {len(all_tweets)} goodnight tweets")
    return all_tweets


def build_date_to_tweets(tweets: list[dict]) -> dict[str, list[str]]:
    """Group tweet IDs by date, ordered chronologically."""
    date_map: dict[str, list[str]] = defaultdict(list)

    for tweet in tweets:
        tweet_id = tweet.get("tweet_id")
        created_at = tweet.get("created_at", "")
        if not tweet_id or not created_at:
            continue

        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue

        date_map[date_str].append(str(tweet_id))

    return dict(date_map)


def find_drawings_without_tweets(metadata_dir: Path) -> list[Path]:
    """Find drawing .md files without a tweet attribute."""
    results = []
    for md_path in sorted(metadata_dir.glob("*.md")):
        content = md_path.read_text()
        if "tweet:" not in content:
            results.append(md_path)
    return results


def fetch_all_media_urls(date_to_tweets: dict[str, list[str]]) -> dict[str, str]:
    """Return photo URLs for the given tweets (media comes with each tweet in API v1)."""
    wanted = {tid for tids in date_to_tweets.values() for tid in tids}
    return {tid: url for tid, url in _PHOTO_URLS.items() if tid in wanted}


def compare_images(local_path: Path, remote_url: str) -> float | None:
    """Compare local image with remote image using ImageMagick RMSE.

    Returns normalized RMSE (0.0 = identical), or None on error.
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
        resp = requests.get(remote_url, timeout=30)
        if resp.status_code != 200:
            os.unlink(tmp_path)
            return None
        tmp.write(resp.content)

    try:
        result = subprocess.run(
            ["magick", "compare", "-metric", "RMSE",
             "-resize", "256x256!",
             str(local_path), tmp_path, "/dev/null"],
            capture_output=True, text=True,
        )
        match = re.search(r"\(([\d.]+)\)", result.stderr.strip())
        return float(match.group(1)) if match else None
    finally:
        os.unlink(tmp_path)


def backfill_tweets(dry_run: bool = False):
    """Main backfill function. Matches drawings to tweets by image comparison."""
    print("Fetching all goodnight tweets from Community Archive...")
    tweets = fetch_all_goodnight_tweets()
    print(f"Total goodnight tweets found: {len(tweets)}")

    date_to_tweets = build_date_to_tweets(tweets)
    print(f"Tweets span {len(date_to_tweets)} unique dates")

    print("Fetching media URLs...")
    tweet_media = fetch_all_media_urls(date_to_tweets)
    print(f"Got media URLs for {len(tweet_media)} tweets")

    drawings = find_drawings_without_tweets(METADATA_DIR)
    print(f"Drawings without tweet URLs: {len(drawings)}")

    date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
    updated = 0
    no_match = 0
    no_image = 0

    for md_path in drawings:
        m = date_pattern.match(md_path.stem)
        if not m:
            continue

        date_str = m.group(1)
        img_path = DRAWINGS_DIR / (md_path.stem + ".jpg")
        if not img_path.exists():
            print(f"  {md_path.name}: image file not found")
            no_image += 1
            continue

        # Gather candidate tweets from ±SEARCH_WINDOW_DAYS
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        candidates = []
        for offset in range(-SEARCH_WINDOW_DAYS, SEARCH_WINDOW_DAYS + 1):
            adj = (dt + timedelta(days=offset)).strftime("%Y-%m-%d")
            for tid in date_to_tweets.get(adj, []):
                if tid in tweet_media:
                    candidates.append((tid, tweet_media[tid]))

        if not candidates:
            print(f"  {md_path.name}: no candidate tweets within ±{SEARCH_WINDOW_DAYS} days")
            no_match += 1
            continue

        # Compare against all candidates, pick best match
        best_tid = None
        best_rmse = float("inf")

        for tid, media_url in candidates:
            rmse = compare_images(img_path, media_url)
            if rmse is not None and rmse < best_rmse:
                best_tid = tid
                best_rmse = rmse

        if best_tid and best_rmse < RMSE_THRESHOLD:
            tweet_url = f"https://x.com/danallison/status/{best_tid}"
            if dry_run:
                print(f"  [dry-run] {md_path.name} -> {tweet_url} (RMSE: {best_rmse:.4f})")
            else:
                update_frontmatter_with_tweet(md_path, tweet_url)
                print(f"  {md_path.name} -> {tweet_url} (RMSE: {best_rmse:.4f})")
            updated += 1
        else:
            print(f"  {md_path.name}: no match (best RMSE: {best_rmse:.4f})")
            no_match += 1

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  No match: {no_match}")
    print(f"  No image file: {no_image}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill tweet URLs for drawing pages")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    backfill_tweets(dry_run=args.dry_run)
