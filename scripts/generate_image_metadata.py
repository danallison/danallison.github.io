#!/usr/bin/env python3
"""Generate Jekyll markdown metadata files for images.

Creates .md files with YAML frontmatter for images matching the YYYY-MM-DD_name pattern.
Skips images that already have corresponding metadata files.

Usage:
    python generate_image_metadata.py --source DIR --dest DIR --layout NAME

Arguments:
    --source  Source directory containing images (e.g., drawings/)
    --dest    Destination directory for markdown files (e.g., _drawings/)
    --layout  Jekyll layout name to use in frontmatter (e.g., drawing)
"""

import argparse
import os
import re
from pathlib import Path


def generate_md_for_images(source_dir: str, dest_dir: str, layout: str) -> int:
    """Create markdown metadata files for images matching YYYY-MM-DD_name pattern."""
    img_pattern = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2})_(?P<name>.+)\.(?:jpg|png|gif)$',
        re.IGNORECASE
    )

    source_dir = Path(source_dir)
    if not source_dir.exists():
        print(f"Source directory {source_dir} does not exist.")
        return 0

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    for img_path in source_dir.iterdir():
        if not img_path.is_file():
            continue
        m = img_pattern.match(img_path.name)
        if not m:
            continue

        date = m.group('date')
        name = m.group('name')
        filename = img_path.name
        pagename = f"{date}_{name}"
        md_path = dest_dir / f"{pagename}.md"

        if md_path.exists():
            continue

        front_matter = f"""---
layout: {layout}
filename: {filename}
pagename: {pagename}
date: {date}
tags:
---
"""
        md_path.write_text(front_matter)
        print(f"Created {md_path}")
        created += 1

    return created


def main():
    parser = argparse.ArgumentParser(description='Generate Jekyll metadata files for images')
    parser.add_argument('--source', required=True, help='Source directory containing images (e.g., drawings/)')
    parser.add_argument('--dest', required=True, help='Destination directory for markdown files (e.g., _drawings/)')
    parser.add_argument('--layout', required=True, help='Jekyll layout to use (e.g., drawing)')
    args = parser.parse_args()

    created = generate_md_for_images(args.source, args.dest, args.layout)
    print(f"Created {created} new metadata files.")


if __name__ == '__main__':
    main()
