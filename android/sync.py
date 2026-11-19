"""Mirror the portable kit to a paired Android device over USB or wireless ADB."""
import argparse
import hashlib
from pathlib import Path
import shlex
import sqlite3
import subprocess
import tempfile
from storage_policy import MINIMUM, RESERVE
from compatibility import ContentPolicy

ROOT = "/sdcard/Android/data/dev.echooffgrid.mobile/files/"
TYPES = {".txt", ".pdf", ".zim", ".pmtiles", ".js", ".css", ".json", ".pbf", ".png", ".jpg", ".html", ".wasm", ".mp3", ".ogg", ".wav", ".m4a", ".mp4", ".m4v", ".webm", ".ogv"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True, help="USB serial or paired wireless ADB endpoint")
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--dictionary", type=Path)
    parser.add_argument("--allow-low-space", action="store_true", help="Explicitly allow this USB import below the 20 GB reserve")
    args = parser.parse_args()
    adb = [args.adb, "-s", args.serial]

    def shell(*words, check=True):
        return subprocess.run(adb + ["shell", shlex.join(words)], check=check, capture_output=True, text=True)

    def send(source, destination):
        # Keep interrupted transfers invisible to the reader and keep existing files usable.
        target = ROOT + destination
        partial = target + ".partial"
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
                digest.update(chunk)
        def matches(remote):
            result = shell("sha256sum", remote, check=False)
            return result.returncode == 0 and result.stdout.split()[0] == digest.hexdigest()
        if matches(target):
            return
        report = shell("df", "-k", ROOT).stdout.splitlines()[-1].split()
        floor = MINIMUM if args.allow_low_space else RESERVE
        if int(report[3])*1024 - source.stat().st_size < floor:
            raise RuntimeError("Incoming USB sync paused for available storage")
        shell("mkdir", "-p", target.rsplit("/", 1)[0])
        subprocess.run(adb + ["push", str(source), partial], check=True, stdout=subprocess.DEVNULL)
        if not matches(partial):
            raise RuntimeError("Incomplete transfer of " + source.name)
        shell("mv", "-f", partial, target)
        print(destination, flush=True)

    files = []
    for group in ("02-Reference", "03-Maps", "04-Entertainment"):
        for file in (args.kit / group).rglob("*"):
            if any(part.endswith(".app") for part in file.parts):
                continue
            if file.is_file() and file.resolve().is_relative_to(args.kit.resolve()) and file.suffix.lower() in TYPES:
                files.append((file, "Kit/" + file.relative_to(args.kit).as_posix()))
    if args.dictionary:
        files.append((args.dictionary, "library/dictionary.sqlite3"))
    if args.archive:
        policy=ContentPolicy(args.archive.parent/"Content",args.archive)
        for file in (args.archive.parent / "Content").glob("*"):
            if file.is_file() and not file.is_symlink() and policy.allows(file.name,"android"):
                files.append((file, "Content/" + file.name))
    if args.archive:
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "desktop.sqlite3"
            with sqlite3.connect(args.archive.resolve().as_uri()+"?mode=ro", uri=True) as src, sqlite3.connect(snapshot) as dst:
                src.backup(dst)
            send(snapshot, "desktop.sqlite3")

    for file, destination in sorted(files, key=lambda pair:(pair[0].stat().st_size < 100000, pair[0].stat().st_size)):
        send(file, destination)

if __name__ == "__main__":
    main()
