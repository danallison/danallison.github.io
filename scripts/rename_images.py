#!/usr/bin/env python3
"""Rename date-only images to include incrementing suffix.

Renames files like YYYY-MM-DD.jpg to YYYY-MM-DD_1.jpg. If that name exists,
increments to _2, _3, etc. Useful for processing camera imports.

Usage:
    python rename_images.py --dir DIR

Arguments:
    --dir  Directory containing images to rename
"""

import argparse
import re
from pathlib import Path


def rename_images(directory: str) -> int:
    """Rename YYYY-MM-DD.jpg to YYYY-MM-DD_1.jpg (incrementing if exists)."""
    img_pattern = re.compile(
        r'^(?P<date>\d{4}-\d{2}-\d{2})(?:[ _](?P<time>\d{2}\.\d{2}\.\d{2}))?\.jpg$',
        re.IGNORECASE
    )

    directory = Path(directory)
    if not directory.exists():
        print(f"Directory {directory} does not exist.")
        return 0

    renamed = 0
    for img_path in directory.iterdir():
        if not img_path.is_file():
            continue
        m = img_pattern.match(img_path.name)
        if not m:
            continue

        date = m.group('date')
        name = 1
        new_name = f"{date}_{name}.jpg"
        new_path = directory / new_name

        while new_path.exists():
            name += 1
            new_name = f"{date}_{name}.jpg"
            new_path = directory / new_name

        img_path.rename(new_path)
        print(f"Renamed {img_path.name} → {new_name}")
        renamed += 1

    return renamed


def main():
    parser = argparse.ArgumentParser(description='Rename date-only images to include suffix')
    parser.add_argument('--dir', required=True, help='Directory containing images to rename')
    args = parser.parse_args()

    renamed = rename_images(args.dir)
    print(f"Renamed {renamed} images.")


if __name__ == '__main__':
    main()
