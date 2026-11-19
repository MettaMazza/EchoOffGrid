"""Content-addressed snapshots and offline search for EchoOffGrid."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import is_zipfile


CATALOG = Path(__file__).with_name("catalog.json")
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=15)
    database.row_factory = sqlite3.Row
    database.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS snapshot (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            rights TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            body BLOB NOT NULL,
            UNIQUE(source, sha256)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(title, body);
        CREATE TABLE IF NOT EXISTS fetch (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            snapshot_id INTEGER REFERENCES snapshot(id),
            error TEXT
        );
    """)
    return database


def eligible(catalog, regions):
    return [source for source in catalog["sources"]
            if set(source["regions"]).intersection(regions)]


def feed_text(content):
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        raise ValueError("Feed contains an unsupported XML declaration")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise ValueError("Expected a well-formed RSS or Atom feed") from error

    atom = "{http://www.w3.org/2005/Atom}"
    if root.tag == atom + "feed":
        parent, prefix, element = root, atom, "entry"
        fields = ("title", "published", "updated", "summary", "content")
    elif root.tag == "rss" and root.find("channel") is not None:
        parent, prefix, element = root.find("channel"), "", "item"
        fields = ("title", "pubDate", "description", "link")
    else:
        raise ValueError("Expected RSS 2.0 or Atom")

    blocks = [parent.findtext(prefix + "title", default="Feed")]
    for entry in parent.findall(prefix + element):
        lines = [entry.findtext(prefix + name, default="").strip() for name in fields]
        if prefix:
            lines.extend(link.get("href", "") for link in entry.findall(prefix + "link")
                         if link.get("rel", "alternate") == "alternate")
        blocks.append("\n".join(line for line in lines if line))
    return "\n\n".join(blocks)


def binary_format(body):
    if body.startswith(b"%PDF-"):
        return "pdf"
    if body.startswith(b"PK") and is_zipfile(BytesIO(body)):
        return "zip"
    return None


def fetch(database, source):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        request = Request(source["url"], headers={"User-Agent": "EchoOffGrid/0.1"})
        with urlopen(request, timeout=20) as response:
            body = response.read(MAX_SNAPSHOT_BYTES + 1)
        if len(body) > MAX_SNAPSHOT_BYTES or not body:
            raise ValueError("Snapshot exceeds the size limit or is empty")
        if source["format"] in {"pdf", "zip"}:
            if binary_format(body) != source["format"]:
                raise ValueError(f'Expected a valid {source["format"].upper()} file')
            decoded = source.get("description", "")
        else:
            decoded = body.decode("utf-8-sig")
            if source["format"] == "json":
                decoded = json.dumps(json.loads(decoded), ensure_ascii=False)
            elif source["format"] == "feed":
                decoded = feed_text(decoded)
            elif decoded.lstrip().lower().startswith(("<html", "<!doctype")):
                raise ValueError("Expected plain text, received an HTML page")
    except (OSError, ValueError) as error:
        with database:
            database.execute("INSERT INTO fetch(source, checked_at, error) VALUES (?, ?, ?)",
                             (source["id"], timestamp, str(error)))
        return {"source": source["id"], "error": str(error)}

    digest = hashlib.sha256(body).hexdigest()
    with database:
        cursor = database.execute(
            "INSERT OR IGNORE INTO snapshot(source,url,title,rights,sha256,body) VALUES (?,?,?,?,?,?)",
            (source["id"], source["url"], source["title"], source["rights"], digest, body),
        )
        if cursor.rowcount:
            database.execute("INSERT INTO search(rowid,title,body) VALUES (?,?,?)",
                             (cursor.lastrowid, source["title"], decoded))
        snapshot = database.execute("SELECT id FROM snapshot WHERE source=? AND sha256=?",
                                    (source["id"], digest)).fetchone()["id"]
        database.execute("INSERT INTO fetch(source,checked_at,snapshot_id) VALUES (?,?,?)",
                         (source["id"], timestamp, snapshot))
    return {"source": source["id"], "snapshot": snapshot, "changed": bool(cursor.rowcount)}


def search(database, phrase):
    words = re.findall(r"\w+", phrase)
    if not words:
        return []
    expression = " AND ".join(f'"{word}"' for word in words)
    return [dict(row) for row in database.execute("""
        SELECT snapshot.id, source, url, snapshot.title, rights, sha256,
               snippet(search, 1, '', '', ' … ', 20) AS excerpt
        FROM search JOIN snapshot ON snapshot.id=search.rowid
        WHERE search MATCH ? ORDER BY rank LIMIT 100
    """, (expression,))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path.home() / "Library/Application Support/EchoOffGrid/archive.sqlite3")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("catalog", "sync"):
        sub = commands.add_parser(name)
        sub.add_argument("--region", action="append", required=True)
        if name == "sync":
            sub.add_argument("--source", action="append", required=True)
    commands.add_parser("search").add_argument("query")
    commands.add_parser("export").add_argument("id", type=int)
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    if args.command in ("catalog", "sync"):
        unknown = set(args.region) - catalog["regions"].keys()
        if unknown:
            parser.error(f"Unknown regions: {', '.join(sorted(unknown))}")
        sources = eligible(catalog, args.region)
        if args.command == "catalog":
            print(json.dumps(sources, indent=2))
            return 0
        missing = set(args.source) - {source["id"] for source in sources}
        if missing:
            parser.error(f"Sources unavailable for selected regions: {', '.join(sorted(missing))}")
    with closing(connect(args.db)) as database:
        if args.command == "sync":
            results = [fetch(database, source) for source in sources if source["id"] in args.source]
            print(json.dumps(results, indent=2))
            return int(any("error" in result for result in results))
        if args.command == "search":
            print(json.dumps(search(database, args.query), indent=2))
        if args.command == "export":
            row = database.execute("SELECT body FROM snapshot WHERE id=?", (args.id,)).fetchone()
            if row is None:
                parser.error("Unknown snapshot ID")
            sys.stdout.buffer.write(row["body"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
