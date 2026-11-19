"""Build an EchoLite schema-1 dictionary from a public Wiktextract JSONL dump."""
import argparse
from contextlib import closing
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unicodedata
from urllib.request import Request, urlopen
import zlib


STARTER_URL = "https://kaikki.org/dictionary/downloads/simple/simple-extract.jsonl.gz"
MAX_RECORD = 2 * 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(source, output, source_date, source_url):
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Choose a new output file: {output}")
    source_hash = sha256_file(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".echolite-dictionary-", dir=output.parent) as staging:
        database_path = Path(staging) / "dictionary.sqlite3"
        with closing(sqlite3.connect(database_path)) as db:
            db.executescript("""
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE entries(id INTEGER PRIMARY KEY,word TEXT NOT NULL,
                    normalized TEXT NOT NULL,pos TEXT NOT NULL,payload BLOB NOT NULL);
            """)
            opener = gzip.open if source.suffix == ".gz" else open
            count = skipped = 0
            with opener(source, "rb") as incoming, db:
                for line in incoming:
                    if not line.strip():
                        continue
                    if len(line) > MAX_RECORD:
                        skipped += 1
                        continue
                    record = json.loads(line)
                    if record.get("lang_code") != "en":
                        continue
                    word = record.get("word")
                    pos = record.get("pos")
                    if not isinstance(word, str) or not isinstance(pos, str) or not word.strip():
                        skipped += 1
                        continue
                    normalized = unicodedata.normalize("NFKC", word.strip()).casefold()
                    payload = zlib.compress(line)
                    if len(payload) > MAX_RECORD:
                        skipped += 1
                        continue
                    db.execute("INSERT INTO entries(word,normalized,pos,payload) VALUES (?,?,?,?)",
                               (word, normalized, pos, payload))
                    count += 1
                if not count:
                    raise ValueError("No English Wiktextract entries found")
                db.execute("CREATE INDEX entries_word ON entries(normalized)")
                db.executemany("INSERT INTO metadata VALUES (?,?)", {
                    "status": "ready", "schema": "1", "source_date": source_date,
                    "source_url": source_url, "source_sha256": source_hash,
                    "builder_sha256": sha256_file(Path(__file__)),
                    "attribution": "Wiktionary contributors; extracted with Wiktextract via kaikki.org",
                    "license": "CC BY-SA 4.0; see Wiktionary for exceptions",
                    "license_url": "https://en.wiktionary.org/wiki/Wiktionary:Copyrights",
                }.items())
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Dictionary integrity check failed")
        os.link(database_path, output)
    return count, skipped


def starter(output, source_date):
    with tempfile.TemporaryDirectory(prefix="echolite-dictionary-source-") as staging:
        path = Path(staging) / "starter.jsonl.gz"
        with urlopen(Request(STARTER_URL, headers={"User-Agent": "EchoOffGrid/0.1"}), timeout=30) as response, path.open("wb") as target:
            limit = 64 * 1024 * 1024
            while chunk := response.read(1024 * 1024):
                limit -= len(chunk)
                if limit < 0:
                    raise ValueError("Starter dictionary download exceeds 64 MiB")
                target.write(chunk)
        return build(path, output, source_date, STARTER_URL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--jsonl", type=Path, help="Local .jsonl or .jsonl.gz data")
    choice.add_argument("--download-simple", action="store_true", help="Fetch the small Simple English edition")
    parser.add_argument("--source-date", default="unknown")
    parser.add_argument("--source-url", default="https://kaikki.org/dictionary/rawdata.html")
    args = parser.parse_args()
    try:
        if args.download_simple:
            count, skipped = starter(args.output, args.source_date)
        else:
            count, skipped = build(args.jsonl, args.output, args.source_date, args.source_url)
    except (OSError, ValueError, AttributeError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")
    print(f"Built {args.output}: {count} English entries, {skipped} skipped")


if __name__ == "__main__":
    main()
