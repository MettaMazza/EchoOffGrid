"""Optional illustrated Kiwix archives, installed locally from first launch."""
import fcntl
import hashlib
from html import escape
from pathlib import Path
from shutil import disk_usage
from threading import Lock, Thread
from time import sleep
from urllib.request import Request, urlopen

EDITIONS = {
    "simple": ("Simple English with images", "wikipedia_en-simple_all_maxi_2026-09.zim",
               3121060947, "2fbdafb57fbf5a43e674b5996319d4a0aebf1b5e5b171566815675e4b3f461af"),
    "full": ("Full English with images", "wikipedia_en_all_maxi_2026-08.zim",
             127418087648, "34162d18b9f96f494eac48a73a309c72e0bc95d85f76be405d0f5de795854aa6"),
}
GIB = 1024**3


class Editions:
    def __init__(self, folder, wiki):
        self.folder, self.wiki = Path(folder), wiki
        self.folder.mkdir(parents=True, exist_ok=True)
        self.choice = self.folder / "edition.txt"
        self.lock = Lock()
        self.message = ""
        self.active = None
        if self.choice.is_file():
            key = self.choice.read_text().strip()
            if key in EDITIONS:
                self.select(key)
            elif key == "starter":
                self.wiki.preferred = self.starter()

    def starter(self):
        return next((p.stem for p in self.wiki.archives if "_mini_" in p.name), None)

    def select(self, key):
        if key not in EDITIONS and key != "starter":
            raise ValueError("Unknown Wikipedia edition")
        with self.lock:
            if self.active:
                raise ValueError("A Wikipedia download is already running.")
            if key in EDITIONS:
                _, name, size, _ = EDITIONS[key]
                ready = any(p.name == name for p in self.wiki.archives)
                part = self.folder / (name + ".part")
                offset = part.stat().st_size if part.exists() else 0
                if not ready and disk_usage(self.folder).free < size - offset + 256*1024**2:
                    self.message = "There is insufficient free space for this edition."
                    return
            pending = self.choice.with_suffix(".tmp")
            pending.write_text(key)
            pending.replace(self.choice)
            self.wiki.preferred = EDITIONS[key][1][:-4] if key in EDITIONS else self.starter()
            self.message = ""
            if key == "starter" or ready:
                return
            self.active = key
            Thread(target=self.download, args=(key,), daemon=True).start()

    def download(self, key):
        _, name, size, digest = EDITIONS[key]
        path = self.folder / (name + ".part")
        guard = self.folder / (name + ".lock")
        with guard.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if not (self.folder / name).exists():
                    self.transfer(name, size, digest, path)
                self.wiki.refresh()
                self.message = "Available offline."
            except BlockingIOError:
                self.message = "Another app window is downloading this edition."
            except Exception as error:
                self.message = f"Download interrupted. Select the edition to retry. {error}"
            finally:
                with self.lock:
                    self.active = None

    def transfer(self, name, size, digest, path):
        offset = path.stat().st_size if path.exists() else 0
        failures = 0
        while offset < size:
            end = min(offset + 32*1024**2, size) - 1
            url = "https://download.kiwix.org/zim/wikipedia/" + name
            request = Request(url, headers={"Range": f"bytes={offset}-{end}"})
            try:
                with urlopen(request, timeout=60) as response:
                    if response.status == 206:
                        expected = f"bytes {offset}-{end}/{size}"
                        if response.headers.get("Content-Range") != expected:
                            raise ValueError("Unexpected archive range")
                    elif response.status == 200 and offset == 0:
                        end = size - 1
                    else:
                        raise ValueError("This mirror cannot resume the archive")
                    with path.open("ab") as dest:
                        for chunk in iter(lambda:response.read(1024*1024), b""):
                            if dest.tell() + len(chunk) > end + 1:
                                raise ValueError("Archive exceeds published range")
                            dest.write(chunk)
                        if dest.tell() != end + 1:
                            raise OSError("Connection ended early")
                failures = 0
                self.message = ""
            except OSError:
                failures += 1
                if failures >= 6:
                    raise
                self.message = "Connection interrupted. Retrying…"
                sleep(min(30, 2**failures))
            offset = path.stat().st_size if path.exists() else 0
        if path.stat().st_size != size:
            raise OSError("Incomplete archive")
        self.message = "Verifying the downloaded archive…"
        checksum = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda:stream.read(4*1024*1024), b""):
                checksum.update(chunk)
        if checksum.hexdigest() != digest:
            path.unlink()
            raise OSError("Checksum mismatch")
        path.replace(self.folder/name)

    def panel(self, token):
        free = disk_usage(self.folder).free
        options = ['<option value="starter">Keep the included starter edition</option>']
        selected = self.choice.read_text().strip() if self.choice.exists() else "starter"
        for key,(label,name,size,_) in EDITIONS.items():
            installed = any(p.name == name for p in self.wiki.archives)
            part = self.folder/(name+".part")
            remaining = size - (part.stat().st_size if part.exists() else 0)
            fits = installed or free >= remaining + 256*1024**2
            status = "installed" if installed else f"{size/GIB:.1f} GiB" + ("" if fits else " · insufficient space")
            options.append(f'<option value="{key}" {"selected" if key == selected else ""} {"" if fits else "disabled"}>{label} · {status}</option>')
        status = self.progress()
        active = self.active
        return (f'<form action="/wiki-edition" method="post"><fieldset><legend>Offline Wikipedia</legend>'
                f'<label>Edition for this device <select name="edition">{"".join(options)}</select></label> '
                f'<input type="hidden" name="token" value="{escape(token)}"><button {"disabled" if active else ""}>Save choice</button>'
                f'<p>{free/GIB:.1f} GiB free on this device. <span id="wiki-progress" data-running="{int(bool(active))}">{escape(status)}</span></p></fieldset></form>')

    def progress(self):
        status = self.message
        active = self.active
        if active:
            _,name,size,_=EDITIONS[active]
            part = self.folder/(name+".part")
            done = part.stat().st_size if part.exists() else 0
            status = f"{done/GIB:.2f} of {size/GIB:.1f} GiB downloaded. " + status
        return status
