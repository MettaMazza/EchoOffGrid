"""Register existing offline reference files for EchoLite without copying them."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import struct
import uuid


def wikipedia_manifest(archive, source_url):
    if archive.suffix != ".zim" or ".." in archive.name:
        raise ValueError("Choose a regular ZIM file with a simple .zim filename")
    with archive.open("rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("The ZIM must be a regular file")
        header = stream.read(80)
        if len(header) != 80 or header[:4] != b"ZIM\x04":
            raise ValueError("Invalid ZIM header")
        position = struct.unpack_from("<Q", header, 72)[0]
        if not 80 <= position <= info.st_size - 16:
            raise ValueError("Invalid ZIM checksum position")
        stream.seek(position)
        checksum = stream.read(16)
        if len(checksum) != 16:
            raise ValueError("Could not read the ZIM checksum")
        final = os.fstat(stream.fileno())
        if (info.st_size, info.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError("The ZIM changed during registration")
    month = re.search(r"_(\d{4}-\d{2})\.zim$", archive.name)
    return {
        "file": archive.name,
        "bytes": info.st_size,
        "mtime_ns": info.st_mtime_ns,
        "uuid": str(uuid.UUID(bytes=header[8:24])),
        "checksum": checksum.hex(),
        "source_date": month.group(1) if month else "unknown",
        "source_url": source_url,
    }


def check_dictionary(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as database:
        metadata = dict(database.execute("SELECT key,value FROM metadata"))
        database.execute("SELECT id,word,pos,payload FROM entries LIMIT 0")
    if (metadata.get("status"), str(metadata.get("schema"))) != ("ready", "1"):
        raise ValueError("Dictionary is not a ready EchoLite schema 1 database")
    if not all(metadata.get(key) for key in ("source_sha256", "builder_sha256")):
        raise ValueError("Dictionary source or builder provenance is missing")


def register(output, archive, dictionary, source_url):
    archive = archive.resolve(strict=True)
    dictionary = dictionary.resolve(strict=True)
    manifest = wikipedia_manifest(archive, source_url)
    check_dictionary(dictionary)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        (output / archive.name).symlink_to(archive)
        (output / "dictionary.sqlite3").symlink_to(dictionary)
        (output / "wikipedia.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except OSError:
        shutil.rmtree(output)
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="Use a new path, usually ASSET_ROOT/library")
    parser.add_argument("zim", type=Path)
    parser.add_argument("dictionary", type=Path)
    parser.add_argument("--source-url", default="https://download.kiwix.org/zim/wikipedia/")
    args = parser.parse_args()
    try:
        manifest = register(args.library, args.zim, args.dictionary, args.source_url)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"{error}\n")
    print(f"Registered {manifest['file']} ({manifest['uuid']}) in {args.library}")


if __name__ == "__main__":
    main()
