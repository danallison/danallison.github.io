#!/usr/bin/env python3
"""Unified CLI for Jekyll site automation tasks.

Usage:
    python scripts/cli.py <command> [options]
    ./scripts/cli.py <command> [options]

Commands:
    generate-tags      Generate tag pages from collection metadata
    generate-metadata  Create .md files for new images
    rename-images      Rename date-only images to include suffix
    to-svg             Batch convert images to SVG
    to-png             Batch convert SVGs to PNG
    build-book         Build a book interior or cover PDF from books/NAME/book.yml
    build-ebook        Build a reflowable EPUB ebook from books/NAME/book.yml
    layout-editor      Adjust drawing sizes and positions in the browser

Examples:
    ./scripts/cli.py generate-tags
    ./scripts/cli.py generate-metadata --source drawings/ --dest _drawings/ --layout drawing
    ./scripts/cli.py rename-images --dir drawings/
    ./scripts/cli.py to-svg --input drawings --output svgs
    ./scripts/cli.py to-png --input svgs --output pngs-for-book --dpi 300
"""

import argparse
import os
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_generate_tags(args):
    """Generate tag pages from collection metadata."""
    from generate_tags import extract_tags, generate_tag_pages
    tags = extract_tags(args.config)
    count = generate_tag_pages(tags, args.output)
    print(f"Generated {count} tag pages in '{args.output}' directory.")


def cmd_generate_metadata(args):
    """Create .md files for new images."""
    from generate_image_metadata import generate_md_for_images
    created = generate_md_for_images(args.source, args.dest, args.layout)
    print(f"Created {created} new metadata files.")


def cmd_rename_images(args):
    """Rename date-only images to include suffix."""
    from rename_images import rename_images
    renamed = rename_images(args.dir)
    print(f"Renamed {renamed} images.")


def cmd_to_svg(args):
    """Batch convert images to SVG."""
    import concurrent.futures
    from pathlib import Path
    from convert_to_svg import ensure_tools, discover_inputs, vectorize_one

    ensure_tools()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

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


def cmd_to_png(args):
    """Batch convert SVGs to PNG."""
    import concurrent.futures
    from pathlib import Path
    from convert_to_png import find_magick, convert_one

    find_magick()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

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


def cmd_daily_drawing(args):
    """Fetch goodnight drawings from Community Archive."""
    from daily_drawing import daily_drawing
    daily_drawing(since=args.since, force=args.force, commit=args.commit)


def cmd_backfill_tweets(args):
    """Backfill tweet URLs for drawing pages."""
    from backfill_tweets import backfill_tweets
    backfill_tweets(dry_run=args.dry_run)


