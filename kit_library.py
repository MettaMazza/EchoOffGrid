"""Read supported media from the user's OffGrid Kit."""
from html import escape
from hashlib import sha256
import mimetypes
from pathlib import Path
import re
from urllib.parse import quote, unquote

GROUPS = {
    "watch": ("Videos", "04-Entertainment/Video", {".mp4", ".webm", ".ogv", ".m4v"}),
    "shows": ("Shows", "04-Entertainment/Shows", {".mp4", ".webm", ".ogv", ".m4v"}),
    "listen": ("Audio", "04-Entertainment/Audio", {".mp3", ".m4a", ".ogg", ".wav"}),
    "books": ("Books", "04-Entertainment/Books", {".txt", ".pdf"}),
    "guides": ("Guides", "02-Reference", {".txt", ".pdf"}),
    "maps": ("Printable maps", "03-Maps", {".pdf"}),
}


def resolve_asset(root, kind, path):
    if root is None or kind not in GROUPS:
        return None
    _, folder, formats = GROUPS[kind]
    base = (root / folder).resolve()
    try:
        asset = (base / unquote(path)).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if (base.is_relative_to(root) and asset.is_relative_to(base)
            and asset.suffix.lower() in formats and asset.is_file()):
        return asset
    return None


def poster(asset):
    folder = asset.parent / ".thumbnails"
    image = folder / (asset.name + ".jpg")
    if not folder.is_symlink() and not image.is_symlink() and image.is_file():
        return image


def audio_cover(title):
    colour = sha256(title.encode()).digest()[0] % 5
    return (f'<span class="audio-cover tone-{colour}" aria-hidden="true">'
            f'<span class="tape-label">{escape(title)}</span><span class="tape-reels"></span></span>')


def carousel(label, cards, classes, attrs=""):
    if not cards:
        return ""
    name = escape(label, quote=True)
    return (f'<section class="carousel" aria-label="{name}">'
            f'<button class="rail-prev" aria-label="Previous {name}" disabled>‹</button>'
            f'<div class="rail {classes}" tabindex="0" aria-label="{name}" {attrs}>{cards}</div>'
            f'<button class="rail-next" aria-label="Next {name}" disabled>›</button></section>')


def category_grid(label, cards, classes, attrs=""):
    if not cards:
        return ""
    return f'<section class="category-grid {classes}" aria-label="{escape(label,quote=True)}" {attrs}>{cards}</section>'


def kit_cards(root, kind):
    if root is None:
        return
    _, folder, formats = GROUPS[kind]
    base = (root / folder).resolve()
    if not base.is_relative_to(root):
        return
    for path in sorted(base.rglob("*")):
        if any(part.startswith(".") for part in path.relative_to(base).parts) or path.suffix.lower() not in formats:
            continue
        relative = quote(path.relative_to(base).as_posix())
        if not resolve_asset(root, kind, relative):
            continue
        title = escape(path.stem.replace("_", " "))
        extra = audio_cover(path.stem.replace("_", " ")) if kind == "listen" else ""
        if kind in ("watch", "shows"):
            if path.parent != base:
                title = escape(path.parent.name) + " · " + title
            clip = path.parent / ".thumbnails" / (path.name + ".preview.mp4")
            preview = f"/preview/{kind}/{relative}" if clip.is_file() else f"/kit-file/{kind}/{relative}"
            image = f'<img loading=lazy alt="" src="/poster/{kind}/{relative}">' if poster(path) else ""
            extra = f'<span class=thumb data-clip="{escape(preview)}">{image}</span>'
        if kind == "books" and path.suffix.lower() == ".txt":
            with path.open(encoding="utf-8-sig", errors="replace") as stream:
                author = re.search(r"^Author:\s*(.+)$", stream.read(4096), re.M | re.I)
            if author:
                title += f'<small>{escape(author[1].strip())}</small>'
        href = f"/library/{kind}/{relative}"
        yield href, f'<a class=item href="{href}">{extra}<strong>{title}</strong></a>'


def listing(root, kind, limit=None, on_load=False, extra_cards="", layout=carousel):
    from itertools import islice
    cards = "".join(card for _,card in islice(kit_cards(root, kind),limit))
    attrs = f'id="shelf-{kind}" data-on-load' if on_load else ""
    return layout(GROUPS[kind][0], extra_cards + cards, f"shelf {kind}", attrs)


def viewer(kind, relative, asset):
    source = f"/kit-file/{kind}/{relative}"
    source = escape(source, quote=True)
    if kind in ("watch", "shows"):
        image = f' poster="/poster/{kind}/{escape(relative, quote=True)}"' if poster(asset) else ""
        return (f'<video controls playsinline preload="metadata"{image} src="{source}"></video>'
                f'<p><a href="/player/{kind}/{escape(relative, quote=True)}">Play with the in-app VLC player</a></p>')
    if kind == "listen":
        return f'<audio controls preload="metadata" src="{source}"></audio>'
    if asset.suffix.lower() == ".pdf":
        return f'<iframe class=kit-document title="{escape(asset.stem)}" src="{source}"></iframe>'
    with asset.open(encoding="utf-8-sig", errors="replace") as stream:
        text = stream.read(200001)
    return f'<pre class=reader data-source="{source}">{escape(text[:200000])}</pre>' + (
        f'<a href="{source}">Open complete text</a>' if len(text) > 200000 else ""
    )


def send_asset(handler, asset):
    with asset.open("rb") as stream:
        size = stream.seek(0, 2)
        start, end = 0, size - 1
        header = handler.headers.get("Range")
        if header:
            match = re.fullmatch(r"bytes=([0-9]{0,20})-([0-9]{0,20})", header)
            if match and any(match.groups()):
                first, last = match.groups()
                start = int(first) if first else max(0, size - int(last))
                end = min(end, int(last)) if first and last else end
            if not match or not any(match.groups()) or not 0 <= start <= end < size:
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{size}")
                handler.send_header("Content-Length", "0")
                handler.end_headers()
                return
        handler.send_response(206 if header else 200)
        if header:
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Content-Type", mimetypes.guess_type(asset.name)[0] or "application/octet-stream")
        handler.send_header("Content-Length", str(end - start + 1))
        handler.send_header("X-Content-Type-Options", "nosniff")
        handler.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'self'")
        handler.end_headers()
        if handler.command == "HEAD":
            return
        stream.seek(start)
        remaining = end - start + 1
        try:
            while remaining:
                data = stream.read(min(remaining, 256 * 1024))
                if not data:
                    break
                handler.wfile.write(data)
                remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            return
