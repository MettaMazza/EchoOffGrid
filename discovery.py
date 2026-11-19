"""Search public catalogues and keep user-selected files on disk."""
import csv
import gzip
import hashlib
from threading import Lock
import json
from pathlib import Path
import re
import shutil
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

KINDS = {"Pictures":"image","Games":"software","Books": "texts", "Films": "movies", "Shows": "movies", "Audiobooks": "audio", "Software": "software"}
PICKS = {"Pictures":["Aberdeen","Aurora","Moon"],"Games":["puzzle","platformer","chess"],"Books": ["Pride and Prejudice", "Frankenstein", "Treasure Island"], "Films": ["Big Buck Bunny", "Elephants Dream", "Sintel"], "Shows": ["Tales of Tomorrow", "Space", "Classic television"], "Audiobooks": ["Sherlock Holmes", "Jane Eyre"], "Software": ["ripgrep", "pandoc", "sqlite"]}


ZIP_URL = "https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js"
ZIP_DIGEST = "acc7e41455a80765b5fd9c7ee1b8078a6d160bbbca455aeae854de65c947d59e"
ZIP_ID = hashlib.sha256(ZIP_URL.encode()).hexdigest()

INSTALLERS = {
    "LocalSend": ("https://github.com/localsend/localsend/releases/download/v1.18.2/LocalSend-1.18.2.dmg", "Apache-2.0", "Share files over a local network. macOS installer.", "126860d56f6f49b11845f601aac51de27a49b16d2b48102415da91e0e37e5155"),
    "SuperTux": ("https://github.com/SuperTux/supertux/releases/download/v0.7.0/SuperTux-v0.7.0-Darwin-arm64.dmg", "GPL-3.0-or-later", "Side-scrolling platform game. Apple Silicon installer.", "670e17dec1d74cd8b0ee961e4c9b18a5a9921416a3f311352bd4b607b1bcdf15"),
}


def featured(kind):
    if kind in ("Games","Pictures"):return []
    if kind == "Software":
        inspector = dict(id=ZIP_ID,kind=kind,title="JSZip · ZIP inspector",preview="Open a local ZIP to browse its files inside EchoOffGrid.",rights="MIT or GPL-3.0-or-later",url=ZIP_URL,ext=".js",provider="In-app tool")
        return [inspector] + [dict(id=hashlib.sha256(url.encode()).hexdigest(),kind=kind,title=title,preview=desc,rights=rights,url=url,ext=".dmg",provider="Official installer")
                for title,(url,rights,desc,_) in INSTALLERS.items()]
    if kind == "Books":
        catalog=json.loads(Path(__file__).with_name("catalog.json").read_text())
        return [dict(id=hashlib.sha256(x["url"].encode()).hexdigest(),kind=kind,title=x["title"],preview="Project Gutenberg · downloadable plain text",rights=x["rights"],url=x["url"],ext=".txt",provider="Project Gutenberg") for x in catalog["sources"] if x["kind"]=="Books"][:4]
    titles={
        "Films":[("Sintel","Sintel","http://creativecommons.org/licenses/by/3.0/","Blender Foundation’s open animated short."),("Elephants Dream","ElephantsDream","http://creativecommons.org/licenses/by/3.0/us/","An animated journey through a machine.")],
        "Shows":[("Tales of Tomorrow · Ice from Space","TalesOfTomorrow-IceFromSpace","http://creativecommons.org/licenses/publicdomain/","An episode of the early science-fiction television series.")],
        "Audiobooks":[("Treasure Island","treasureisland_librivox","http://creativecommons.org/licenses/publicdomain/","Robert Louis Stevenson · LibriVox recording.")]}
    items=[]
    for title,identifier,rights,desc in titles[kind]:
        url="https://archive.org/metadata/"+identifier
        items.append(dict(id=hashlib.sha256(url.encode()).hexdigest(),kind=kind,title=title,preview=desc,rights=rights,url=url,ext="",provider="Internet Archive"))
    return items


