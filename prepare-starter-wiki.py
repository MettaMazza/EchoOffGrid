"""Prepare the verified Simple English Wikipedia archive for an offline release."""
import argparse
from hashlib import sha256
from pathlib import Path
import os
from shutil import copyfile
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

NAME = "wikipedia_en-simple_all_mini_2026-09.zim"
SIZE = 530482005
DIGEST = "a6a56861f8dedca2e2434d921c61c74e552c80310623173b1ec31e80ce1a692e"
URL = "https://download.kiwix.org/zim/wikipedia/" + NAME

def verify(path):
    if not path.is_file() or path.stat().st_size != SIZE:
        return False
    checksum = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            checksum.update(block)
    return checksum.hexdigest() == DIGEST

def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / NAME
    if verify(output):
        return output
    source = os.environ.get("ECHO_STARTER_ZIM")
    with NamedTemporaryFile(dir=folder, delete=False) as stream:
        partial = Path(stream.name)
    try:
        if source:
            copyfile(source, partial)
        else:
            from shutil import copyfileobj
            with urlopen(URL, timeout=60) as response, partial.open("wb") as dest:
                copyfileobj(response, dest, 1024*1024)
        if not verify(partial):
            raise ValueError("Wikipedia archive failed size or checksum verification")
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder",type=Path)
    print(prepare(parser.parse_args().folder))
