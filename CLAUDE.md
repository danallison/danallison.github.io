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
| `--overwrite` | `false` | Overwrite existing PNGs |
| `--jobs` | CPU count | Parallel workers |

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
