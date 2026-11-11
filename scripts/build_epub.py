#!/usr/bin/env python3
"""Build a reflowable EPUB 3 ebook from books/<name>/book.yml.

Requirements:
    pip install typst pyyaml
    ImageMagick (brew install imagemagick)

Usage:
    python build_epub.py NAME [--output PATH]

Arguments:
    NAME      Book directory under books/ (e.g. volume-2)
    --output  Output EPUB path (default: book-files/NAME/NAME.epub)

One drawing per page, cropped to its ink and saved as a small 4-gray PNG (Kindle charges
a delivery fee per megabyte). The cover is the front of the paperback cover. Front matter
comes from book.yml; the ebook ISBN, if set (`isbn: {ebook: ...}`), goes on the copyright page
and in the metadata. Also writes the cover as a separate JPEG (NAME-cover.jpg) for the
ebook cover upload.
"""

import argparse
import concurrent.futures
import html
import json
import os
import re
import subprocess
import sys
import uuid
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from build_book import COVER_TEMPLATE, FONTS, REPO, load_ink_bounds, resolve_cover
from convert_to_png import find_magick, svg_size

# Drawings are fitted into this many pixels (portrait), then reduced to GRAYS shades.
IMAGE_BOX = (1200, 1600)
GRAYS = 4
# Blank margin kept around each drawing's ink, as a fraction of its longer side.
IMAGE_MARGIN = 0.02
# Ebook cover height in pixels (KDP recommends 2560 on the long side).
COVER_HEIGHT = 2560
# Kindle's delivery fee (US, 70% royalty option), per megabyte.
DELIVERY_FEE_PER_MB = 0.15

CSS = """\
body { margin: 0; padding: 0; font-family: serif; line-height: 1.5; }
p { margin: 0 0 1em 0; text-indent: 0; }
h1 { font-size: 1.4em; font-weight: 600; margin: 2em 0 1em 0; }
.title-page { text-align: center; margin-top: 30%; }
.title-page .title { font-size: 1.6em; margin: 0; }
.title-page .volume { font-size: 1.6em; font-weight: bold; margin: 0 0 1.5em 0; }
.title-page .author { font-size: 1.2em; }
.copyright { text-align: center; font-size: 0.85em; margin-top: 20%; }
.dedication { text-align: center; font-style: italic; margin-top: 30%; }
.preface p { text-align: justify; }
.image-page { margin: 0; padding: 0; text-align: center; }
.image-page img { max-width: 100%; max-height: 95vh; width: auto; height: auto; }
.end-mark { margin-top: 30%; }
.end-mark img { width: 37%; }  /* as in print: 2.156" of a 5.83" page */
"""


def drawing_alt(drawing_id: str) -> str:
    """Alt text from a drawing id like 2025-12-01_wizard-cat-electric-disks."""
    day, _, slug = drawing_id.partition('_')
    when = date.fromisoformat(day).strftime('%B %-d, %Y')
    if slug and not slug.isdigit():
        return f"Drawing: {slug.replace('-', ' ')} ({when})"
    return f"Drawing from {when}"


def markup_html(text: str) -> str:
    """Convert the Typst markup used in book.yml text (_italic_, *bold*, \\@, trailing \\
    line breaks, blank-line paragraphs) to XHTML paragraphs, linking bare URLs."""
    paragraphs = []
    for para in re.split(r'\n\s*\n', text.strip()):
        lines = [line.strip() for line in para.strip().split('\n')]
        out = []
        for i, line in enumerate(lines):
            brk = line.endswith('\\')
            line = line.rstrip('\\').rstrip()
            urls = []

            def stash(m):
                urls.append(m.group(0))
                return f"\x00{len(urls) - 1}\x00"
            line = re.sub(r'https?://[^\s()]+[^\s().,;:]', stash, line)
            line = html.escape(line, quote=False)
            line = re.sub(r'\\([@#$*_\\])', r'\1', line)
            line = re.sub(r'(?<![\w\\])_(.+?)_(?!\w)', r'<em>\1</em>', line)
            line = re.sub(r'(?<![\w\\])\*(.+?)\*(?!\w)', r'<strong>\1</strong>', line)
            line = re.sub(r'\x00(\d+)\x00', lambda m: '<a href="{0}">{0}</a>'.format(
                html.escape(urls[int(m.group(1))])), line)
            out.append(line + ('<br/>' if brk and i < len(lines) - 1 else ''))
        paragraphs.append('<p>' + '\n'.join(out) + '</p>')
    return '\n'.join(paragraphs)


