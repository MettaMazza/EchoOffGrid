"""Publisher artwork cached locally for Discover, catalogue results and news."""
from contextlib import closing
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import BoundedSemaphore,Lock
from urllib.parse import quote,unquote,urljoin,urlsplit,urlencode
from urllib.request import Request,HTTPRedirectHandler,build_opener
from xml.etree import ElementTree as ET
import json
import re
import time
import publishers
from archive import connect

KNOWN={"archive.org","gutenberg.org","pglaf.org","standardebooks.org","wikimedia.org","nasa.gov","github.com","githubassets.com","githubusercontent.com","f-droid.org","debian.net","debian.org","ccc.de","librivox.org","blender.org","bbci.co.uk","ichef.bbci.co.uk","guim.co.uk","cbsistatic.com","akamaihd.net","france24.com","rfi.fr","cbc.ca","dwcdn.net","dw.com","npr.org","nprcdn.com","brightspotcdn.com","rnztools.nz","mediacorp.sg","i-scmp.com","scmp.com","thenational.scot","thehindu.com","thgim.com","bbc.com","bbc.co.uk"}
KNOWN.update(p[2] for p in publishers.WORLD+publishers.SCOTLAND+[publishers.NORTH])
slots=BoundedSemaphore(5)
locks=[Lock() for _ in range(32)]

def permitted(url):
    u=urlsplit(url)
    return u.scheme=="https" and not u.username and not u.password and u.port in (443,None) and any(u.hostname==d or (u.hostname or "").endswith("."+d) for d in KNOWN)

class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not permitted(newurl):raise ValueError("Unsupported media origin")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def open_url(url,headers=None):
    if not permitted(url):raise ValueError("Unsupported media origin")
    return build_opener(Redirect()).open(Request(url,headers={"User-Agent":"EchoOffGrid/1.0 Offline Library",**(headers or {})}),timeout=10)

def fetch(url,limit):
    with open_url(url) as r:
        data=r.read(limit+1)
    if len(data)>limit:raise ValueError("Preview too large")
    return data

class Metadata(HTMLParser):
    image=""
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=="meta" and (values.get("property") or values.get("name")) in {"og:image","twitter:image","og:image:secure_url"} and not self.image:
            self.image=values.get("content","")

def social_image(url):
    parser=Metadata()
    with open_url(url) as r:
        parser.feed(r.read(450000).decode("utf8","replace"))
    return urljoin(url,parser.image) if parser.image else ""

