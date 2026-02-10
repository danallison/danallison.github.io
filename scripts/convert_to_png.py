#!/usr/bin/env python3
"""Batch convert SVG files to high-DPI PNG using ImageMagick.

Requirements:
    macOS:    brew install imagemagick
    Ubuntu:   sudo apt-get install imagemagick
    Windows:  winget install ImageMagick.ImageMagick

Usage:
    python convert_to_png.py [FILES...] [--input DIR] [--output DIR] [options]

Arguments:
    FILES        Specific SVG files to convert (optional)
    --input      Input directory containing SVGs (default: svgs, ignored if FILES provided)
    --output     Output directory for PNGs (default: pngs-for-book)
    --dpi        DPI resolution for output (default: 300)
    --overwrite  Overwrite existing PNG files (default: skip existing)
    --jobs       Number of parallel workers (default: CPU count)
"""

import argparse
import concurrent.futures
import os
import subprocess
from pathlib import Path


def find_magick() -> str:
    """Find ImageMagick binary."""
    for candidate in ['magick', 'convert']:
        try:
            subprocess.run([candidate, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return candidate
        except Exception:
            continue
    raise RuntimeError("ImageMagick not found. Install it and ensure 'magick' or 'convert' is on PATH.")


def convert_one(svg: Path, output_dir: Path, dpi: int, overwrite: bool) -> str:
    """Convert a single SVG to PNG."""
    png = output_dir / (svg.stem + '.png')
    if png.exists() and not overwrite:
        return f"skip  {svg.name}"

    magick = find_magick()
    cmd = [
        magick, str(svg),
        '-density', str(dpi),
        '-background', 'white',
        '-flatten',
        '-units', 'PixelsPerInch',
        str(png)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return f"done  {svg.name} → {png.name}"


def main():
    parser = argparse.ArgumentParser(description='Batch convert SVG to PNG')
    parser.add_argument('files', nargs='*', help='Specific SVG files to convert (optional)')
    parser.add_argument('--input', default='svgs', help='Input directory (default: svgs, ignored if files provided)')
    parser.add_argument('--output', default='pngs-for-book', help='Output directory (default: pngs-for-book)')
    parser.add_argument('--dpi', type=int, default=300, help='DPI resolution (default: 300)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing PNGs')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4, help='Parallel jobs')
    args = parser.parse_args()

    find_magick()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use provided files or discover from input directory
    if args.files:
        svgs = [Path(f) for f in args.files]
        # Validate files exist and are SVGs
        for f in svgs:
            if not f.exists():
                print(f"Error: File not found: {f}")
                return
            if f.suffix.lower() != '.svg':
                print(f"Error: Not an SVG file: {f}")
                return
    else:
        input_dir = Path(args.input)
        svgs = list(input_dir.rglob('*.svg'))

    if not svgs:
        print("No SVGs found.")
        return

    print(f"Converting {len(svgs)} SVGs to PNG at {args.dpi} DPI using {args.jobs} workers.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {ex.submit(convert_one, svg, output_dir, args.dpi, args.overwrite): svg for svg in svgs}
        for fut in concurrent.futures.as_completed(futures):
            try:
                print(fut.result())
            except Exception as e:
                print(f"FAIL  {futures[fut].name}: {e}")


if __name__ == '__main__':
    main()
