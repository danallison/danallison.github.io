#!/usr/bin/env python3
"""Build a book interior PDF from books/<name>/book.yml.

Requirements:
    pip install typst pyyaml
    ImageMagick (brew install imagemagick), to find each drawing's ink bounds

Usage:
    python build_book.py NAME [--bleed INCHES] [--output PATH]

Arguments:
    NAME      Book directory under books/ (e.g. volume-1)
    --bleed   Bleed added to every edge, in inches (default: 0; Lulu's print-ready files use 0.125)
    --output  Output PDF path (default: book-files/NAME/interior.pdf, or interior-bleed.pdf with bleed)

Each drawing is sized and centered by its ink (ignoring the blank paper around it), scaled
to fit a box so it fills either the box's width or its height. Nothing is clipped. book.yml
drawings entries are either a drawing id or a mapping with `id` and one of `width` (inches),
`height` (inches), or `scale` (multiplier on the default size), plus optional `dx`/`dy`
(inches; nudge right/down from centered, for drawings that look off-center). Optional `sizing:` keys:
`max_width`, `max_height` (the box, in inches) and `crop` (false to place whole photos, as
Volume 1 does).
"""

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from convert_to_png import find_magick, svg_size

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / 'books' / 'shared' / 'interior.typ'
FONTS = REPO / 'books' / 'shared' / 'fonts'
INK_CACHE = REPO / 'book-files' / '.ink-bounds.json'

# Box each drawing's ink is fitted into. Leaves at least 1.1" to the page edges and about
# 1" between the drawing and the running header and page number.
DEFAULT_SIZING = {'max_width': 3.5, 'max_height': 5.0, 'crop': True}


def ink_bounds(svg: Path) -> list:
    """Return the ink's bounding box as fractions of the SVG frame: [x, y, width, height].

    Specks smaller than ~2pt across (stray marks on the paper) are ignored so they don't
    stretch the box.
    """
    out = subprocess.run(
        [find_magick(), '-density', '72', str(svg), '-background', 'white', '-flatten',
         '-threshold', '50%', '-define', 'connected-components:area-threshold=8',
         '-define', 'connected-components:mean-color=true', '-connected-components', '8',
         '-trim', '-format', '%w %h %X %Y %W %H', 'info:'],
        capture_output=True, text=True, check=True).stdout.split()
    w, h, x, y, fw, fh = (float(v) for v in out)
    return [x / fw, y / fh, w / fw, h / fh]


def load_ink_bounds(svgs: list) -> dict:
    """Ink bounds for each SVG path, cached by modification time (ImageMagick takes ~1s each)."""
    try:
        cache = json.loads(INK_CACHE.read_text())
    except (FileNotFoundError, ValueError):
        cache = {}
    key = lambda svg: str(svg.relative_to(REPO))
    stale = [svg for svg in svgs if cache.get(key(svg), {}).get('mtime') != svg.stat().st_mtime]
    if stale:
        print(f"Measuring ink bounds of {len(stale)} drawings...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            for svg, bounds in zip(stale, ex.map(ink_bounds, stale)):
                cache[key(svg)] = {'mtime': svg.stat().st_mtime, 'bounds': bounds}
        INK_CACHE.parent.mkdir(parents=True, exist_ok=True)
        INK_CACHE.write_text(json.dumps(cache, indent=1))
    return {svg: cache[key(svg)]['bounds'] for svg in svgs}


def resolve_image(path: str, entry: dict, sizing: dict, crop: list = None) -> dict:
    """Compute the placed size of one image (its ink, if `crop` is given) from the entry's overrides."""
    sw, sh = svg_size(REPO / path.lstrip('/'))
    if crop:
        sw, sh = sw * crop[2], sh * crop[3]
    aspect = sw / sh
    if 'width' in entry:
        w = entry['width']
    elif 'height' in entry:
        w = entry['height'] * aspect
    else:
        w = min(sizing['max_width'], sizing['max_height'] * aspect) * entry.get('scale', 1.0)
    return {'path': path, 'width': round(w, 4), 'height': round(w / aspect, 4), 'crop': crop,
            'dx': entry.get('dx', 0), 'dy': entry.get('dy', 0)}


def resolve_book(book: dict) -> dict:
    sizing = {**DEFAULT_SIZING, **book.get('sizing', {})}
    entries = [{'id': e} if isinstance(e, str) else e for e in book['drawings']]
    svgs = [REPO / 'svgs' / f"{e['id']}.svg" for e in entries]
    missing = [str(svg.relative_to(REPO)) for svg in svgs if not svg.exists()]
    if missing:
        raise FileNotFoundError(f"Missing SVGs: {', '.join(missing)}")
    bounds = load_ink_bounds(svgs) if sizing['crop'] else {}

    drawings = [{'id': e['id'], **resolve_image(f"/svgs/{e['id']}.svg", e, sizing, bounds.get(svg))}
                for e, svg in zip(entries, svgs)]
    resolved = {**book, 'drawings': drawings}
    if book.get('end_mark'):
        resolved['end_mark'] = resolve_image('/' + book['end_mark']['path'], book['end_mark'], sizing)
    return resolved


def build(name: str, bleed: float = 0.0, output: Path = None) -> Path:
    import typst

    book_dir = REPO / 'books' / name
    book = yaml.safe_load((book_dir / 'book.yml').read_text())
    resolved = resolve_book(book)

    if output is None:
        output = REPO / 'book-files' / name / ('interior-bleed.pdf' if bleed else 'interior.pdf')
    output.parent.mkdir(parents=True, exist_ok=True)

    typst.compile(
        str(TEMPLATE),
        output=str(output),
        root=str(REPO),
        font_paths=[str(FONTS)],
        sys_inputs={'book': json.dumps(resolved), 'bleed': str(bleed)},
    )
    return output


def main():
    parser = argparse.ArgumentParser(description='Build a book interior PDF')
    parser.add_argument('name', help='Book directory under books/ (e.g. volume-1)')
    parser.add_argument('--bleed', type=float, default=0.0, help='Bleed in inches (default: 0)')
    parser.add_argument('--output', type=Path, help='Output PDF path')
    args = parser.parse_args()

    out = build(args.name, args.bleed, args.output)
    print(f"Wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


if __name__ == '__main__':
    main()