def media_url(row,video=False):
    url=row["url"]; provider=row["provider"];u=urlsplit(url)
    if provider=="Internet Archive":
        identifier=u.path.rstrip("/").split("/")[-1]
        if video:
            files=json.loads(fetch("https://archive.org/metadata/"+quote(identifier),4000000)).get("files",[])
            movies=[f for f in files if f.get("name","").lower().endswith(".mp4") and not f.get("private") and str(f.get("size","")).isdigit()]
            if movies:return "https://archive.org/download/"+quote(identifier)+"/"+quote(min(movies,key=lambda x:int(x["size"]))["name"])
            return ""
        return "https://archive.org/services/img/"+quote(identifier)
    if provider=="Wikimedia Commons":
        filename=unquote(u.path.rsplit("/",1)[-1])
        prop="videoinfo" if video else "imageinfo"
        args={"action":"query","format":"json","titles":"File:"+filename,"prop":prop}
        if video:args["viprop"]="derivatives|url"
        else:args.update(iiprop="url",iiurlwidth=640)
        data=json.loads(fetch("https://commons.wikimedia.org/w/api.php?"+urlencode(args),500000))
        info=next(iter(data["query"]["pages"].values()))[prop][0]
        if video:return next((r["src"] for r in info.get("derivatives",[]) if r.get("transcodekey")=="240p.vp9.webm"),info.get("url",""))
        return info.get("thumburl") or (url if row["kind"]=="Pictures" else "")
    if provider=="media.ccc.de":
        item=json.loads(fetch(url,750000))
        if video:return next((r["recording_url"] for r in item.get("recordings",[]) if r.get("recording_url","").endswith(".mp4")),"")
        return item.get("thumb_url") or item.get("poster_url") or ""
    if provider=="Blender Open Movies":
        if video:return url
        return social_image("https://studio.blender.org/films/"+("big-buck-bunny" if "bunny" in url.lower() else "sintel")+"/")
    if video:return ""
    if provider=="NASA Image Library":return url.replace("~thumb.","~small.")
    if provider=="Project Gutenberg":
        number=re.search(r"/(?:epub|files)/(\d+)/",u.path)
        if number:return "https://www.gutenberg.org/cache/epub/"+number[1]+"/pg"+number[1]+".cover.medium.jpg"
    if provider=="Standard Ebooks":return url.split("/downloads/")[0]+"/downloads/cover.jpg"
    if provider.startswith("GitHub"):
        parts=u.path.strip("/").split("/")
        if len(parts)>=3:return "https://opengraph.githubassets.com/1/"+"/".join(parts[1:3])
    if provider=="News":return social_image(url)
    if provider=="LibriVox":
        root=ET.fromstring(fetch(url,1500000))
        icon=root.find("./channel/{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
        return icon.get("href","") if icon is not None else root.findtext("./channel/image/url") or ""
    if provider=="F-Droid":return social_image("https://f-droid.org/packages/"+u.path.rsplit("/",1)[-1].rsplit("_",1)[0]+"/")
    if provider=="Debian":return "https://screenshots.debian.net/thumbnail/"+quote(row["title"])
    return ""

def tag(key,title="",detail=False):
    return f'<span class="publisher-art{" detail" if detail else ""}"><span class="cover-letter" aria-hidden="true">{escape(title[:1].upper())}</span><img loading="lazy" decoding="async" alt="{escape(title,quote=True)}" src="/publisher-art/{escape(str(key),quote=True)}"></span>'

def lookup(db,key):
    if key.startswith("story-") and key[6:].isdigit():
        return db.execute("SELECT link AS url,title,'News' AS provider,'News' AS kind FROM news_story WHERE id=?",(key[6:],)).fetchone()
    return db.execute("SELECT * FROM discovery_item WHERE id=?",(key,)).fetchone()

def resolve(database,key):
    with closing(connect(database)) as db:
        row=lookup(db,key)
        hint=db.execute("SELECT url FROM news_art WHERE link=?",(row["url"],)).fetchone() if row and row["provider"]=="News" else None
    if not row:raise ValueError("Unknown entry")
    digest=sha256(row["url"].encode()).hexdigest()
    cache=database.parent/"Publisher artwork"
    cache.mkdir(exist_ok=True)
    path=cache/digest
    miss=cache/(digest+".miss")
    with locks[int(digest[:2],16)%len(locks)]:
        if path.is_file():return path.read_bytes()
        if miss.is_file() and time.time()-miss.stat().st_mtime<900:raise ValueError("Artwork unavailable")
        try:
            with slots:
                url=hint[0] if hint else media_url(row)
                try:
                    data=fetch(url,5*1024*1024)
                except (OSError, ValueError):
                    if row["provider"] != "NASA Image Library" or row["url"] == url:raise
                    data=fetch(row["url"],5*1024*1024)
            if not mime(data):raise ValueError("Publisher supplied no image")
            with NamedTemporaryFile(dir=cache,delete=False) as out:out.write(data)
            Path(out.name).replace(path)
            return data
        except Exception:
            miss.touch();raise

def mime(data):
    if data.startswith(b"\xff\xd8\xff"):return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):return "image/png"
    if data.startswith((b"GIF87a",b"GIF89a")):return "image/gif"
    if data[:4]==b"RIFF" and data[8:12]==b"WEBP":return "image/webp"

def film_preview(handler,key):
    with closing(connect(handler.server.database)) as db:row=lookup(db,key)
    if not row or row["kind"] not in {"Films","Shows"}:
        handler.send_error(404);return
    try:
        movie=media_url(row,video=True)
        if not movie:raise ValueError("No stream offered")
        headers={}
        requested=handler.headers.get("Range","")
        if requested:
            if not re.fullmatch(r"bytes=\d*-\d*",requested):raise ValueError("Invalid range")
            headers["Range"]=requested
        with open_url(movie,headers) as remote:
            mime=remote.headers.get_content_type()
            if not (mime.startswith("video/") or mime=="application/octet-stream"):raise ValueError("Preview unavailable")
            handler.send_response(remote.status)
            handler.send_header("Content-Type",mime if mime.startswith("video/") else "video/mp4")
            for name in ("Content-Length","Content-Range","Accept-Ranges"):
                if remote.headers.get(name):handler.send_header(name,remote.headers[name])
            handler.end_headers()
            while chunk:=remote.read(128*1024):handler.wfile.write(chunk)
    except (BrokenPipeError,ConnectionResetError):return
    except (OSError,ValueError,KeyError,StopIteration):handler.send_error(502,"Publisher preview unavailable")
