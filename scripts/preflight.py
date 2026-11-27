#!/usr/bin/env python3
"""Check a book's interior and covers against KDP and IngramSpark file rules before upload.

Requirements:
    pip install typst pyyaml
    ImageMagick (brew install imagemagick), to measure what's printed on each page

Usage:
    python preflight.py NAME [--printer kdp|ingram]

Builds the interior (without bleed) and each printer's cover in memory from
books/NAME/book.yml, exactly as build_book.py does, and checks:

- Content: the text fields (copyright, dedication, preface, about) are filled in with no
  TODOs left, and the paperback and ebook ISBNs are set and valid.
- Interior: trim size, page count (KDP's limits; even for IngramSpark), fonts embedded,
  grayscale only, and each page's margins (KDP's inside margin grows with the page count).
- Cover: size (both trims + spine + bleed), fonts embedded, grayscale only, everything
  inside the safe areas (0.125" from the trim, 0.0625" from the spine folds), spine text
  allowed for the page count, and the barcode area left blank.

Margins are measured on pages rendered at RENDER_PPI, so they're accurate to about 0.01".
Exits with status 1 if any check fails.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from build_book import (COVER_TEMPLATE, FONTS, REPO, SPINE_PER_PAGE, compile_interior, isbn_list,
                        page_count, resolve_book, resolve_cover)
from convert_to_png import find_magick

RENDER_PPI = 100

# KDP paperback, white paper, black ink: page limits, and the inside margin for each page
# count band (kdp.amazon.com/help/topic/GVBQ3CMEQW3W2VL6). Outside, top and bottom margins
# are at least 0.25" without bleed.
KDP_PAGES = (24, 828)
KDP_INSIDE = [(150, 0.375), (300, 0.5), (500, 0.625), (700, 0.75), (828, 0.875)]
KDP_OUTSIDE = 0.25
# IngramSpark's guides disagree on minimums, so use 0.5" on every side, stricter than any
# of them. Its interiors must have an even page count.
INGRAM_MARGIN = 0.5
INGRAM_MIN_PAGES = 18
# KDP allows spine text only from this many pages (thinner spines are too narrow).
KDP_SPINE_TEXT_PAGES = 79
# Text every book needs before publishing (Typst markup in book.yml).
TEXT_FIELDS = ('copyright', 'dedication', 'preface', 'about')
COVER_SAFE = 0.125
SPINE_SAFE = 0.0625
# Measurements within this of a limit pass (rendering and antialiasing blur edges slightly).
TOLERANCE = 0.01


def kdp_inside_margin(pages: int) -> float:
    return next((m for limit, m in KDP_INSIDE if pages <= limit), KDP_INSIDE[-1][1])


def pdf_problems(pdf: bytes, size: tuple) -> list:
    """Problems in the PDF itself: page sizes, embedded fonts and color spaces."""
    problems = []
    # Only the objects' dictionaries; compressed stream data could match anything.
    pdf = re.sub(rb'stream\r?\n.*?endstream', b'', pdf, flags=re.S)
    w, h = (round(v * 72, 2) for v in size)
    boxes = {(round(float(a), 2), round(float(b), 2))
             for a, b in re.findall(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', pdf)}
    if boxes != {(w, h)}:
        sizes = ', '.join(f'{a / 72:.4f}" x {b / 72:.4f}"' for a, b in sorted(boxes))
        problems.append(f'page size {sizes}, expected {size[0]:.4f}" x {size[1]:.4f}"')
    descriptors = re.findall(rb'/Type\s*/FontDescriptor.*?>>', pdf, re.S)
    unembedded = [d for d in descriptors if not re.search(rb'/FontFile[23]?\b', d)]
    if unembedded:
        problems.append(f'{len(unembedded)} font(s) not embedded')
    # Typst writes every color in one grayscale ICC space (/N 1) when only black and grays are used.
    if re.search(rb'/Device(RGB|CMYK)\b|/N\s*[34]\b', pdf):
        problems.append('uses color (RGB or CMYK); interiors and these covers should be grayscale')
    return problems


def ink_boxes(pngs: list) -> list:
    """The bounding box of everything printed on each rendered page, in inches: (x, y, w, h),
    or None for a blank page."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i, png in enumerate(pngs):
            path = Path(tmp) / f'{i:04d}.png'
            path.write_bytes(png)
            paths.append(str(path))
        out = subprocess.run([find_magick(), *paths, '-fuzz', '10%', '-format', '%@\n', 'info:'],
                             capture_output=True, text=True, check=True).stdout.split()
    boxes = []
    for geometry in out:
        w, h, x, y = (int(v) for v in re.match(r'(\d+)x(\d+)\+(\d+)\+(\d+)', geometry).groups())
        boxes.append((x / RENDER_PPI, y / RENDER_PPI, w / RENDER_PPI, h / RENDER_PPI) if w and h else None)
    return boxes


