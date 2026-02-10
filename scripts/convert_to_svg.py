#!/usr/bin/env python3
"""Batch convert JPG/PNG images to SVG using ImageMagick and Potrace.

Requirements:
    macOS:    brew install imagemagick potrace
    Ubuntu:   sudo apt-get install imagemagick potrace
    Windows:  winget install ImageMagick.ImageMagick potrace.potrace

Usage:
    python convert_to_svg.py [FILES...] [--input DIR] [--output DIR] [options]

Arguments:
    FILES        Specific image files to convert (optional)
    --input      Input directory containing images (default: drawings, ignored if FILES provided)
    --output     Output directory for SVGs (default: svgs)
    --threshold  Black/white threshold 0-100; raise to clean paper, lower if
                 lines break (default: 88)
    --turdsize   Potrace speckle filter size in pixels (default: 2)
    --alphamax   Curve smoothness; use 0.6-0.8 for crisper corners (default: 1.0)
    --opttol     Curve optimization tolerance (default: 0.2)
    --overwrite  Overwrite existing SVG files (default: skip existing)
    --jobs       Number of parallel workers (default: CPU count)
"""

import argparse
import concurrent.futures
import os
import subprocess
import tempfile
from pathlib import Path


EXTENSIONS = ['jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp']


def find_magick() -> str:
    """Find ImageMagick binary."""
    for candidate in ['magick', 'convert']:
        try:
            subprocess.run([candidate, '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return candidate
        except Exception:
            continue
    raise RuntimeError("ImageMagick not found. Install it and ensure 'magick' or 'convert' is on PATH.")


def ensure_tools():
    """Verify required tools are installed."""
    find_magick()
    try:
        subprocess.run(['potrace', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception:
        raise RuntimeError("Potrace not found. Install it and ensure 'potrace' is on PATH.")


def run(cmd: list):
    """Run a command and raise on failure."""
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p


def to_pbm(src: Path, pbm_path: Path, threshold: int):
    """Convert image to PBM format."""
    magick = find_magick()
    cmd = [
        magick, str(src),
        '-colorspace', 'Gray',
        '-filter', 'point',
        '-resize', '100%',
        '-threshold', f'{threshold}%',
        '-type', 'bilevel',
        '-compress', 'none',
        str(pbm_path)
    ]
    run(cmd)


def potrace_to_svg(pbm_path: Path, svg_path: Path, turdsize: int, alphamax: float, opttol: float):
    """Convert PBM to SVG using Potrace."""
    cmd = [
        'potrace', str(pbm_path),
        '--svg',
        '--output', str(svg_path),
        '--turdsize', str(turdsize),
        '--alphamax', str(alphamax),
        '--opttolerance', str(opttol),
        '--flat',
        '--longcurve',
        '--group',
        '--turnpolicy', 'minority',
    ]
    run(cmd)


def vectorize_one(src: Path, dst_dir: Path, threshold: int, turdsize: int,
                  alphamax: float, opttol: float, overwrite: bool) -> str:
    """Vectorize a single image."""
    dst = dst_dir / (src.stem + '.svg')
    if dst.exists() and not overwrite:
        return f"skip  {src.name}"

    with tempfile.TemporaryDirectory() as td:
        pbm = Path(td) / (src.stem + '.pbm')
        to_pbm(src, pbm, threshold)
        potrace_to_svg(pbm, dst, turdsize, alphamax, opttol)

    return f"done  {src.name} → {dst.name}"


def discover_inputs(root: Path) -> list:
    """Find all image files in directory."""
    files = []
    for ext in EXTENSIONS:
        files.extend(root.rglob(f'*.{ext}'))
        files.extend(root.rglob(f'*.{ext.upper()}'))
    return list(set(files))


def main():
    parser = argparse.ArgumentParser(description='Batch convert images to SVG')
    parser.add_argument('files', nargs='*', help='Specific image files to convert (optional)')
    parser.add_argument('--input', default='drawings', help='Input directory (default: drawings, ignored if files provided)')
    parser.add_argument('--output', default='svgs', help='Output directory (default: svgs)')
    parser.add_argument('--threshold', type=int, default=88, help='Threshold 0-100 (default: 88)')
    parser.add_argument('--turdsize', type=int, default=2, help='Speckle filter size (default: 2)')
    parser.add_argument('--alphamax', type=float, default=1.0, help='Curve smoothness (default: 1.0)')
    parser.add_argument('--opttol', type=float, default=0.2, help='Optimization tolerance (default: 0.2)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing SVGs')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4, help='Parallel jobs')
    args = parser.parse_args()

    ensure_tools()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use provided files or discover from input directory
    if args.files:
        files = [Path(f) for f in args.files]
        # Validate files exist and have valid extensions
        valid_exts = {f'.{ext}' for ext in EXTENSIONS} | {f'.{ext.upper()}' for ext in EXTENSIONS}
        for f in files:
            if not f.exists():
                print(f"Error: File not found: {f}")
                return
            if f.suffix.lower() not in {f'.{ext}' for ext in EXTENSIONS}:
                print(f"Error: Unsupported file type: {f}")
                return
    else:
        input_dir = Path(args.input)
        files = discover_inputs(input_dir)

    if not files:
        print("No input files found.")
        return

    print(f"Found {len(files)} images. Writing SVGs to: {output_dir}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {
            ex.submit(
                vectorize_one, f, output_dir, args.threshold,
                args.turdsize, args.alphamax, args.opttol, args.overwrite
            ): f for f in files
        }
        for fut in concurrent.futures.as_completed(futures):
            try:
                print(fut.result())
            except Exception as e:
                print(f"FAIL  {futures[fut].name}: {e}")


if __name__ == '__main__':
    main()
