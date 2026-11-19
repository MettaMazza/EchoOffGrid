"""Install pinned Kokoro weights and the CPython 3.11 Apple Silicon speech engine."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from zipfile import ZipFile
from urllib.request import urlopen

MODEL = "kokoro-int8-multi-lang-v1_0"
WHEELS = {
    "sherpa_onnx-1.12.30-cp311-cp311-macosx_11_0_arm64.whl": "c8fdab047a8ea9a4061effe8334592cfa93f05ceb7a30e35fdad0e14d9817c11",
    "sherpa_onnx_core-1.12.30-py3-none-macosx_11_0_arm64.whl": "113dad83fd0e66bf59bad482f5378cbc4984fed91cfa747ff6e0247e4c7e966c",
}


def checked(path, digest, url):
    if not path.is_file():
        partial = path.with_suffix(".part")
        subprocess.run(["curl", "-fL", "--retry", "2", "-o", str(partial), url()], check=True)
        partial.replace(path)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise ValueError(f"Checksum mismatch: {path}")


def install(cache, output):
    cache.mkdir(exist_ok=True, parents=True)
    for name, digest in WHEELS.items():
        def wheel_url():
            package = name.split("-")[0]
            with urlopen(f"https://pypi.org/pypi/{package}/1.12.30/json", timeout=30) as response:
                return next(x["url"] for x in json.load(response)["urls"] if x["filename"] == name)
        checked(cache/name, digest, wheel_url)
        with ZipFile(cache/name) as archive:
            archive.extractall(output/"runtime")
    checked(cache/"voice.tar.bz2", "72c347230107ef8a31098ec4d468a605244beef5f1ed00db97efa13518800653",
            lambda: f"https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/{MODEL}.tar.bz2")
    keep = {"model.int8.onnx", "tokens.txt", "lexicon-gb-en.txt", "voices.bin", "espeak-ng-data", "LICENSE", "README.md"}
    with tarfile.open(cache/"voice.tar.bz2") as archive:
        for entry in archive:
            parts = Path(entry.name).parts
            if len(parts)<2 or parts[0]!=MODEL or parts[1] not in keep or not entry.isfile() or ".." in parts:
                continue
            target = output/"model"/Path(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(entry) as source, target.open("wb") as dest:
                shutil.copyfileobj(source,dest)


if __name__ == "__main__":
    install(Path(sys.argv[1]), Path(sys.argv[2]))