def page_ranges(pages: list) -> str:
    """Compact page list: [1, 2, 3, 7] → '1-3, 7'."""
    runs = []
    for p in pages:
        if runs and p == runs[-1][1] + 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    return ', '.join(f'{a}' if a == b else f'{a}-{b}' for a, b in runs)


def check_content(book: dict) -> tuple:
    """Return (notes, problems) for the text and ISBNs: everything needed before publishing."""
    problems = []
    for field in TEXT_FIELDS:
        if not book.get(field):
            problems.append(f'no `{field}:` in book.yml')
        elif 'TODO' in book[field]:
            problems.append(f'`{field}:` still has TODO text')
    try:
        isbns = dict(isbn_list(book))
    except ValueError as e:
        problems.append(str(e))
        isbns = {}
    missing = [fmt for fmt in ('paperback', 'ebook') if fmt not in isbns]
    if missing:
        problems.append(f"no {' or '.join(missing)} ISBN (`isbn: {{paperback: ..., ebook: ...}}`)")
    return [', '.join(f'{fmt} ISBN {isbn}' for fmt, isbn in isbns.items()) or 'no ISBNs yet'], problems


def check_interior(book: dict, printer: str) -> tuple:
    """Return (notes, problems) for the interior as uploaded to `printer`."""
    resolved = resolve_book(book)
    pdf = compile_interior(resolved)
    pages = page_count(pdf)
    trim = (book['trim']['width'], book['trim']['height'])
    problems = pdf_problems(pdf, trim)

    if printer == 'kdp':
        if not KDP_PAGES[0] <= pages <= KDP_PAGES[1]:
            problems.append(f'{pages} pages; KDP allows {KDP_PAGES[0]}-{KDP_PAGES[1]}')
        inside, outside = kdp_inside_margin(pages), KDP_OUTSIDE
    else:
        if pages % 2 or pages < INGRAM_MIN_PAGES:
            problems.append(f'{pages} pages; IngramSpark needs an even count of at least {INGRAM_MIN_PAGES}')
        inside = outside = INGRAM_MARGIN

    boxes = ink_boxes(compile_interior(resolved, format='png', ppi=RENDER_PPI))
    tight = {}  # side → [(page, margin)]
    for page, box in enumerate(boxes, start=1):
        if box is None:
            continue
        x, y, w, h = box
        left, right = x, trim[0] - x - w
        # Odd pages are right-hand pages, bound on their left.
        margins = {'inside': left if page % 2 else right, 'outside': right if page % 2 else left,
                   'top': y, 'bottom': trim[1] - y - h}
        for side, margin in margins.items():
            limit = inside if side == 'inside' else outside
            if margin < limit - TOLERANCE:
                tight.setdefault(side, []).append((page, margin))
    for side, found in tight.items():
        limit = inside if side == 'inside' else outside
        smallest = min(m for _, m in found)
        problems.append(f'{side} margin under {limit}" on page(s) {page_ranges([p for p, _ in found])} '
                        f'(smallest {smallest:.2f}")')

    notes = [f'{pages} pages, {trim[0]}" x {trim[1]}"; margins required: inside {inside}", '
             f'others {outside}"']
    return notes, problems


