# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Python Environment

Python scripts require the project-local virtual environment (`.venv/`). Activate it before running scripts:
```bash
source .venv/bin/activate
./scripts/cli.py <command>
```

## Build Commands

```bash
# Install dependencies (first time)
bundle install

# Run local development server
bundle exec jekyll serve

# Build site without serving
bundle exec jekyll build
```

The built site outputs to `_site/`. GitHub Pages builds automatically on push.

## Architecture

This is a Jekyll static site for a personal portfolio (danallison.info) with art/drawings and writings.

### Collections System

Five Jekyll collections defined in `_config.yml`:
- `_drawings/` → `/drawings/:title/`
- `_stereoscopic_images/` → `/stereoscopic-images/:title/`
- `_scribbles/` → `/scribbles/:title`
- `_stereo_tarot_cards/` → `/stereo-tarot/:title`
- `_tags/` → `/tags/:title/`

Each collection item is a markdown file with YAML frontmatter. The actual image files live in corresponding non-underscore directories (e.g., `drawings/` contains JPGs, `_drawings/` contains metadata).

### Naming Convention

Image files and their markdown metadata follow: `YYYY-MM-DD_descriptive-name.ext`

Frontmatter structure for images:
```yaml
---
layout: drawing
filename: 2024-01-15_home-protector.jpg
pagename: 2024-01-15_home-protector
date: 2024-01-15
tags:
  - house
  - figure
---
```

### Adding New Drawings Workflow

The `_drawings/` collection is generated from images in `drawings/`:

1. **Add images** to `drawings/` with naming pattern `YYYY-MM-DD_descriptive-name.jpg`
2. **Generate metadata** by running:
   ```bash
   ./scripts/cli.py generate-metadata --source drawings/ --dest _drawings/ --layout drawing
   ```
   This creates a `.md` file in `_drawings/` for each new image, with frontmatter containing `layout`, `filename`, `pagename`, and `date` extracted from the filename.
3. **Add tags** (optional) - Edit the generated `.md` files to add tags to the frontmatter
4. **Regenerate tag pages** if you added new tags:
   ```bash
   ./scripts/cli.py generate-tags
   ```

The script skips images that already have corresponding metadata files, so it's safe to re-run after adding new images.

### Automation Scripts

