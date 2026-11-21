"""Stream user-selected files into the local library."""
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import re
import posixpath
import json
import plistlib
import shutil
from xml.etree import ElementTree as ET
from html import escape
from html.parser import HTMLParser
from tempfile import NamedTemporaryFile, TemporaryDirectory
import subprocess
import sys
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from archive import connect

SHELVES={"documents":"Documents","watch":"Films","shows":"Shows","books":"Books","listen":"Audiobooks","games":"Games","software":"Software","pictures":"Pictures","guides":"Guides","maps":"Printable maps"}
FORMATS={
    "Documents":".pdf .txt",
    "Books":".txt .pdf .epub .cbz .cbr .mobi .md",
    "Films":".mp4 .m4v .mov .mkv .webm .ogv .avi","Shows":".mp4 .m4v .mov .mkv .webm .ogv .avi",
    "Audiobooks":".mp3 .m4a .ogg .oga .opus .flac .wav .aac","Pictures":".png .jpg .jpeg .gif .webp",
    "Guides":".pdf .txt .epub .md","Printable maps":".pdf .png .jpg .jpeg .webp",
}
KINDS=set(SHELVES.values())
IMAGE_LIMIT = 8 * 1024 * 1024

def image_format(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"

def epub_index(z):
    def xml(name,limit=1024*1024):
        if z.getinfo(name).file_size > limit: raise ValueError("Oversized publication index")
        return ET.fromstring(z.read(name))
    package=xml("META-INF/container.xml").find(".//{*}rootfile").attrib["full-path"]
    document=xml(package)
    items={i.get("id"): (posixpath.normpath(posixpath.join(posixpath.dirname(package),unquote(i.get("href","")))),i)
           for i in document.findall(".//{*}manifest/{*}item")}
    return document,items

class ChapterText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text=[]
        self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {"head","script","style"}:self.skip+=1
        if tag in {"p","div","br","h1","h2","h3","li"}:self.text.append("\n")
    def handle_endtag(self,tag):
        if tag in {"head","script","style"}:self.skip=max(0,self.skip-1)
    def handle_data(self,text):
        if not self.skip:self.text.append(text)

def epub_page(path,key,n):
    try:
        with ZipFile(path) as z:
            doc,items=epub_index(z)
            spine=[items[i.get("idref")][0] for i in doc.findall(".//{*}spine/{*}itemref") if i.get("idref") in items]
            if not 0<=n<len(spine) or z.getinfo(spine[n]).file_size>4*1024*1024:raise ValueError()
            parser=ChapterText()
            parser.feed(z.read(spine[n]).decode("utf-8","replace"))
            words="".join(parser.text).splitlines()
            nav=" ".join(f'<a href="/content/{key}?chapter={i}">{label}</a>' for i,label in [(n-1,"Previous"),(n+1,"Next")] if 0<=i<len(spine))
            return f'<nav class=pills>{nav}<small>Chapter {n+1} of {len(spine)}</small></nav><article class=reader>'+''.join("<p>"+escape(w.strip())+"</p>" for w in words if w.strip())+'</article>'
    except (BadZipFile,KeyError,ValueError,AttributeError,ET.ParseError,RuntimeError,OSError,NotImplementedError):
        return "<p>This edition needs an external EPUB reader.</p>"

def artwork(path):
    if path.suffix in {".epub", ".apk", ".zip", ".jar"}:
        try:
            with ZipFile(path) as archive:
                if path.suffix==".epub":
                    try:
                        doc,items=epub_index(archive)
                        ids={m.get("content") for m in doc.findall(".//{*}meta") if m.get("name")=="cover"}
                        for key,(name,item) in items.items():
                            if key in ids or "cover-image" in item.get("properties","").split():
                                if archive.getinfo(name).file_size<=IMAGE_LIMIT:
                                    data=archive.read(name)
                                    if image_format(data):return data
                    except (KeyError,ValueError,AttributeError,ET.ParseError):
                        pass
                files = [f for f in archive.infolist() if 0 < f.file_size <= IMAGE_LIMIT
                         and re.search(r"(cover|front|ic_launcher|icon|poster|folder).*\.(png|jpe?g|webp)$", Path(f.filename).name, re.I)]
                if path.suffix==".zip" and sys.platform=="darwin":
                    icons=[f for f in archive.infolist() if ".app/Contents/Resources/" in f.filename and f.filename.lower().endswith(".icns") and f.file_size<=IMAGE_LIMIT]
                    if icons:
                        with TemporaryDirectory() as folder:
                            icon=Path(folder)/"app.icns"
                            icon.write_bytes(archive.read(icons[0]))
                            png=icon.with_suffix(".png")
                            try:
                                subprocess.run(["/usr/bin/sips","-s","format","png","-Z","360",icon,"--out",png],check=True,timeout=8,capture_output=True)
                                return png.read_bytes()
                            except (OSError,subprocess.SubprocessError):
                                pass
                for f in sorted(files, key=lambda x: ("cover" not in x.filename.lower(), -x.file_size)):
                    data = archive.read(f)
                    if image_format(data):
                        return data
        except (BadZipFile, OSError, RuntimeError, ValueError, NotImplementedError):
            pass
    if path.suffix in {".mp3", ".m4a", ".flac"}:
        with path.open("rb") as src:
            header = src.read(IMAGE_LIMIT)
        for start, end in [(b"\xff\xd8\xff",b"\xff\xd9"),(b"\x89PNG\r\n\x1a\n",b"IEND\xaeB`\x82")]:
            a = header.find(start)
            b = header.find(end, a + len(start)) if a >= 0 else -1
            if b >= 0:
                return header[a:b+len(end)]

def save(handler, kind, name):
    name = Path(unquote(name)).name.strip()
    suffix = Path(name).suffix.lower()
    if suffix==".cover" or kind not in KINDS or not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix) or len(name)>255:
        raise ValueError("Choose a category and a file with an extension.")
    if kind in FORMATS and suffix not in FORMATS[kind].split():
        raise ValueError("That file type does not belong on this shelf.")
    root = handler.server.database.parent / "Content"
    root.mkdir(exist_ok=True)
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        raise ValueError("This file is empty.")
    digest = sha256(kind.encode()+b"\0")
    with NamedTemporaryFile(dir=root,prefix=".import-",delete=False) as tmp:
        temp = Path(tmp.name)
        try:
            while length:
                chunk = handler.rfile.read(min(length, 1024*1024))
                if not chunk:
                    raise ValueError("File transfer interrupted.")
                tmp.write(chunk)
                digest.update(chunk)
                length -= len(chunk)
            tmp.close()
            key = "personal-"+digest.hexdigest()
            path = root / (key+suffix)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    label=""
    title=Path(name).stem
    if path.suffix in {".epub",".zip"}:
        try:
            with ZipFile(path) as z:
                if path.suffix==".epub":
                    doc,_=epub_index(z)
                    title=doc.findtext(".//{*}metadata/{*}title") or title
                else:
                    entry=next((f for f in z.infolist() if f.filename.endswith(".app/Contents/Info.plist") and f.file_size<=1024*1024),None)
                    if entry:
                        info=plistlib.loads(z.read(entry))
                        label="Mac application"
                        title=info.get("CFBundleDisplayName") or info.get("CFBundleName") or title.removesuffix(".app")
        except (BadZipFile,KeyError,ValueError,RuntimeError,AttributeError,ET.ParseError,plistlib.InvalidFileException):pass
    image = artwork(path)
    if image:
        write_cover(root,key,image)
    helper=Path(__file__).with_name("make-poster")
    if sys.platform=="darwin" and helper.is_file() and suffix in {".pdf",".mp3",".m4a",".flac",".mp4",".mov",".m4v",".aac",".aiff",".wav"}:
        try:
            native=subprocess.run([helper,"--metadata",path,root/(key+".cover")],capture_output=True,text=True,timeout=15,check=True)
            title=native.stdout.strip() or title
        except (OSError,ValueError,subprocess.SubprocessError):pass
    with closing(connect(handler.server.database)) as db, db:
        db.execute("""INSERT OR IGNORE INTO discovery_item
            (id,kind,title,preview,rights,url,ext,provider,filename) VALUES(?,?,?,?,'Personal library','',?,'Personal library',?)""",
            (key,kind,str(title)[:400],label,suffix,path.name))
    return key

