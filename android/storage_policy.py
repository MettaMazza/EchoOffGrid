"""Per-device sync intake reserve and cleanup of generated cache files."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import shutil
import sqlite3
import time

GB = 10**9
RESERVE = 20 * GB
MINIMUM = 256 * 1024**2
ALLOWANCE = "sync-allow-until"


def allowance(root):
    try:
        until = float((root / ALLOWANCE).read_text())
        return time.time() < until <= time.time() + 601
    except (OSError, ValueError):
        return False


def capacity(root, explicit=False):
    floor = MINIMUM if explicit or allowance(root) else RESERVE
    return shutil.disk_usage(root).free - floor


def fits(root, size, explicit=False):
    return size >= 0 and size <= capacity(root, explicit)


def saved_art(database):
    links = set()
    if database.is_file():
        with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)) as db:
            for table, query in (("news_story","SELECT link FROM news_story"),
                                 ("discovery_item","SELECT url FROM discovery_item WHERE filename IS NOT NULL")):
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    links.update(row[0] for row in db.execute(query) if row[0])
    return {sha256(link.encode()).hexdigest() for link in links}


def cache_files(root):
    pinned = saved_art(root / "archive.sqlite3")
    for folder, pattern in ((root/"Publisher artwork",r"[0-9a-f]{64}(?:\.miss)?"),
                            (root/"Content"/".thumbnails",r".+\.(?:mp4|m4v|webm|ogv)\.jpg")):
        if folder.is_symlink() or folder.parent.is_symlink() or not folder.is_dir():
            continue
        for p in folder.iterdir():
            if p.name in pinned or p.is_symlink() or not re.fullmatch(pattern,p.name,re.I):
                continue
            try:
                if p.is_file():
                    stat = p.stat()
                    yield stat.st_mtime, stat.st_size, p
            except FileNotFoundError:
                continue


def clean(root, clear=False):
    files = sorted(cache_files(root))
    total = sum(size for _,size,_ in files)
    now = time.time()
    for modified, size, path in files:
        ttl = 900 if path.suffix == ".miss" else 30*86400
        if clear or now-modified > ttl or total > 256*1024**2:
            path.unlink(missing_ok=True)
            total -= size
    return total


def storage_page(root, token):
    free = shutil.disk_usage(root).free
    cache = sum(size for _,size,_ in cache_files(root))
    override = allowance(root)
    state = "Low-space override active" if override else ("Incoming sync paused" if free < RESERVE else "Incoming sync enabled")
    action = "protect" if override else "allow"
    label = "Reinstate 20 GB reserve" if override else "Allow incoming sync for 10 minutes"
    return (f'<section><h3>Storage on this device</h3><p><strong>{free/GB:.1f} GB free</strong> · {state}</p>'
            f'<p>Automatic sync reserves 20 GB. You can temporarily accept transfers below that level.</p>'
            f'<form method="post" action="/storage"><input type="hidden" name="token" value="{token}">'
            f'<button name="action" value="{action}">{label}</button></form>'
            f'<p>Disposable cache · {cache/10**6:.1f} MB. Old browsing artwork and generated thumbnails expire after 30 days. '
            f'The cache budget is 256 MiB. Saved files and their publisher artwork are retained.</p>'
            f'<form method="post" action="/storage"><input type="hidden" name="token" value="{token}">'
            f'<button name="action" value="clean">Clear disposable cache</button></form></section>')