def xhtml(title: str, body: str, epub_type: str = None) -> str:
    type_attr = f' epub:type="{epub_type}"' if epub_type else ''
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body{type_attr}>
{body}
</body>
</html>
"""


def render_drawing(svg: Path, bounds: list, dst: Path) -> Path:
    """Render a drawing's ink (plus a small margin) as a GRAYS-shade PNG fitted to IMAGE_BOX."""
    if dst.exists() and dst.stat().st_mtime >= svg.stat().st_mtime:
        return dst
    x, y, w, h = bounds
    sw, sh = svg_size(svg)  # potrace units; ImageMagick renders them at 96 per inch of density
    scale = min(IMAGE_BOX[0] / (w * sw), IMAGE_BOX[1] / (h * sh)) / (1 + 2 * IMAGE_MARGIN)
    fw, fh = sw * scale, sh * scale
    m = IMAGE_MARGIN * max(w * fw, h * fh)
    crop = f"{w * fw + 2 * m:.0f}x{h * fh + 2 * m:.0f}+{max(0, x * fw - m):.0f}+{max(0, y * fh - m):.0f}"
    levels = int.bit_length(GRAYS - 1)
    subprocess.run(
        [find_magick(), '-density', f'{96 * scale:.3f}', str(svg), '-background', 'white', '-flatten',
         '-crop', crop, '+repage', '-colorspace', 'Gray', '-posterize', str(GRAYS),
         '-depth', str(levels), '-define', 'png:compression-level=9', '-strip', str(dst)],
        check=True, capture_output=True)
    return dst


def render_cover(book: dict, dst: Path) -> Path:
    """The front of the KDP paperback cover, without bleed, as a JPEG COVER_HEIGHT tall."""
    import typst
    cover = resolve_cover(book, 'kdp', bleed=0.0)
    ppi = COVER_HEIGHT / cover['trim']['height']
    png = typst.compile(str(COVER_TEMPLATE), root=str(REPO), font_paths=[str(FONTS)], format='png',
                        ppi=ppi, sys_inputs={'cover': json.dumps(cover)})
    left = round((cover['trim']['width'] + cover['spine']) * ppi)
    width = round(cover['trim']['width'] * ppi)
    subprocess.run([find_magick(), 'png:-', '-crop', f'{width}x{COVER_HEIGHT}+{left}+0', '+repage',
                    '-colorspace', 'sRGB', '-quality', '88', '-strip', str(dst)],
                   input=png, check=True, capture_output=True)
    return dst