def write_cover(root,key,data):
    suffix = image_format(data)
    if not suffix:
        raise ValueError("Choose a PNG, JPEG or WebP cover.")
    # Detect the format from bytes when serving. A single path also syncs cover replacements.
    with NamedTemporaryFile(dir=root,prefix=".cover-",delete=False) as f:
        f.write(data)
        temp = Path(f.name)
    temp.replace(root/(key+".cover"))

def seed_pictures(db,folder):
    source=Path(__file__).parent/"vendor/picture-samples"
    dest=folder/"Content"
    dest.mkdir(exist_ok=True)
    for photo in json.loads((source/"credits.json").read_text()):
        name=photo["file"]
        key=sha256(photo["source"].encode()).hexdigest()
        if db.execute("SELECT 1 FROM removed_item WHERE id=?",(key,)).fetchone():continue
        filename=key+".jpg"
        if not (dest/filename).exists():
            with NamedTemporaryFile(dir=dest,delete=False) as out, (source/name).open("rb") as inp:
                shutil.copyfileobj(inp,out)
            Path(out.name).replace(dest/filename)
        db.execute("""INSERT OR IGNORE INTO discovery_item(id,kind,title,preview,rights,url,ext,provider,filename)
            VALUES(?,'Pictures',?,'',?,? ,'.jpg','Wikimedia Commons',?)""",
            (key,photo["title"],photo["artist"]+" · "+photo["license"]+" · "+photo["source"],photo["original"],filename))

