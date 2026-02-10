#!/usr/bin/env python3
"""Generate tag pages from Jekyll collection metadata.

Usage:
    python generate_tags.py [--config PATH] [--output DIR]

Arguments:
    --config  Path to Jekyll config file (default: _config.yml)
    --output  Output directory for tag pages (default: _tags/)
"""

import argparse
import glob
import os
import re
import yaml


def extract_tags(config_path: str) -> set:
    """Extract all tags from Jekyll collections."""
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)

    collections = set(cfg.get('collections', {}).keys())
    collections.add('posts')

    tags = set()
    for coll in collections:
        dir_name = '_posts' if coll == 'posts' else f"_{coll}"
        if not os.path.isdir(dir_name):
            continue
        for path in glob.glob(os.path.join(dir_name, '*.md')):
            with open(path, 'r') as f:
                content = f.read()
            fm = re.match(r'^---\s*(.*?)\s*---', content, re.DOTALL)
            if not fm:
                continue
            data = yaml.safe_load(fm.group(1))
            for t in data.get('tags', []) or []:
                if isinstance(t, str):
                    tags.add(t.strip())
    return tags


def generate_tag_pages(tags: set, output_dir: str) -> int:
    """Generate markdown files for each tag."""
    os.makedirs(output_dir, exist_ok=True)

    for tag in tags:
        slug = re.sub(r'[^\w-]', '', tag.lower().replace(' ', '-'))
        header = f"""---
layout: tag
tag: {tag}
title: {tag}
---"""
        with open(os.path.join(output_dir, f'{slug}.md'), 'w') as f:
            f.write(header + '\n')

    return len(tags)


def main():
    parser = argparse.ArgumentParser(description='Generate tag pages from Jekyll collections')
    parser.add_argument('--config', default='_config.yml', help='Path to Jekyll config (default: _config.yml)')
    parser.add_argument('--output', default='_tags/', help='Output directory for tag pages (default: _tags/)')
    args = parser.parse_args()

    tags = extract_tags(args.config)
    count = generate_tag_pages(tags, args.output)
    print(f"Generated {count} tag pages in '{args.output}' directory.")


if __name__ == '__main__':
    main()