def metadata(url):
    with urlopen(Request(url, headers={"User-Agent":"EchoOffGrid/1.0"}), timeout=15) as response:
        return json.loads(response.read(10_000_000))


def clean(value):
    if isinstance(value, list):
        value = " · ".join(str(x) for x in value)
    return " ".join(re.sub("<[^>]*>", " ", str(value or "")).split())


def public_license(url):
    parsed = urlsplit(str(url))
    return parsed.hostname in ("creativecommons.org","www.creativecommons.org") and parsed.path.startswith(("/licenses/", "/publicdomain/"))


_book_lock = Lock()


def book_search(db, index, query, page):
    with _book_lock:
        db.execute("CREATE TABLE IF NOT EXISTS gutenberg(id INTEGER PRIMARY KEY,title TEXT,authors TEXT,subjects TEXT,language TEXT)")
        if not db.execute("SELECT 1 FROM gutenberg LIMIT 1").fetchone():
            with gzip.open(index, "rt", encoding="utf-8-sig", newline="") as stream, db:
                records=csv.DictReader(stream)
                db.executemany("INSERT OR IGNORE INTO gutenberg VALUES(?,?,?,?,?)",
                    ((r["Text#"],r["Title"],r["Authors"],r["Subjects"],r["Language"]) for r in records
                     if r["Type"]=="Text" and r["Text#"].isdigit()))
    terms=query.split()[:12]
    conditions=" AND ".join(["instr(lower(title || ' ' || authors || ' ' || subjects), lower(?)) > 0"]*len(terms)) or "1"
    rows=db.execute(f"SELECT * FROM gutenberg WHERE {conditions} ORDER BY id LIMIT 21 OFFSET ?",(*terms,(page-1)*20)).fetchall()
    items=[]
    for row in rows[:20]:
        num=row["id"]
        url=f"https://gutenberg.pglaf.org/cache/epub/{num}/pg{num}.txt"
        items.append(dict(id=hashlib.sha256(url.encode()).hexdigest(),kind="Books",title=row["title"],preview=(row["authors"]+" · "+row["subjects"])[:320],rights="Free Gutenberg edition · terms in the ebook",url=url,ext=".txt",provider="Project Gutenberg"))
    return items,len(rows)>20


def search(kind, query, page):
    if kind not in KINDS:
        raise ValueError("Choose a catalogue")
    result = []
    if kind in ("Software","Games"):
        filters = " in:name,description fork:false archived:false stars:>5"
        if kind=="Games":filters+=" topic:game"
        params = urlencode({"q":query + filters,"per_page":20,"page":page,"sort":"stars"})
        data = metadata("https://api.github.com/search/repositories?" + params)
        for item in data["items"]:
            repo = item["full_name"]
            license_id = (item.get("license") or {}).get("spdx_id")
            if license_id not in {"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","ISC","GPL-2.0","GPL-3.0","AGPL-3.0","LGPL-3.0","MPL-2.0","Unlicense","CC0-1.0"} or not re.fullmatch(r"[\w.-]+/[\w.-]+",repo):
                continue
            url = "https://api.github.com/repos/" + repo + "/tarball/" + quote(item["default_branch"], safe="")
            result.append((repo, item["description"], license_id, url, ".tar.gz", "GitHub source archive"))
        more = page*20 < min(data["total_count"],1000)
    else:
        words = re.findall(r"[^\W_]+", query, re.UNICODE)
        clauses = ["mediatype:"+KINDS[kind], "licenseurl:(*creativecommons.org*)"]
        if kind == "Shows":
            clauses += ['(collection:television OR collection:classic_tv OR subject:episode OR subject:series)']
        if kind == "Audiobooks":
            clauses += ["collection:librivoxaudio"]
        clauses.extend('"' + word + '"' for word in words)
        params=urlencode({"q":" AND ".join(clauses),"page":page,"rows":20,"output":"json","sort[]":"downloads desc","fl[]":["identifier","title","description","licenseurl"]},doseq=True)
        data=metadata("https://archive.org/advancedsearch.php?"+params)["response"]
        for item in data["docs"]:
            license_url=item.get("licenseurl","")
            if isinstance(license_url,list):
                license_url=next((x for x in license_url if public_license(x)),"")
            identifier=item["identifier"]
            if public_license(license_url) and re.fullmatch(r"[A-Za-z0-9._-]+",identifier):
                result.append((item.get("title",identifier),item.get("description"),license_url,"https://archive.org/metadata/"+identifier,"","Internet Archive"))
        more=page*20<data["numFound"]
    return [dict(id=hashlib.sha256(url.encode()).hexdigest(),kind=kind,title=clean(title),preview=clean(desc)[:320],rights=rights,url=url,ext=ext,provider=provider) for title,desc,rights,url,ext,provider in result],more