def seed_empty_shelves(db, folder, kit):
    from kit_library import GROUPS
    source = Path(__file__).parent / "vendor/library-samples"
    destination = folder / "Content"
    samples = [
        ("books", "book.txt", "Dracula", "Bram Stoker · Project Gutenberg #345 · Terms included in the book"),
        ("listen", "audio.mp3", "A Scandal in Bohemia · opening excerpt", "LibriVox volunteers · Public domain in the US · librivox.org"),
        ("watch", "film.mp4", "Big Buck Bunny · preview", "Blender Foundation / Peach Open Movie Project · CC BY 3.0 · peach.blender.org"),
        ("shows", "show.mp4", "Caminandes 2, Gran Dillama · preview", "Blender Foundation and Caminandes team · CC BY · studio.blender.org/films/caminandes-2/"),
        ("games", "game.html", "Lights Out", "EchoOffGrid · Included puzzle"),
        ("guides", "guide.txt", "Getting started offline", "EchoOffGrid · Included guide"),
        ("maps", "map.pdf", "World reference map", "Natural Earth · Public domain · naturalearthdata.com"),
    ]
    for shelf, asset, title, rights in samples:
        kind = SHELVES[shelf]
        if db.execute("SELECT 1 FROM discovery_item WHERE kind=? AND filename IS NOT NULL LIMIT 1", (kind,)).fetchone():
            continue
        if kit:
            _, subdir, formats = GROUPS.get(shelf, ("Games", "04-Entertainment/Games/Browser Puzzles", {".wasm"}))
            base = kit / subdir
            if any(p.suffix.lower() in formats and p.is_file() and not any(part.startswith(".") for part in p.relative_to(base).parts) for p in base.rglob("*")):
                continue
        key = sha256(("EchoOffGrid starter " + asset).encode()).hexdigest()
        if db.execute("SELECT 1 FROM removed_item WHERE id=?",(key,)).fetchone():continue
        suffix = Path(asset).suffix
        filename = key + suffix
        with NamedTemporaryFile(dir=destination, delete=False) as tmp, (source / asset).open("rb") as sample:
            shutil.copyfileobj(sample, tmp)
        Path(tmp.name).replace(destination / filename)
        db.execute("""INSERT OR IGNORE INTO discovery_item(id,kind,title,preview,rights,url,ext,provider,filename)
                      VALUES(?,?,?,'',?,'',?,'Offline sample',?)""", (key,kind,title,rights,suffix,filename))
