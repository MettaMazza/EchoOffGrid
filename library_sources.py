"""Public catalogues with independently cached pages."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from hashlib import sha256
from io import BytesIO
from itertools import zip_longest
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock
from time import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import discovery

PROVIDERS={
    "Pictures":("Wikimedia Commons","NASA Image Library"),
    "Books":("Project Gutenberg","Standard Ebooks","Internet Archive","Wikimedia Commons"),
    "Films":("Blender Open Movies","Internet Archive","Wikimedia Commons"),
    "Shows":("media.ccc.de","Internet Archive","Wikimedia Commons"),
    "Audiobooks":("LibriVox","Internet Archive","Wikimedia Commons"),
    "Games":("F-Droid","GitHub","Debian"),
    "Software":("F-Droid","GitHub","Debian"),
}
index_lock=Lock()

def get(url,limit):
    with urlopen(Request(url,headers={"User-Agent":"EchoOffGrid/1.0 offline-library"}),timeout=12) as r:
        data=r.read(limit+1)
    if len(data)>limit:raise ValueError("Catalogue exceeds size limit")
    return data

def item(kind,provider,title,desc,rights,url,ext):
    return dict(id=sha256((kind+"|"+url).encode()).hexdigest(),kind=kind,provider=provider,title=discovery.clean(title),
                preview=discovery.clean(desc)[:320],rights=discovery.clean(rights),url=url,ext=ext)

def commons(kind,q,page):
    filters={"Pictures":("filemime:image/jpeg","landscape"),"Books":("filemime:application/pdf","book"),"Films":("filetype:video","short film"),
             "Shows":("filetype:video","episode"),"Audiobooks":("filetype:audio","audiobook")}
    fmt,term=filters[kind]
    params=dict(action="query",format="json",generator="search",gsrnamespace=6,gsrlimit=15,gsroffset=(page-1)*15,
                gsrsearch=fmt+" "+(q or term),prop="imageinfo",iiprop="url|extmetadata")
    result=discovery.metadata("https://commons.wikimedia.org/w/api.php?"+urlencode(params))
    if "error" in result:raise ValueError("Commons search unavailable")
    rows=[]
    for p in sorted(result.get("query",{}).get("pages",{}).values(),key=lambda x:x.get("index",0)):
        info=(p.get("imageinfo") or [{}])[0]
        url=info.get("url","")
        if urlsplit(url).hostname!="upload.wikimedia.org":continue
        ext=Path(urlsplit(url).path).suffix.lower()
        if ext not in {"Pictures":{".jpg",".jpeg",".png",".webp"},"Books":{".pdf"},"Films":{".mp4",".webm",".ogv"},"Shows":{".mp4",".webm",".ogv"},"Audiobooks":{".ogg",".oga",".mp3",".wav",".flac"}}[kind]:continue
        meta=info.get("extmetadata",{})
        license=discovery.clean(meta.get("LicenseShortName",{}).get("value"))
        if not (license.startswith(("CC ","CC0")) or "public domain" in license.lower()):continue
        author=discovery.clean(meta.get("Artist",{}).get("value"))
        rights=" · ".join(x for x in (license,author,info.get("descriptionurl","")) if x)
        rows.append(item(kind,"Wikimedia Commons",p["title"].removeprefix("File:"),meta.get("ImageDescription",{}).get("value"),rights,url,ext))
    return rows,"continue" in result

def nasa(kind,q,page):
    data=discovery.metadata("https://images-api.nasa.gov/search?"+urlencode({"q":q or "Earth","media_type":"image","page":page,"page_size":15}))
    collection=data["collection"];rows=[]
    for entry in collection.get("items",[]):
        d=(entry.get("data") or [{}])[0]
        link=next((r.get("href","") for r in entry.get("links",[]) if r.get("rel")=="preview"),"")
        if urlsplit(link).hostname!="images-assets.nasa.gov" or not urlsplit(link).path.lower().endswith((".jpg",".jpeg")):continue
        creator=d.get("photographer") or d.get("secondary_creator") or d.get("center") or "NASA"
        rows.append(item(kind,"NASA Image Library",d.get("title"),d.get("description"),f"{creator} · NASA image {d.get('nasa_id','')} · NASA media usage guidelines",link,".jpg"))
    return rows,any(l.get("rel")=="next" for l in collection.get("links",[]))

def standard(kind,q,page):
    if page!=1:return [],False
    doc=ET.fromstring(get("https://standardebooks.org/feeds/atom/new-releases",2_000_000))
    rows=[]
    for e in doc.findall("{*}entry"):
        title=e.findtext("{*}title") or ""
        author=e.findtext("{*}author/{*}name") or ""
        if q.casefold() not in (title+" "+author).casefold():continue
        link=next((a.get("href","") for a in e.findall("{*}link") if a.get("type")=="application/epub+zip"),"")
        if urlsplit(link).hostname=="standardebooks.org":
            rows.append(item(kind,"Standard Ebooks",title,author+" · "+(e.findtext("{*}summary") or ""),e.findtext("{*}rights"),link,".epub"))
    return rows,False

def librivox(kind,q,page):
    params=dict(format="json",limit=15,offset=(page-1)*15)
    if q:params["title"]="^"+q
    data=discovery.metadata("https://librivox.org/api/feed/audiobooks/?"+urlencode(params))
    rows=[]
    for b in data.get("books") or []:
        book=str(b["id"])
        if book.isdigit():
            rows.append(item(kind,"LibriVox",b["title"],b.get("description"),"Public domain in the US · LibriVox volunteers",
                             "https://librivox.org/rss/"+book,".mp3"))
    return rows,len(rows)==15

def chapters(url):
    root=ET.fromstring(get(url,5_000_000))
    parts=[]
    for track in root.findall("./channel/item"):
        file=track.find("enclosure")
        if file is None:continue
        src=file.get("url","")
        host=urlsplit(src).hostname or ""
        if (host=="archive.org" or host.endswith(".archive.org") or host.endswith(".librivox.org")) and urlsplit(src).scheme in ("http","https"):
            parts.append((track.findtext("title") or "Chapter",src.replace("http://","https://",1),".mp3",None,None))
    if not parts:raise ValueError("No downloadable audiobook chapters")
    return parts

def talks(kind,q,page):
    route="search?"+urlencode({"q":q}) if q else "recent"
    data=discovery.metadata("https://api.media.ccc.de/public/events/"+route)
    events=data.get("events",[]);rows=[]
    for e in events[(page-1)*15:page*15]:
        u=e.get("url","")
        if urlsplit(u).hostname=="api.media.ccc.de":
            rows.append(item(kind,"media.ccc.de",e["title"],e.get("conference_title"),"Conference recording · see recording licence",u,".mp4"))
    return rows,page*15<len(events)

def recording(url):
    files=discovery.metadata(url).get("recordings",[])
    for rec in sorted(files,key=lambda r:(bool(r.get("high_quality")),r.get("size") or 0)):
        u=rec.get("recording_url","");host=urlsplit(u).hostname or ""
        if urlsplit(u).scheme=="https" and (host=="cdn.media.ccc.de" or host.endswith(".ccc.de")) and urlsplit(u).path.endswith(".mp4"):
            return u
    raise ValueError("No downloadable MP4 for this recording")

def blender(kind,q,page):
    if page!=1:return [],False
    films=[("Big Buck Bunny","https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_640x360.m4v","CC BY 3.0 · Blender Foundation"),
           ("Sintel","https://download.blender.org/durian/movies/Sintel.2010.720p.mkv","CC BY 3.0 · Blender Foundation")]
    return [item(kind,"Blender Open Movies",t,"Official open movie",r,u,Path(u).suffix) for t,u,r in films if q.casefold() in t.casefold()],False

def package_records(provider):
    if provider=="F-Droid":
        raw=get("https://f-droid.org/repo/index-v1.jar",50_000_000)
        with ZipFile(BytesIO(raw)) as z:
            if z.getinfo("index-v1.json").file_size>200_000_000:raise ValueError("Index too large")
            with z.open("index-v1.json") as f:data=json.load(f)
        for app in data["apps"]:
            versions=data["packages"].get(app["packageName"],[])
            builds=[v for v in versions if re.fullmatch(r"[\w.-]+\.apk",v.get("apkName","")) and re.fullmatch("[a-f0-9]{64}",v.get("hash",""))]
            if not builds:continue
            v=max(builds,key=lambda v:int(v.get("versionCode",0)))
            loc=app.get("localized",{}).get("en-US",{})
            yield ("Games" if any(c.endswith(" Game") or c in ("Games","Emulator","Visual Novel") for c in app.get("categories",[])) else "Software",loc.get("name") or app.get("name") or app["packageName"],
                   loc.get("summary") or app.get("summary") or app["packageName"],app.get("license") or "See package licence",
                   "https://f-droid.org/repo/"+v["apkName"]+"#sha256="+v["hash"],".apk")
    else:
        import lzma
        binary=get("https://deb.debian.org/debian/dists/stable/main/source/Sources.xz",32_000_000)
        with lzma.open(BytesIO(binary),"rt",encoding="utf-8",errors="replace") as f:
            fields={};section=""
            for line in f:
                if line.strip():
                    if line.startswith(" "):
                        if section=="Checksums-Sha256":fields[section]+="\n"+line.strip()
                    else:
                        section,_,value=line.partition(":")
                        fields[section]=value.strip()
                    continue
                checks=[s.split() for s in fields.get("Checksums-Sha256","").splitlines() if ".orig.tar." in s]
                if checks and "Directory" in fields and fields["Directory"].startswith("pool/main/"):
                    checksum,size,name=checks[0]
                    if re.fullmatch(r"[a-f0-9]{64}",checksum) and "/" not in name:
                        yield ("Games" if fields.get("Section")=="games" else "Software",fields.get("Package",name),
                               "Debian stable · source archive · "+fields.get("Version",""),"Debian main · licence in source archive",
                               "https://deb.debian.org/debian/"+fields["Directory"]+"/"+quote(name)+"#sha256="+checksum,"".join(Path(name).suffixes[-2:]))
                fields={};section=""

def packages(db,provider,kind,q,page):
    with index_lock:
        db.execute("CREATE TABLE IF NOT EXISTS package_catalog(provider,kind,title,description,rights,url,ext)")
        db.execute("CREATE TABLE IF NOT EXISTS package_catalog_time(provider PRIMARY KEY, stamp)")
        stamp=db.execute("SELECT stamp FROM package_catalog_time WHERE provider=?",(provider,)).fetchone()
        if not stamp or time()-stamp[0]>7*86400:
            try:
                records=list(package_records(provider))
                if not records:raise ValueError("No packages available")
                with db:
                    db.execute("DELETE FROM package_catalog WHERE provider=?",(provider,))
                    db.executemany("INSERT INTO package_catalog VALUES(?,?,?,?,?,?,?)",((provider,*r) for r in records))
                    db.execute("INSERT OR REPLACE INTO package_catalog_time VALUES(?,?)",(provider,time()))
            except Exception:
                if not stamp:raise
    rows=db.execute("""SELECT title,description,rights,url,ext FROM package_catalog WHERE provider=? AND kind=?
        AND instr(lower(title||' '||description),lower(?))>0 ORDER BY title LIMIT 16 OFFSET ?""",(provider,kind,q,(page-1)*15)).fetchall()
    return [item(kind,provider,*r) for r in rows[:15]],len(rows)>15

def lookup(db,source,kind,q,page,index):
    if source=="Project Gutenberg":return discovery.book_search(db,index,q,page)
    if source in ("GitHub","Internet Archive"):return discovery.search(kind,q,page)
    if source in ("Debian","F-Droid"):return packages(db,source,kind,q,page)
    return {"NASA Image Library":nasa,"Standard Ebooks":standard,"Wikimedia Commons":commons,"LibriVox":librivox,
            "media.ccc.de":talks,"Blender Open Movies":blender}[source](kind,q,page)

def browse(database,kind,q,page,selected,index):
    sources=[selected] if selected in PROVIDERS[kind] else PROVIDERS[kind]
    def from_source(source):
        cache_key=source+"|"+q
        with closing(sqlite3.connect(database,timeout=30)) as db:
            db.row_factory=sqlite3.Row
            try:
                rows,more=lookup(db,source,kind,q,page,index)
                discovery.remember(db,kind,cache_key,page,rows,more)
                return rows,more,""
            except Exception:
                prev=db.execute("SELECT items,more FROM discovery_page WHERE kind=? AND query=? AND page=?",(kind,cache_key,page)).fetchone()
                if not prev and source in ("Project Gutenberg","Internet Archive","GitHub"):
                    prev=db.execute("SELECT items,more FROM discovery_page WHERE kind=? AND query=? AND page=?",(kind,q,page)).fetchone()
                if not prev:return [],False,source+" unavailable"
                rows=[db.execute("SELECT * FROM discovery_item WHERE id=?",(key,)).fetchone() for key in json.loads(prev["items"])]
                return [r for r in rows if r],bool(prev["more"]),source+" saved page"
    with ThreadPoolExecutor(max_workers=4) as pool: batches=list(pool.map(from_source,sources))
    items={r["id"]:r for group in zip_longest(*(b[0] for b in batches)) for r in group if r}
    return list(items.values()),any(b[1] for b in batches)," · ".join(b[2] for b in batches if b[2])