def init(db):
    db.execute("CREATE TABLE IF NOT EXISTS discovery_cart(id TEXT PRIMARY KEY REFERENCES discovery_item(id))")
    db.execute("CREATE TABLE IF NOT EXISTS transfer_progress(id TEXT PRIMARY KEY,received INTEGER,total INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS discovery_file(id TEXT,sequence INTEGER,title TEXT,filename TEXT,PRIMARY KEY(id,sequence))")
    db.execute("""CREATE TABLE IF NOT EXISTS discovery_item(id TEXT PRIMARY KEY,kind TEXT,title TEXT,preview TEXT,rights TEXT,url TEXT,ext TEXT,provider TEXT,filename TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS discovery_page(kind TEXT,query TEXT,page INTEGER,items TEXT,more INTEGER,PRIMARY KEY(kind,query,page))""")


def remember(db,kind,query,page,items,more):
    with db:
        db.executemany("INSERT INTO discovery_item(id,kind,title,preview,rights,url,ext,provider) VALUES(:id,:kind,:title,:preview,:rights,:url,:ext,:provider) ON CONFLICT(id) DO UPDATE SET preview=excluded.preview, rights=excluded.rights WHERE discovery_item.filename IS NULL",items)
        db.execute("INSERT OR REPLACE INTO discovery_page VALUES (?,?,?,?,?)",(kind,query,page,json.dumps([i["id"] for i in items]),int(more)))


# Verified offline editions for oversized Commons originals.
COMMONS_EDITIONS = {
    "Wizard_of_Oz_(1925).webm": ("The Wizard of Oz (1925)", "https://archive.org/download/the-wizard-of-oz-1925/The%20Wizard%20of%20Oz%20%281925%29.mp4",
                                 ".mp4", 399884974, "479afb60992c6a6a3b7952347ad1635d058f9a26"),
}

def commons_video(item):
    source=urlsplit(item["url"])
    edition=COMMONS_EDITIONS.get(unquote(source.path.rsplit("/",1)[-1]))
    if source.hostname=="upload.wikimedia.org" and edition:
        return edition
    title="File:"+unquote(urlsplit(item["url"]).path.rsplit("/",1)[-1]).replace("_"," ")
    params={"action":"query","format":"json","titles":title,"prop":"videoinfo","viprop":"url|size|sha1|derivatives"}
    pages=metadata("https://commons.wikimedia.org/w/api.php?"+urlencode(params)).get("query",{}).get("pages",{})
    info=next((video for page in pages.values() for video in page.get("videoinfo",[])),{})
    if info.get("size",0)>1024**3:
        versions=[v for v in info.get("derivatives",[]) if 0<v.get("height",0)<=720
                  and v.get("type","").startswith("video/webm") and urlsplit(v.get("src","")).hostname=="upload.wikimedia.org"]
        if versions:
            edition=max(versions,key=lambda v:v["height"])
            return (item["title"],edition["src"],".webm",None,None)
    return (item["title"],item["url"],item["ext"],info.get("size"),info.get("sha1"))