def cmd_build_book(args):
    """Build a book interior or cover PDF."""
    from build_book import build, build_cover, REPO
    if args.cover:
        bleed = 0.125 if args.bleed is None else args.bleed
        out = build_cover(args.name, args.cover, args.spine, bleed, args.guides, args.output)
    else:
        out = build(args.name, args.bleed or 0.0, args.output)
    print(f"Wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


def cmd_build_ebook(args):
    """Build a reflowable EPUB ebook."""
    from build_epub import build_epub, REPO
    out = build_epub(args.name, args.output)
    print(f"Wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


def cmd_layout_editor(args):
    """Serve the drawing layout editor for a book."""
    import sys
    sys.argv = ['layout_editor.py', args.name, '--port', str(args.port)] + (['--no-browser'] if args.no_browser else [])
    from layout_editor import main as editor_main
    editor_main()


def main():
    parser = argparse.ArgumentParser(
        description='Jekyll site automation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # generate-tags
    p_tags = subparsers.add_parser('generate-tags', help='Generate tag pages from collection metadata')
    p_tags.add_argument('--config', default='_config.yml', help='Path to Jekyll config (default: _config.yml)')
    p_tags.add_argument('--output', default='_tags/', help='Output directory (default: _tags/)')
    p_tags.set_defaults(func=cmd_generate_tags)

    # generate-metadata
    p_meta = subparsers.add_parser('generate-metadata', help='Create .md files for new images')
    p_meta.add_argument('--source', required=True, help='Source directory containing images')
    p_meta.add_argument('--dest', required=True, help='Destination directory for markdown files')
    p_meta.add_argument('--layout', required=True, help='Jekyll layout name')
    p_meta.set_defaults(func=cmd_generate_metadata)

    # rename-images
    p_rename = subparsers.add_parser('rename-images', help='Rename date-only images to include suffix')
    p_rename.add_argument('--dir', required=True, help='Directory containing images to rename')
    p_rename.set_defaults(func=cmd_rename_images)

    # to-svg
    p_svg = subparsers.add_parser('to-svg', help='Batch convert images to SVG')
    p_svg.add_argument('--input', default='drawings', help='Input directory (default: drawings)')
    p_svg.add_argument('--output', default='svgs', help='Output directory (default: svgs)')
    p_svg.add_argument('--threshold', type=int, default=88, help='Threshold 0-100 (default: 88)')
    p_svg.add_argument('--turdsize', type=int, default=2, help='Speckle filter size (default: 2)')
    p_svg.add_argument('--alphamax', type=float, default=1.0, help='Curve smoothness (default: 1.0)')
    p_svg.add_argument('--opttol', type=float, default=0.2, help='Optimization tolerance (default: 0.2)')
    p_svg.add_argument('--overwrite', action='store_true', help='Overwrite existing SVGs')
    p_svg.add_argument('--jobs', type=int, default=os.cpu_count() or 4, help='Parallel jobs')
    p_svg.set_defaults(func=cmd_to_svg)

    # to-png
    p_png = subparsers.add_parser('to-png', help='Batch convert SVGs to PNG')
    p_png.add_argument('--input', default='svgs', help='Input directory (default: svgs)')
    p_png.add_argument('--output', default='pngs-for-book', help='Output directory (default: pngs-for-book)')
    p_png.add_argument('--dpi', type=int, default=300, help='DPI resolution (default: 300)')
    p_png.add_argument('--page-width', type=float, default=5.83, help='Max printed width in inches (default: 5.83, A5)')
    p_png.add_argument('--page-height', type=float, default=8.27, help='Max printed height in inches (default: 8.27, A5)')
    p_png.add_argument('--overwrite', action='store_true', help='Overwrite existing PNGs')
    p_png.add_argument('--jobs', type=int, default=os.cpu_count() or 4, help='Parallel jobs')
    p_png.set_defaults(func=cmd_to_png)

    # daily-drawing
    p_daily = subparsers.add_parser('daily-drawing', help='Fetch goodnight drawings from Community Archive')
    p_daily.add_argument('--since', help='Start date YYYY-MM-DD (default: most recent local drawing)')
    p_daily.add_argument('--force', action='store_true', help='Re-download even if date exists locally')
    p_daily.add_argument('--commit', action='store_true', help='Commit changes after processing')
    p_daily.set_defaults(func=cmd_daily_drawing)

    # backfill-tweets
    p_backfill = subparsers.add_parser('backfill-tweets', help='Backfill tweet URLs for drawing pages')
    p_backfill.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    p_backfill.set_defaults(func=cmd_backfill_tweets)

    # build-book
    p_book = subparsers.add_parser('build-book', help='Build a book interior or cover PDF from books/NAME/book.yml')
    p_book.add_argument('name', help='Book directory under books/ (e.g. volume-1)')
    p_book.add_argument('--cover', choices=['kdp', 'ingram'], help='Build the paperback cover for this printer')
    p_book.add_argument('--spine', type=float, help='Cover spine width in inches (default: from book.yml or page count)')
    p_book.add_argument('--guides', action='store_true', help='Draw trim, fold, safe-area and barcode guides on the cover')
    p_book.add_argument('--bleed', type=float, help='Bleed in inches (default: 0 for interiors, 0.125 for covers)')
    p_book.add_argument('--output', type=Path, help='Output PDF path (default: book-files/NAME/interior.pdf or cover-PRINTER.pdf)')
    p_book.set_defaults(func=cmd_build_book)

    # build-ebook
    p_ebook = subparsers.add_parser('build-ebook', help='Build a reflowable EPUB ebook from books/NAME/book.yml')
    p_ebook.add_argument('name', help='Book directory under books/ (e.g. volume-2)')
    p_ebook.add_argument('--output', type=Path, help='Output EPUB path (default: book-files/NAME/NAME.epub)')
    p_ebook.set_defaults(func=cmd_build_ebook)

    # layout-editor
    p_editor = subparsers.add_parser('layout-editor', help='Adjust drawing sizes and positions in the browser')
    p_editor.add_argument('name', help='Book directory under books/ (e.g. volume-2)')
    p_editor.add_argument('--port', type=int, default=8765, help='Port (default: 8765)')
    p_editor.add_argument('--no-browser', action='store_true', help="Don't open a browser")
    p_editor.set_defaults(func=cmd_layout_editor)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