def check_cover(book: dict, printer: str) -> tuple:
    """Return (notes, problems) for `printer`'s cover."""
    import typst

    cover = resolve_cover(book, printer)
    w, h, spine, bleed = cover['trim']['width'], cover['trim']['height'], cover['spine'], cover['bleed']
    size = (2 * w + spine + 2 * bleed, h + 2 * bleed)
    args = dict(root=str(REPO), font_paths=[str(FONTS)], sys_inputs={'cover': json.dumps(cover)})
    pdf = typst.compile(str(COVER_TEMPLATE), **args)
    problems = pdf_problems(pdf, size)
    if printer == 'kdp' and cover['pages'] < KDP_SPINE_TEXT_PAGES:
        problems.append(f'{cover["pages"]} pages; KDP allows spine text only from {KDP_SPINE_TEXT_PAGES}')

    png = typst.compile(str(COVER_TEMPLATE), format='png', ppi=RENDER_PPI, **args)
    # Each panel's trim edges (left, right), the safe distance in from them, and the strip of the
    # sheet measured for it (the outer panels include their bleed), in inches from the left.
    spine_x = bleed + w
    regions = {
        'back cover': (bleed, spine_x, COVER_SAFE, (0, spine_x)),
        'spine': (spine_x, spine_x + spine, SPINE_SAFE, (spine_x, spine_x + spine)),
        'front cover': (spine_x + spine, size[0] - bleed, COVER_SAFE, (spine_x + spine, size[0])),
    }
    with tempfile.TemporaryDirectory() as tmp:
        sheet = Path(tmp) / 'cover.png'
        sheet.write_bytes(png)
        boxes = []
        for *_, (x0, x1) in regions.values():
            out = subprocess.run(
                [find_magick(), str(sheet), '-crop',
                 f'{round((x1 - x0) * RENDER_PPI)}x{round(size[1] * RENDER_PPI)}+{round(x0 * RENDER_PPI)}+0',
                 '+repage', '-fuzz', '10%', '-format', '%@', 'info:'],
                capture_output=True, text=True, check=True).stdout
            bw, bh, bx, by = (int(v) for v in re.match(r'(\d+)x(\d+)\+(\d+)\+(\d+)', out).groups())
            boxes.append((x0 + bx / RENDER_PPI, by / RENDER_PPI, bw / RENDER_PPI, bh / RENDER_PPI)
                         if bw and bh else None)
        if cover['barcode']:
            b = cover['barcode']
            bx0 = spine_x - b['inset'] - b['width']
            by0 = bleed + h - b['inset'] - b['height']
            out = subprocess.run(
                [find_magick(), str(sheet), '-crop',
                 f'{round(b["width"] * RENDER_PPI)}x{round(b["height"] * RENDER_PPI)}+'
                 f'{round(bx0 * RENDER_PPI)}+{round(by0 * RENDER_PPI)}',
                 '+repage', '-fuzz', '10%', '-format', '%@', 'info:'],
                capture_output=True, text=True, check=True).stdout
            if not out.startswith('0x0'):
                problems.append('something is printed in the barcode area')

    for (name, (left, right, safe, _)), box in zip(regions.items(), boxes):
        if box is None:
            continue
        x, y, bw, bh = box
        gaps = {'left': x - left, 'right': right - x - bw, 'top': y - bleed, 'bottom': bleed + h - y - bh}
        close = [f'{side} {gap:.3f}"' for side, gap in gaps.items() if gap < safe - TOLERANCE]
        if close:
            problems.append(f'{name}: content outside the safe area ({safe}" in): {", ".join(close)}')

    notes = [f'{cover["pages"]} interior pages, spine {spine:.4f}", sheet {size[0]:.4f}" x {size[1]:.4f}"']
    if printer == 'ingram':
        notes.append('grayscale cover; IngramSpark asks for CMYK covers (PDF/X-1a preferred), '
                     'so confirm with its file validator when uploading')
    return notes, problems


def preflight(name: str, printers: list = None) -> bool:
    """Print every check for each printer; return True if all pass."""
    book = yaml.safe_load((REPO / 'books' / name / 'book.yml').read_text())
    ok = True
    notes, problems = check_content(book)
    print(f"{name} content: {'FAIL' if problems else 'ok'}")
    for line in notes + [f'- {p}' for p in problems]:
        print(f'  {line}')
    ok = not problems
    for printer in printers or sorted(SPINE_PER_PAGE):
        for label, check in (('interior', check_interior), ('cover', check_cover)):
            notes, problems = check(book, printer)
            print(f"{name} {label} ({printer}): {'FAIL' if problems else 'ok'}")
            for note in notes:
                print(f'  {note}')
            for problem in problems:
                print(f'  - {problem}')
            ok = ok and not problems
    return ok


def main():
    parser = argparse.ArgumentParser(description='Check book PDFs against printer file rules')
    parser.add_argument('name', help='Book directory under books/ (e.g. volume-2)')
    parser.add_argument('--printer', choices=sorted(SPINE_PER_PAGE), help='Check one printer only')
    args = parser.parse_args()
    sys.exit(0 if preflight(args.name, [args.printer] if args.printer else None) else 1)


if __name__ == '__main__':
    main()