def download(db,root,item):
    url,ext=item["url"],item["ext"]
    size=None
    checksum=None
    if item["provider"]=="LibriVox":
        import library_sources
        files=library_sources.chapters(url)
    elif item["provider"]=="Wikimedia Commons" and item["kind"] in {"Films","Shows"}:
        files=[commons_video(item)]
    elif item["provider"]=="media.ccc.de":
        import library_sources
        files=[(item["title"],library_sources.recording(url),".mp4",None,None)]
    elif item["provider"]=="Internet Archive":
        record=metadata(url)
        if record.get("is_dark") or record.get("metadata",{}).get("access-restricted-item") in ("true",True):
            raise ValueError("This title has restricted downloads")
        rights=record.get("metadata",{}).get("licenseurl",[])
        if item["rights"] not in (rights if isinstance(rights,list) else [rights]):
            raise ValueError("The publisher changed the licence. Search for this title again.")
        formats={"Books":[".txt",".pdf",".epub"],"Films":[".mp4",".webm",".ogv"],"Shows":[".mp4",".webm",".ogv"],"Audiobooks":[".mp3",".ogg"]}
        choices=[]
        for f in record.get("files",[]):
            name=f.get("name","")
            suffix=Path(name).suffix.lower()
            if suffix in formats[item["kind"]] and not f.get("private") and str(f.get("size","")).isdigit():
                choices.append((formats[item["kind"]].index(suffix),name,int(f["size"]),f.get("sha1")))
        if not choices: raise ValueError("No downloadable file in a supported format")
        preferred=min(x[0] for x in choices)
        matches=sorted(x for x in choices if x[0]==preferred)
        if item["kind"] == "Audiobooks":
            names = {entry[1] for entry in matches}
            matches = [entry for entry in matches if Path(entry[1]).stem + "_64kb.mp3" not in names]
        files=[]
        for _,name,size,checksum in matches:
            ext=Path(name).suffix.lower()
            media_url="https://archive.org/download/"+item["url"].rsplit("/",1)[1]+"/"+quote(name,safe="/")
            files.append((name,media_url,ext,size,checksum))
        if item["kind"] in ("Books","Films"):
            files=[max(files,key=lambda x:x[3])]
    else:
        files=[(item["title"],url,ext,None,None)]
    root.mkdir(parents=True,exist_ok=True)
    total_bytes = sum(size or 0 for _,_,_,size,_ in files)
    finished_bytes = 0
    first_filename = None
    for idx,(name,url,ext,size,checksum) in enumerate(files):
        filename=item["id"] + (f"-{idx+1}" if len(files)>1 else "") + ext
        if idx == 0:
            first_filename = filename
        target=root/filename
        sha256=next((v[3] for v in INSTALLERS.values() if v[0]==url),None)
        if item["provider"] in ("F-Droid","Debian"):
            url,separator,sha256=url.partition("#sha256=")
            if not separator or not re.fullmatch(r"[0-9a-f]{64}",sha256):raise ValueError("Package checksum missing")
        if url == ZIP_URL:
            sha256 = ZIP_DIGEST
        def progress(written,total):
            with db:
                db.execute("INSERT OR REPLACE INTO transfer_progress VALUES(?,?,?)",("discover-"+item["id"],finished_bytes+written,total_bytes or total))
        verified = False
        if size and checksum and target.is_file() and target.stat().st_size == size:
            digest = hashlib.sha1()
            with target.open("rb") as cached:
                for chunk in iter(lambda:cached.read(512*1024),b""):
                    digest.update(chunk)
            verified = digest.hexdigest() == checksum
        if not verified:
            transfer(target,url,size,checksum,sha256,progress)
        finished_bytes += size or 0
        with db:
            db.execute("INSERT OR REPLACE INTO discovery_file VALUES(?,?,?,?)",(item["id"],idx,name,filename))
    with db:
        db.execute("DELETE FROM transfer_progress WHERE id=?", ("discover-"+item["id"],))
        db.execute("UPDATE discovery_item SET filename=? WHERE id=?", (first_filename,item["id"]))
        if item["provider"]=="Wikimedia Commons" and files[0] in COMMONS_EDITIONS.values():
            name,edition_url,*_=files[0]
            note=" · Offline edition: "+edition_url.rsplit("/",1)[0].replace("/download/","/details/")
            db.execute("UPDATE discovery_item SET title=?, rights=? WHERE id=?",
                       (name,item["rights"].removesuffix(note)+note,item["id"]))


