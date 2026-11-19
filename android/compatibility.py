"""Decide whether a library asset is usable on its destination before transfer."""
from contextlib import closing
from functools import lru_cache
from pathlib import Path
import sqlite3
from zipfile import ZipFile, BadZipFile

MEDIA={".epub",".pdf",".txt",".md",".cbz",".cbr",".mobi",".mp4",".m4v",".mov",".webm",".ogv",".mkv",".avi",".m4a",".mp3",".flac",".ogg",".oga",".wav",".aac",".opus",".jpg",".jpeg",".png",".gif",".webp",".srt",".vtt"}
ROMS={".nes",".fds",".sfc",".smc",".n64",".v64",".z64",".gba",".gb",".gbc",".nds",".sms",".gg",".md",".gen",".a26",".a78",".pce",".chd",".cue",".iso"}
PLATFORM={".apk":"android",".apks":"android",".xapk":"android",".aab":"build",".app":"macos",".dmg":"macos",".pkg":"macos",".ipa":"ios",".msi":"windows",".exe":"windows",".bat":"windows",".appimage":"linux",".deb":"linux",".rpm":"linux",".flatpakref":"linux",".flatpak":"linux"}
def archive_target(names):
    platforms=set()
    for name in names:
        low="/"+name.lower()
        if ".app/contents/" in low:platforms.add("macos")
        if "/payload/" in low and ".app/" in low:platforms.add("ios")
        ext=Path(low).suffix
        if ext in PLATFORM:platforms.add(PLATFORM[ext])
        if low=="/androidmanifest.xml":platforms.add("android")
    if platforms:return platforms
    if any(Path(n).suffix.lower() in ROMS or n.lower().endswith((".html",".htm")) for n in names):return {"android","macos"}
    return set()

@lru_cache(maxsize=1024)
def targets(file,mtime,size,kind,title):
    ext=file.suffix.lower()
    if ext==".apk":
        try:
            with ZipFile(file) as apk:
                names=apk.namelist()
                abi={p.split("/")[1] for p in names if p.startswith("lib/") and p.endswith(".so")}
                if "AndroidManifest.xml" not in names or (abi and "arm64-v8a" not in abi):return set()
        except (BadZipFile,OSError):return set()
    if ext in PLATFORM:
        return {PLATFORM[ext]}
    if ext in MEDIA|ROMS|{".html",".htm",".js",".css",".wasm"}:return {"android","macos"}
    if ext==".zip":
        try:
            with ZipFile(file) as z:return archive_target(z.namelist())
        except (BadZipFile,OSError):return set()
    # Opaque archives and build-source distributions have no verified runtime target.
    return set()

class ContentPolicy:
    def __init__(self,folder,database):
        self.folder=folder
        self.files={}
        self.covers={}
        if database.is_file():
            with closing(sqlite3.connect(database)) as db:
                for key,kind,title,name in db.execute("SELECT id,kind,title,filename FROM discovery_item WHERE filename IS NOT NULL"):
                    self.files[name]=(kind,title)
                    self.covers[key+".cover"]=name
                for name,kind,title in db.execute("SELECT f.filename,i.kind,i.title FROM discovery_file f JOIN discovery_item i ON i.id=f.id"):
                    self.files[name]=(kind,title)
    def allows(self,name,platform):
        name=self.covers.get(name,name)
        if Path(name).name!=name:return False
        file=self.folder/name
        if file.is_symlink() or not file.is_file():return False
        stat=file.stat()
        kind,title=self.files.get(name,("",""))
        return platform in targets(file,stat.st_mtime_ns,stat.st_size,kind,title)