def build_epub(name: str, output: Path = None) -> Path:
    book = yaml.safe_load((REPO / 'books' / name / 'book.yml').read_text())
    out_dir = REPO / 'book-files' / name
    img_dir = out_dir / 'epub-images'
    img_dir.mkdir(parents=True, exist_ok=True)
    output = output or out_dir / f'{name}.epub'

    full_title = f"{book['title']} Volume {book['volume']}"
    isbn = (book.get('isbn') or {}).get('ebook')
    identifier = f"urn:isbn:{isbn.replace('-', '')}" if isbn else \
        f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'https://danallison.info/books/{name}')}"
    year = re.search(r'©\s*(\d{4})', book['copyright'])

    # Images
    ids = [e if isinstance(e, str) else e['id'] for e in book['drawings']]
    svgs = [REPO / 'svgs' / f'{i}.svg' for i in ids]
    bounds = load_ink_bounds(svgs)
    print(f"Rendering {len(svgs)} drawings...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        images = list(ex.map(lambda s: render_drawing(s, bounds[s], img_dir / f'{s.stem}.png'), svgs))
    end_mark = None
    if book.get('end_mark'):
        mark_svg = REPO / book['end_mark']['path']
        end_mark = render_drawing(mark_svg, load_ink_bounds([mark_svg])[mark_svg], img_dir / 'end-mark.png')
    cover = render_cover(book, out_dir / f'{name}-cover.jpg')

    # Pages, in reading order: (file, title, xhtml body, epub:type)
    copyright = markup_html(book['copyright'])
    if isbn:
        copyright += f'\n<p>ISBN {html.escape(isbn)} (ebook)</p>'
    pages = [
        ('cover.xhtml', 'Cover',
         f'<div class="image-page"><img src="images/cover.jpg" alt="Cover: {html.escape(full_title)}, by {html.escape(book["author"])}"/></div>',
         'cover'),
        ('title.xhtml', full_title,
         f'<div class="title-page"><p class="title">{html.escape(book["title"])}</p>'
         f'<p class="volume">Volume {book["volume"]}</p><p class="author">by {html.escape(book["author"])}</p></div>',
         'titlepage'),
        ('copyright.xhtml', 'Copyright', f'<div class="copyright">{copyright}</div>', 'copyright-page'),
        ('dedication.xhtml', 'Dedication', f'<div class="dedication"><p>{html.escape(book["dedication"])}</p></div>',
         'dedication'),
        ('preface.xhtml', 'Preface', f'<section class="preface"><h1>Preface</h1>\n{markup_html(book["preface"])}</section>',
         'preface'),
    ]
    for n, (i, img) in enumerate(zip(ids, images), 1):
        pages.append((f'd{n:03d}.xhtml', f'Drawing {n}',
                      f'<div class="image-page"><img src="images/{img.name}" alt="{html.escape(drawing_alt(i))}"/></div>',
                      'bodymatter' if n == 1 else None))
    if end_mark:
        pages.append(('end.xhtml', 'End', '<div class="image-page end-mark"><img src="images/end-mark.png" alt="A heart with a face, beside another face"/></div>', None))

    first_drawing = 'd001.xhtml'
    nav = xhtml('Contents', f"""<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>
<li><a href="title.xhtml">{html.escape(full_title)}</a></li>
<li><a href="preface.xhtml">Preface</a></li>
<li><a href="{first_drawing}">Drawings</a></li>
</ol></nav>
<nav epub:type="landmarks" hidden="hidden"><ol>
<li><a epub:type="cover" href="cover.xhtml">Cover</a></li>
<li><a epub:type="bodymatter" href="{first_drawing}">Drawings</a></li>
</ol></nav>""")
    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="{identifier}"/></head>
<docTitle><text>{html.escape(full_title)}</text></docTitle>
<navMap>
<navPoint id="n1" playOrder="1"><navLabel><text>{html.escape(full_title)}</text></navLabel><content src="title.xhtml"/></navPoint>
<navPoint id="n2" playOrder="2"><navLabel><text>Preface</text></navLabel><content src="preface.xhtml"/></navPoint>
<navPoint id="n3" playOrder="3"><navLabel><text>Drawings</text></navLabel><content src="{first_drawing}"/></navPoint>
</navMap>
</ncx>
"""

    modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>',
    ]
    manifest += [f'<item id="img-{p.stem}" href="images/{p.name}" media-type="image/png"/>'
                 for p in images + ([end_mark] if end_mark else [])]
    manifest += [f'<item id="{f[:-6]}" href="{f}" media-type="application/xhtml+xml"/>' for f, *_ in pages]
    spine = [f'<itemref idref="{f[:-6]}"/>' for f, *_ in pages]
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="pub-id">{identifier}</dc:identifier>
<dc:title>{html.escape(full_title)}</dc:title>
<dc:creator id="author">{html.escape(book['author'])}</dc:creator>
<meta refines="#author" property="role" scheme="marc:relators">aut</meta>
<dc:publisher>{html.escape(book.get('publisher', book['author']))}</dc:publisher>
<dc:language>en</dc:language>
{f'<dc:date>{year.group(1)}</dc:date>' if year else ''}
<dc:rights>Copyright © {year.group(1) if year else ''} {html.escape(book['author'])}. Licensed under Creative Commons Attribution-NonCommercial 4.0 International.</dc:rights>
<meta property="dcterms:modified">{modified}</meta>
<meta property="belongs-to-collection" id="series">{html.escape(book['title'])}</meta>
<meta refines="#series" property="collection-type">series</meta>
<meta refines="#series" property="group-position">{book['volume']}</meta>
<meta name="cover" content="cover-image"/>
<meta property="schema:accessMode">visual</meta>
<meta property="schema:accessMode">textual</meta>
<meta property="schema:accessModeSufficient">visual,textual</meta>
<meta property="schema:accessibilityFeature">alternativeText</meta>
<meta property="schema:accessibilityFeature">tableOfContents</meta>
<meta property="schema:accessibilityHazard">none</meta>
<meta property="schema:accessibilitySummary">A book of line drawings, one per page, each with a short text description.</meta>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">
{chr(10).join(spine)}
</spine>
</package>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""

    with zipfile.ZipFile(output, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        deflate = lambda path, data: z.writestr(path, data, compress_type=zipfile.ZIP_DEFLATED)
        deflate('META-INF/container.xml', container)
        deflate('OEBPS/content.opf', opf)
        deflate('OEBPS/nav.xhtml', nav)
        deflate('OEBPS/toc.ncx', ncx)
        deflate('OEBPS/style.css', CSS)
        for f, title, body, epub_type in pages:
            deflate(f'OEBPS/{f}', xhtml(title, body, epub_type))
        z.write(cover, 'OEBPS/images/cover.jpg', compress_type=zipfile.ZIP_STORED)
        for img in images + ([end_mark] if end_mark else []):
            z.write(img, f'OEBPS/images/{img.name}', compress_type=zipfile.ZIP_STORED)

    mb = output.stat().st_size / 1e6
    print(f"{len(images)} drawings, {mb:.1f} MB (Kindle delivery fee about ${mb * DELIVERY_FEE_PER_MB:.2f} per sale)")
    if not isbn:
        print("Note: no ebook ISBN in book.yml (isbn: {ebook: ...}); using a generated identifier")
    return output


def main():
    parser = argparse.ArgumentParser(description='Build a reflowable EPUB 3 ebook')
    parser.add_argument('name', help='Book directory under books/ (e.g. volume-2)')
    parser.add_argument('--output', type=Path, help='Output EPUB path')
    args = parser.parse_args()

    out = build_epub(args.name, args.output)
    print(f"Wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


if __name__ == '__main__':
    main()