def transfer(target,url,size,checksum,sha256,progress):
    root=target.parent
    partial=target.with_suffix(target.suffix+".part")
    try:
        with urlopen(Request(url,headers={"User-Agent":"EchoOffGrid/1.0"}),timeout=35) as response:
            expected=size or int(response.headers.get("Content-Length") or 0)
            if expected and expected+64*1024*1024>shutil.disk_usage(root).free: raise ValueError("Insufficient available storage")
            digest=hashlib.sha1()
            secure_digest=hashlib.sha256()
            written=0
            progress(0,expected)
            with partial.open("wb") as out:
                while chunk:=response.read(512*1024):
                    out.write(chunk)
                    digest.update(chunk)
                    secure_digest.update(chunk)
                    written+=len(chunk)
                    if written % (2*1024*1024) == 0: progress(written,expected)
            if not written or expected and expected!=written or checksum and checksum!=digest.hexdigest() or sha256 and sha256!=secure_digest.hexdigest():
                raise ValueError("Incomplete download or checksum mismatch")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def record_lines(source, data):
    """Render feed entries as text for both the dashboard and offline reader."""
    if isinstance(data, dict):
        for field in ("events", "features", "items", "results", "nodes"):
            if isinstance(data.get(field), list):
                data = data[field]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        return
    if source == "worldbank-population" and len(data) == 2 and isinstance(data[1], list):
        data = data[1]
    records = [r for r in data if isinstance(r, dict)]
    if source == "noaa-kp":
        records.sort(key=lambda r: str(r.get("time_tag", "")), reverse=True)
    for record in records:
        r = record.get("properties") or record
        if not isinstance(r, dict):
            continue
        if source == "noaa-kp" and isinstance(r.get("Kp"), (int,float)):
            stamp = str(r.get("time_tag","")).replace("T"," ")[:16]
            yield f"Planetary Kp index {r['Kp']:g} · {stamp} UTC" + (f" · {r['station_count']} reporting stations" if isinstance(r.get("station_count"), int) else "")
        elif source == "worldbank-population" and isinstance(r.get("value"), (int,float)) and isinstance(r.get("country"),dict):
            yield f"{clean(r['country'].get('value'))} · {r['value']:,} people ({clean(r.get('date'))})"
        else:
            detail = next((clean(r[k]) for k in ("htmldescription","title","name","description","label") if isinstance(r.get(k),str) and r[k].strip()), "")
            if detail:
                yield detail
                continue
            # Flat scalar fields remain legible even for an unfamiliar provider.
            fields = [f"{k.replace('_',' ')}: {v}" for k,v in r.items()
                      if isinstance(v,(int,float,str)) and str(v).strip() and not str(v).lstrip().startswith(("{","[","http"))]
            if fields:
                yield " · ".join(fields[:4])


def preview(source, text):
    text = (text or "").lstrip()
    if text.startswith(("{", "[")):
        try:
            line = next(record_lines(source,json.loads(text)), "")
        except ValueError:
            line = ""
        return line[:190] or "No readable entries in this saved feed."
    if source.startswith("gutenberg-"):
        author = re.search(r"^Author:\s*(.+)$",text,re.M)
        if author:
            return "By " + clean(author[1])[:180]
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    return " ".join(lines[1:3] if len(lines)>1 else lines)[:190] or "Open the saved copy to read the result."
