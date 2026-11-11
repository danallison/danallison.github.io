#!/usr/bin/env python3
"""Build a book interior or cover PDF from books/<name>/book.yml.

Requirements:
    pip install typst pyyaml
    ImageMagick (brew install imagemagick), to find each drawing's ink bounds

Usage:
    python build_book.py NAME [--bleed INCHES] [--output PATH]
    python build_book.py NAME --cover PRINTER [--spine INCHES] [--bleed INCHES] [--guides] [--output PATH]

Arguments:
    NAME      Book directory under books/ (e.g. volume-1)
    --cover   Build the paperback cover for a printer (kdp or ingram) instead of the interior
    --spine   Cover spine width in inches (default: from book.yml, else interior pages x paper)
    --guides  Draw trim, fold, safe-area and barcode guides on the cover (for checking only)
    --bleed   Bleed added to every edge, in inches (interior default: 0, as KDP and IngramSpark
              take interiors without bleed; cover default: 0.125)
    --output  Output PDF path (default: book-files/NAME/interior.pdf, interior-bleed.pdf with
              bleed, or cover-PRINTER.pdf)

Each drawing is sized and centered by its ink (ignoring the blank paper around it), scaled
to fit a box so it fills either the box's width or its height. Nothing is clipped. book.yml
drawings entries are either a drawing id or a mapping with `id` and one of `width` (inches),
`height` (inches), or `scale` (multiplier on the default size), plus optional `dx`/`dy`
(inches; nudge right/down from centered, for drawings that look off-center). Optional `sizing:` keys:
`max_width`, `max_height` (the box, in inches) and `crop` (false to place whole photos, as
Volume 1 does).

The cover is set by `cover:` in book.yml: `front` and `back` drawings (entries like the ones
above, always sized by their ink), plus optional `spine: {kdp: ..., ingram: ...}` widths,
`sizing: {front: {...}, back: {...}}` boxes, and `barcode: false` to leave no barcode area.
"""

import argparse
import concurrent.futures
import json
import os
import re
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

COVER_TEMPLATE = REPO / 'books' / 'shared' / 'cover.typ'

# Spine width per interior page on white paper, in inches. KDP's is from its help pages;
# IngramSpark's may differ slightly, so set its exact width from the cover template it emails
# (`cover: {spine: {ingram: ...}}` in book.yml).
SPINE_PER_PAGE = {'kdp': 0.002252, 'ingram': 0.002252}
# Kept clear in the bottom corner of the back cover, by the spine (inches).
BARCODE_AREA = {'width': 2.0, 'height': 1.2, 'inset': 0.25}
# Boxes the cover drawings' ink is fitted into. The front leaves ~0.6" to the title and the
# author line; the back is kept short enough to clear the barcode area when centred.
COVER_SIZING = {'front': {'max_width': 4.2, 'max_height': 5.0},
                'back': {'max_width': 4.2, 'max_height': 4.9}}

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


def page_count(pdf: bytes) -> int:
    """Number of pages in a PDF written by Typst."""
    return int(re.search(rb'/Type\s*/Pages\s*/Count\s+(\d+)', pdf).group(1))


def resolve_cover(book: dict, printer: str, spine: float = None, bleed: float = 0.125,
                  guides: bool = False) -> dict:
    """Resolve cover drawing sizes and spine width for one printer."""
    import typst

    cover = {k: {'id': v} if k in ('front', 'back') and isinstance(v, str) else v
             for k, v in book['cover'].items()}
    pages = page_count(typst.compile(str(TEMPLATE), root=str(REPO), font_paths=[str(FONTS)],
                                     sys_inputs={'book': json.dumps(resolve_book(book)), 'bleed': '0'}))
    if spine is None:
        spine = cover.get('spine', {}).get(printer) or round(pages * SPINE_PER_PAGE[printer], 4)

    svgs = {side: REPO / 'svgs' / f"{cover[side]['id']}.svg" for side in ('front', 'back')}
    bounds = load_ink_bounds(list(svgs.values()))
    sizing = {side: {**COVER_SIZING[side], **cover.get('sizing', {}).get(side, {})} for side in svgs}
    resolved = {
        'title': book['title'], 'volume': book['volume'], 'author': book['author'],
        'trim': book['trim'], 'pages': pages, 'spine': spine, 'bleed': bleed, 'guides': guides,
        'face_mark': '/books/shared/face-mark.svg',
        'barcode': BARCODE_AREA if cover.get('barcode', True) else None,
    }
    for side, svg in svgs.items():
        resolved[side] = resolve_image(f"/svgs/{cover[side]['id']}.svg", cover[side], sizing[side],
                                       bounds[svg])
    return resolved


def barcode_overlap(cover: dict) -> bool:
    """Whether the back drawing's ink box runs into the barcode area."""
    if not cover['barcode']:
        return False
    b, d, t = cover['barcode'], cover['back'], cover['trim']
    left, bottom = t['width'] / 2 - d['width'] / 2 + d['dx'], t['height'] / 2 + d['height'] / 2 + d['dy']
    right = left + d['width']
    return right > t['width'] - b['inset'] - b['width'] and bottom > t['height'] - b['inset'] - b['height']


def build_cover(name: str, printer: str, spine: float = None, bleed: float = 0.125,
                guides: bool = False, output: Path = None) -> Path:
    import typst

    book = yaml.safe_load((REPO / 'books' / name / 'book.yml').read_text())
    cover = resolve_cover(book, printer, spine, bleed, guides)
    print(f"{cover['pages']} interior pages, spine {cover['spine']:.4f}\", "
          f"cover {2 * cover['trim']['width'] + cover['spine'] + 2 * bleed:.4f}\" x "
          f"{cover['trim']['height'] + 2 * bleed:.4f}\"")
    if barcode_overlap(cover):
        print("Warning: the back drawing overlaps the barcode area (shrink or move it in book.yml)")

    if output is None:
        output = REPO / 'book-files' / name / f"cover-{printer}{'-guides' if guides else ''}.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    typst.compile(str(COVER_TEMPLATE), output=str(output), root=str(REPO), font_paths=[str(FONTS)],
                  sys_inputs={'cover': json.dumps(cover)})
    return output


def main():
    parser = argparse.ArgumentParser(description='Build a book interior or cover PDF')
    parser.add_argument('name', help='Book directory under books/ (e.g. volume-1)')
    parser.add_argument('--cover', choices=sorted(SPINE_PER_PAGE), help='Build the cover for this printer')
    parser.add_argument('--spine', type=float, help='Cover spine width in inches')
    parser.add_argument('--guides', action='store_true', help='Draw guides on the cover')
    parser.add_argument('--bleed', type=float, help='Bleed in inches (interior: 0, cover: 0.125)')
    parser.add_argument('--output', type=Path, help='Output PDF path')
    args = parser.parse_args()

    if args.cover:
        bleed = 0.125 if args.bleed is None else args.bleed
        out = build_cover(args.name, args.cover, args.spine, bleed, args.guides, args.output)
    else:
        out = build(args.name, args.bleed or 0.0, args.output)
    print(f"Wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


if __name__ == '__main__':
    main()
