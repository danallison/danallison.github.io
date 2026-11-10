#!/usr/bin/env python3
"""Interactive page layout editor for a book's drawings.

Serves books/shared/layout-editor.html on localhost and opens it in the browser. Drag
drawings to move them, scroll to resize, then save: the per-drawing `scale`, `dx` and `dy`
(or `width`, for entries that already set one) are written back into books/NAME/book.yml.

Usage:
    python layout_editor.py NAME [--port PORT] [--no-browser]

Arguments:
    NAME          Book directory under books/ (e.g. volume-2)
    --port        Port to listen on (default: 8765)
    --no-browser  Don't open the editor in a browser
"""

import argparse
import json
import mimetypes
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from build_book import DEFAULT_SIZING, REPO, build, load_ink_bounds, resolve_image

EDITOR = REPO / 'books' / 'shared' / 'layout-editor.html'
# Only these paths are served as static files.
STATIC_PREFIXES = ('svgs/', 'books/shared/', 'book-files/')


def book_path(name: str) -> Path:
    return REPO / 'books' / name / 'book.yml'


def editor_data(name: str) -> dict:
    """The book's drawings with everything the editor needs to place them like the PDF does."""
    book = yaml.safe_load(book_path(name).read_text())
    sizing = {**DEFAULT_SIZING, **book.get('sizing', {})}
    entries = [{'id': e} if isinstance(e, str) else e for e in book['drawings']]
    svgs = [REPO / 'svgs' / f"{e['id']}.svg" for e in entries]
    bounds = load_ink_bounds(svgs) if sizing['crop'] else {}
    drawings = []
    for e, svg in zip(entries, svgs):
        path = f"/svgs/{e['id']}.svg"
        crop = bounds.get(svg)
        placed = resolve_image(path, e, sizing, crop)
        drawings.append({
            'id': e['id'],
            'path': path,
            'crop': crop or [0, 0, 1, 1],
            'aspect': placed['width'] / placed['height'],
            'base_width': resolve_image(path, {}, sizing, crop)['width'],
            'width': placed['width'],
            'dx': placed['dx'],
            'dy': placed['dy'],
            'mode': 'width' if 'width' in e or 'height' in e else 'scale',
        })
    return {'name': name, 'title': book['title'], 'trim': book['trim'], 'sizing': sizing,
            'drawings': drawings}


def number(v: float, places: int) -> str:
    return f"{round(v, places):.{places}f}".rstrip('0').rstrip('.')


def yaml_scalar(s: str) -> str:
    """Quote a string only if YAML would read it back as something else (e.g. a date)."""
    try:
        if yaml.safe_load(s) == s:
            return s
    except yaml.YAMLError:
        pass
    return json.dumps(s)


def entry_line(entry: dict) -> str:
    """Format one drawings entry as a list item, as a bare id when there are no overrides."""
    if set(entry) == {'id'}:
        return f"  - {yaml_scalar(entry['id'])}\n"
    parts = [f"{k}: {yaml_scalar(v) if isinstance(v, str) else v}" for k, v in entry.items()]
    return "  - {" + ", ".join(parts) + "}\n"


def save_layout(name: str, layout: list) -> None:
    """Write edited sizes and offsets into book.yml, keeping its comments and other keys."""
    path = book_path(name)
    data = editor_data(name)
    if [d['id'] for d in layout] != [d['id'] for d in data['drawings']]:
        raise ValueError("book.yml's drawings changed since the editor loaded; reload and redo")
    book = yaml.safe_load(path.read_text())
    entries = [{'id': e} if isinstance(e, str) else dict(e) for e in book['drawings']]

    for entry, edit, current in zip(entries, layout, data['drawings']):
        for key in ('width', 'height', 'scale', 'dx', 'dy'):
            entry.pop(key, None)
        if current['mode'] == 'width':
            entry['width'] = float(number(edit['width'], 4))
        else:
            scale = float(number(edit['width'] / current['base_width'], 3))
            if scale != 1:
                entry['scale'] = scale
        for key in ('dx', 'dy'):
            v = float(number(edit[key], 3))
            if v:
                entry[key] = v

    lines = path.read_text().splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if re.match(r'drawings:\s*$', line)) + 1
    items = iter(entries)
    for i in range(start, len(lines)):
        if lines[i].startswith('  - '):
            lines[i] = entry_line(next(items))
        elif lines[i].strip() and not lines[i].startswith((' ', '#')):
            break  # next top-level key
    path.write_text(''.join(lines))


class Handler(BaseHTTPRequestHandler):
    book = None

    def send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, status: int = 200):
        self.send(status, json.dumps(obj).encode(), 'application/json')

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == '/':
            return self.send(200, EDITOR.read_bytes(), 'text/html; charset=utf-8')
        if path == '/api/book':
            return self.send_json(editor_data(self.book))
        rel = path.lstrip('/')
        file = (REPO / rel).resolve()
        if (rel.startswith(STATIC_PREFIXES) and file.is_relative_to(REPO) and '..' not in rel
                and file.is_file()):
            ctype = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
            return self.send(200, file.read_bytes(), ctype)
        self.send(404, b'Not found', 'text/plain')

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == '/api/book':
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                save_layout(self.book, body['drawings'])
                return self.send_json(editor_data(self.book))
            if path == '/api/build':
                out = build(self.book)
                return self.send_json({'pdf': '/' + str(out.relative_to(REPO))})
        except Exception as e:
            return self.send_json({'error': str(e)}, 400)
        self.send(404, b'Not found', 'text/plain')

    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet


def main():
    parser = argparse.ArgumentParser(description='Interactive page layout editor for a book')
    parser.add_argument('name', help='Book directory under books/ (e.g. volume-2)')
    parser.add_argument('--port', type=int, default=8765, help='Port (default: 8765)')
    parser.add_argument('--no-browser', action='store_true', help="Don't open a browser")
    args = parser.parse_args()

    if not book_path(args.name).exists():
        sys.exit(f"No such book: {book_path(args.name).relative_to(REPO)}")
    editor_data(args.name)  # measure any new ink bounds before the browser asks
    Handler.book = args.name
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Layout editor for {args.name} at {url} (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
