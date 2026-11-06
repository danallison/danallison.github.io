#!/usr/bin/env python3
"""Batch convert SVG files to high-DPI PNG using ImageMagick.

Requirements:
    macOS:    brew install imagemagick
    Ubuntu:   sudo apt-get install imagemagick
    Windows:  winget install ImageMagick.ImageMagick

Each SVG is rendered (not upscaled) so that it fits inside the page size at the
given DPI, preserving aspect ratio. With the A5 defaults at 300 DPI, every PNG
fits within 1749x2481 px.

Usage:
    python convert_to_png.py [FILES...] [--input DIR] [--output DIR] [options]

Arguments:
    FILES          Specific SVG files to convert (optional)
    --input        Input directory containing SVGs (default: svgs, ignored if FILES provided)
    --output       Output directory for PNGs (default: pngs-for-book)
    --dpi          DPI resolution for output (default: 300)
    --page-width   Max printed width in inches (default: 5.83, A5)
    --page-height  Max printed height in inches (default: 8.27, A5)
    --overwrite    Overwrite existing PNG files (default: skip existing)
    --jobs         Number of parallel workers (default: CPU count)
"""

import argparse
import concurrent.futures
import os
import re
import subprocess
from pathlib import Path

A5_WIDTH_IN = 5.83
A5_HEIGHT_IN = 8.27


def find_magick() -> str:
    """Find ImageMagick binary."""
    for candidate in ['magick', 'convert']:
        try:
            subprocess.run([candidate, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return candidate
        except Exception:
            continue
    raise RuntimeError("ImageMagick not found. Install it and ensure 'magick' or 'convert' is on PATH.")


def svg_size(svg: Path) -> tuple:
    """Return the SVG's (width, height) in its own units (pt for potrace output)."""
    header = svg.read_text(errors='ignore')[:2000]
    w = re.search(r'<svg[^>]*\swidth="([\d.]+)', header)
    h = re.search(r'<svg[^>]*\sheight="([\d.]+)', header)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', header)
    if vb:
        return float(vb.group(1)), float(vb.group(2))
    raise ValueError(f"Could not determine size of {svg}")


def convert_one(svg: Path, output_dir: Path, dpi: int, overwrite: bool,
                page_width: float = A5_WIDTH_IN, page_height: float = A5_HEIGHT_IN) -> str:
    """Convert a single SVG to a PNG that fits the page at the given DPI."""
    png = output_dir / (svg.stem + '.png')
    if png.exists() and not overwrite:
        return f"skip  {svg.name}"

    max_w = round(page_width * dpi)
    max_h = round(page_height * dpi)
    w, h = svg_size(svg)
    # ImageMagick renders 1 SVG unit as 1 px at density 72; pick the density
    # that makes the drawing fill the page box, then resize to fit exactly.
    density = 72 * min(max_w / w, max_h / h)

    magick = find_magick()
    cmd = [
        magick,
        '-density', f'{density:.4f}',
        str(svg),
        '-background', 'white',
        '-flatten',
        '-resize', f'{max_w}x{max_h}',
        '-units', 'PixelsPerInch',
        '-density', str(dpi),
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
    parser.add_argument('--page-width', type=float, default=A5_WIDTH_IN, help=f'Max printed width in inches (default: {A5_WIDTH_IN}, A5)')
    parser.add_argument('--page-height', type=float, default=A5_HEIGHT_IN, help=f'Max printed height in inches (default: {A5_HEIGHT_IN}, A5)')
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

    print(f"Converting {len(svgs)} SVGs to PNG at {args.dpi} DPI, fit to {args.page_width}x{args.page_height} in, using {args.jobs} workers.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {ex.submit(convert_one, svg, output_dir, args.dpi, args.overwrite,
                             args.page_width, args.page_height): svg for svg in svgs}
        for fut in concurrent.futures.as_completed(futures):
            try:
                print(fut.result())
            except Exception as e:
                print(f"FAIL  {futures[fut].name}: {e}")


if __name__ == '__main__':
    main()