Python scripts in `scripts/` handle tasks that would normally be Jekyll plugins (GitHub Pages doesn't allow custom plugins).

**Unified CLI** - All commands available via `./scripts/cli.py`:
```bash
./scripts/cli.py generate-tags                    # Generate tag pages
./scripts/cli.py generate-metadata --source drawings/ --dest _drawings/ --layout drawing
./scripts/cli.py rename-images --dir drawings/    # Rename YYYY-MM-DD.jpg → YYYY-MM-DD_1.jpg
./scripts/cli.py to-svg                           # Convert images to SVG
./scripts/cli.py to-png --dpi 300                 # Convert SVGs to PNG
```

Individual scripts can also be run directly:

**generate_tags.py** - Generate tag pages from collection metadata
```bash
python scripts/generate_tags.py [--config _config.yml] [--output _tags/]
```
| Argument | Default | Description |
|----------|---------|-------------|
| `--config` | `_config.yml` | Path to Jekyll config |
| `--output` | `_tags/` | Output directory for tag pages |

**generate_image_metadata.py** - Create `.md` files for new images
```bash
python scripts/generate_image_metadata.py --source <dir> --dest <dir> --layout <name>
```
| Argument | Required | Description |
|----------|----------|-------------|
| `--source` | Yes | Source directory containing images (e.g., `drawings/`) |
| `--dest` | Yes | Destination directory for markdown files (e.g., `_drawings/`) |
| `--layout` | Yes | Jekyll layout name (e.g., `drawing`) |

**rename_images.py** - Rename date-only images (`YYYY-MM-DD.jpg` → `YYYY-MM-DD_1.jpg`)
```bash
python scripts/rename_images.py --dir <directory>
```
| Argument | Required | Description |
|----------|----------|-------------|
| `--dir` | Yes | Directory containing images to rename |

**convert_to_svg.py** - Batch vectorize images (requires: `brew install imagemagick potrace`)
```bash
python scripts/convert_to_svg.py [--input drawings] [--output svgs] [options]
```
| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | `drawings` | Input directory |
| `--output` | `svgs` | Output directory |
| `--threshold` | `88` | Black/white threshold 0-100 (raise to clean paper, lower if lines break) |
| `--turdsize` | `2` | Speckle filter size in pixels |
| `--alphamax` | `1.0` | Curve smoothness (0.6-0.8 for crisper corners) |
| `--opttol` | `0.2` | Curve optimization tolerance |
| `--overwrite` | `false` | Overwrite existing SVGs |
| `--jobs` | CPU count | Parallel workers |

**convert_to_png.py** - Export SVGs to high-DPI PNG (requires: `brew install imagemagick`)
```bash
python scripts/convert_to_png.py [--input svgs] [--output pngs-for-book] [options]
```
| Argument | Default | Description |
|----------|---------|-------------|
| `--input` | `svgs` | Input directory |
| `--output` | `pngs-for-book` | Output directory |
| `--dpi` | `300` | DPI resolution |
| `--page-width` | `5.83` | Max printed width in inches (A5) |
| `--page-height` | `8.27` | Max printed height in inches (A5) |

Each SVG is rendered from vector (not upscaled) to fit within page-width × page-height at the given DPI, preserving aspect ratio (1749×2481 px max for A5 at 300 DPI). Specific files can be passed as positional args to `convert_to_png.py` (the `cli.py to-png` wrapper converts a whole directory).
| `--overwrite` | `false` | Overwrite existing PNGs |
| `--jobs` | CPU count | Parallel workers |

**build_book.py** - Build a book interior PDF from `books/NAME/book.yml` (requires: `pip install typst pyyaml` in `.venv`, and ImageMagick)
```bash
./scripts/cli.py build-book volume-2              # → book-files/volume-2/interior.pdf
./scripts/cli.py build-book volume-1 --bleed 0.125  # → book-files/volume-1/interior-bleed.pdf
./scripts/cli.py build-book volume-2 --cover kdp    # → book-files/volume-2/cover-kdp.pdf (also: ingram)
./scripts/cli.py build-book volume-2 --cover kdp --guides  # same, with trim/fold/safe-area/barcode guides
```
Covers use `books/shared/cover.typ` (matches the Volume 1 Lulu cover) and the `cover:` drawings in `book.yml`. The spine width comes from the interior page count × 0.002252" (white paper) unless `cover: {spine: {kdp: ..., ingram: ...}}` sets it; use IngramSpark's emailed template value for `ingram`. The build warns if the back drawing runs into the barcode area (bottom corner by the spine).
Layout lives in `books/shared/interior.typ` (Typst; matches the Volume 1 Google Docs layout). Fonts are bundled in `books/shared/fonts/`. Drawings are placed as vector SVGs from `svgs/`, sized and centered by their ink bounds (measured with ImageMagick, cached in `book-files/.ink-bounds.json`; the first build takes ~30s). The publishing plan and launch checklist are in `books/PLAN.md` (local only; gitignored).

**build_epub.py** - Build a reflowable EPUB 3 ebook from `books/NAME/book.yml`
```bash
./scripts/cli.py build-ebook volume-2   # → book-files/volume-2/volume-2.epub and volume-2-cover.jpg
```
One drawing per page, cropped to its ink and saved as a 4-gray PNG fitted to 1200×1600 px (cached in `book-files/NAME/epub-images/`), to keep Kindle's per-MB delivery fee low; the build prints the size and fee. The cover is the front of the KDP paperback cover. Front matter is converted from the Typst markup in `book.yml`; the ebook ISBN comes from `isbn: {ebook: ...}` when set. Validate with EPUBCheck (`brew install epubcheck`) before uploading.

**layout_editor.py** - Adjust drawing sizes and positions in the browser
```bash
./scripts/cli.py layout-editor volume-2   # serves http://127.0.0.1:8765/ and opens it
```
Shows the book as spreads, placed exactly as in the PDF (editor page: `books/shared/layout-editor.html`). Drag to move, scroll to resize; Save writes `scale`/`dx`/`dy` into `book.yml` (keeping its comments), and Build PDF rebuilds the interior.

### Layout Hierarchy

- `default.html` - Base wrapper with OG/Twitter meta tags
- `image.html` - Shared gallery image template (title, tags, social links)
- `drawing.html`, `scribble.html`, `stereoscopic_image.html` - Extend `image.html`
- `tag.html` - Tag index pages with CSS grid gallery

### Content Directories

- `writings/` - Blog posts organized by `YYYY/MM/`
- `images/` - Misc images (logos, photos for articles)
- `svgs/` - Vectorized versions of drawings
- `pngs-for-book/` - High-res exports for print
