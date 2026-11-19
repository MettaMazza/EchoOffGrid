"""Offline dictionary and local Kiwix reader."""
from contextlib import closing, nullcontext
from datetime import date
from string import ascii_lowercase
from functools import lru_cache
from html import escape
from http.client import HTTPConnection, RemoteDisconnected
import json
import os
import re
from pathlib import Path
from shutil import copyfileobj
import socket
import sqlite3
import subprocess
from threading import Lock
from time import monotonic, sleep
import unicodedata
from urllib.parse import quote, urlencode, urlsplit
import zlib


STARTER = Path(__file__).resolve().parent / "vendor/starter-reference"


def word_link(word):
    return f'<a href="/dictionary?{escape(urlencode({"q":word}))}">{escape(word)}</a>'


def word_relations(db, record):
    groups = []
    for field, label in (("synonyms","Synonyms"), ("antonyms","Antonyms"), ("related","Related words")):
        words = dict.fromkeys(item["word"] for item in record.get(field, [])
                              if isinstance(item, dict) and isinstance(item.get("word"), str))
        if words:
            chips = []
            for word in words:
                key = unicodedata.normalize("NFKC",word).casefold()
                if db.execute("SELECT 1 FROM entries WHERE normalized=? LIMIT 1",(key,)).fetchone():
                    chips.append(word_link(word))
                if len(chips) == 12:
                    break
            if chips:
                groups.append(f'<div class="word-rel"><small>{label}</small>{"".join(chips)}</div>')
    return "".join(groups)


def definition(db, term):
    key = unicodedata.normalize("NFKC",term).casefold()
    articles = []
    for word,pos,payload in db.execute("""SELECT word,pos,payload FROM entries WHERE normalized=?
            ORDER BY (word=?) DESC,id""",(key,term)):
        data = json.loads(zlib.decompress(payload))
        groups = {}
        for sense in data.get("senses", []):
            glosses = [g for g in sense.get("glosses",[]) if isinstance(g,str) and g]
            if not glosses:
                continue
            section = " › ".join(g.rstrip(":") for g in glosses[:-1])
            example = next((x["text"] for x in sense.get("examples",[]) if x.get("type")=="example" and x.get("text")), "")
            groups.setdefault(section, []).append('<div class="word-sense"><p>'+escape(glosses[-1])+'</p>'
                + (f'<blockquote>{escape(example)}</blockquote>' if example else "") + word_relations(db,sense) + '</div>')
        if not groups:
            continue
        sections = [(f'<h4>{escape(label)}</h4>' if label else "") + "".join(dict.fromkeys(items))
                    for label,items in groups.items()]
        senses = sections[0]
        if len(sections)>1:
            senses += '<details class="more-senses"><summary>More meanings</summary>' + "".join(sections[1:]) + '</details>'
        articles.append(f'<article class="word-entry"><header class="word-heading"><h3>{escape(word)}</h3>'
                        f'<span>{escape(pos)}</span></header>{senses}{word_relations(db,data)}</article>')
    if articles:
        return "".join(articles)
    return '<p>No exact entry for <strong>'+escape(term)+'</strong>. Open the word index below to browse by spelling.</p>'


def daily_word(db):
    day = date.today().toordinal()
    pool = "estuary cadence canopy luminous meander aperture glacier mosaic compass orbit resilience lichen ember sonorous tide tessellate solstice archive lucid fern horizon cadence almanac prism current latitude habitat nocturnal echo perennial".split()
    for index in range(len(pool)):
        key = pool[(day + index) % len(pool)]
        row = db.execute("SELECT word,pos,payload FROM entries WHERE normalized=? ORDER BY id LIMIT 1",(key,)).fetchone()
        if row:
            break
    else:
        maximum = db.execute("SELECT max(id) FROM entries").fetchone()[0]
        if not maximum:
            return ""
        row = db.execute("SELECT word,pos,payload FROM entries WHERE id>=? ORDER BY id LIMIT 1",
                         (1 + day * 2654435761 % maximum,)).fetchone()
    word,pos,payload = row
    data = json.loads(zlib.decompress(payload))
    gloss = next((s["glosses"][-1] for s in data.get("senses",[]) if s.get("glosses")), "")
    return (f'<section class="daily-word"><small>Word of the day · {date.today():%d %B}</small>'
            f'<h3>{word_link(word)}</h3><small>{escape(pos)}</small><p>{escape(gloss)}</p></section>')


@lru_cache(maxsize=4)
def index_letters(path, modified):
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True)) as db:
        sample = db.execute("SELECT payload FROM entries ORDER BY id LIMIT 1").fetchone()
        if not sample or json.loads(zlib.decompress(sample[0])).get("lang_code") == "en":
            return tuple(ascii_lowercase)
        rows = db.execute("SELECT DISTINCT substr(normalized,1,1) AS initial FROM entries ORDER BY initial")
        return tuple(row[0] for row in rows if row[0].isalpha())


@lru_cache(maxsize=4)
def reading_vocabulary(path, modified):
    """Intersect the English reading list with the connected dictionary."""
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as db:
        first = db.execute("SELECT payload FROM entries ORDER BY id LIMIT 1").fetchone()
        if not first or json.loads(zlib.decompress(first[0])).get("lang_code") != "en":
            return None
        words = Path(__file__).with_name("reading-words.txt").read_text().splitlines()
        available = set()
        for start in range(0,len(words),400):
            batch = words[start:start+400]
            slots = ",".join("?" for _ in batch)
            available.update(row[0] for row in db.execute(
                f"SELECT DISTINCT normalized FROM entries WHERE normalized IN ({slots}) AND word=normalized",batch))
    return tuple(sorted(available))


def dictionary(launcher, term, prefix=None, page="1", phrases=False, *, path=None):
    term = term.strip()
    form = (f'<form class="word-search"><input type=search name=q aria-label="Dictionary word" '
            f'placeholder="Look up a word…" value="{escape(term)}" required> <button>Look up</button></form>')
    if path is None and launcher:
        path = launcher.parent / "library/dictionary.sqlite3"
    if not path or not path.is_file():
        path = STARTER / "reading-dictionary.db"
    letters = index_letters(path,path.stat().st_mtime_ns)
    prefix = unicodedata.normalize("NFKC",prefix if prefix is not None else (term[:1] or next(iter(letters),""))).casefold()[:40]
    number = int(page) if page.isascii() and page.isdigit() and len(page)<=6 else 1
    number = max(1,number)
    def browse(prefix, number=1):
        return "/dictionary?" + escape(urlencode({"prefix":prefix,"page":number, "phrases":int(phrases)})) + "#word-index"
    alphabet = "".join(f'<a href="{browse(c)}" {"aria-current=true" if prefix==c else ""}>{c.upper()}</a>' for c in letters[:96])
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as db:
        content = definition(db,term) if term else daily_word(db)
        vocabulary = None if phrases else reading_vocabulary(path,path.stat().st_mtime_ns)
        offset = (number-1)*48
        if vocabulary is not None:
            matches = [word for word in vocabulary if word.startswith(prefix)]
            rows = matches[offset:offset+49]
        else:
            condition = "WHERE normalized>=? AND normalized<?" if prefix else ""
            args = (prefix, prefix+chr(0x10ffff)) if prefix else ()
            records = db.execute(f"""SELECT coalesce(min(CASE WHEN word=normalized THEN word END),min(word))
                FROM entries {condition} GROUP BY normalized ORDER BY normalized LIMIT 49 OFFSET ?""",
                (*args,offset))
            rows = [word for word, in records]
    words = "".join(word_link(word) for word in rows[:48])
    prev = f'<a href="{browse(prefix,number-1)}">← Previous</a>' if number>1 else ""
    more = f'<a href="{browse(prefix,number+1)}">Next →</a>' if len(rows)>48 else ""
    index = (f'<section id="word-index"><div class=section-head><h3>{"Reading vocabulary" if vocabulary is not None else "Full dictionary index"}</h3><a href="{browse("")}">All letters</a></div>'
             f'<nav class="word-alphabet" aria-label="Initial letter">{alphabet}</nav>'
             f'<form class="index-filter" action="/dictionary#word-index"><label>Starts with <input name=prefix value="{escape(prefix)}" maxlength=40 size=8></label><label><input type=checkbox name=phrases value=1 {"checked" if phrases else ""}> Full dictionary (includes abbreviations)</label><button>Apply</button></form>'
             f'<div class="word-grid">{words or "<p>No entries on this page.</p>"}</div>'
             f'<nav class="word-paging" aria-label="Word index pages">{prev}<span>Page {number}</span>{more}</nav></section>')
    if term:
        index = '<details class="entry-index"><summary>Browse the word index</summary>' + index + '</details>'
    else:
        content = '<div class="dictionary-browser">' + content + index + '</div>'
        index = ""
    return form+content+index+'<small>Wiktionary contributors · Wiktextract / kaikki.org</small>'


class Wiki:
    def __init__(self, kit, launcher, downloads=None):
        self.folders = [p for p in (kit / "02-Reference" if kit else None,
                                   launcher.parent / "library" if launcher else None, downloads) if p]
        self.preferred = None
        self.archives = self.scan()
        runtimes = launcher.parent.glob("models/runtime/kiwix-tools*/kiwix-serve") if launcher else []
        self.tool = next(iter(sorted(runtimes, reverse=True)), STARTER / "kiwix-serve")
        self.lock = Lock()
        self.process = None
        self.diagnostic_log = None

    def scan(self):
        files = {}
        for folder in self.folders:
            for path in sorted(folder.glob("*.zim")):
                files.setdefault(path.name, path)
        return self.with_starter(list(files.values()))

    def refresh(self):
        with self.lock:
            archives = self.scan()
            if archives != self.archives:
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait()
                self.archives = archives

    @staticmethod
    def with_starter(archives):
        if any(p.name.startswith("wikipedia_") for p in archives):
            return list(archives)
        for folder in (STARTER, STARTER.parents[1]/"dist/reference"):
            available = sorted(folder.glob("wikipedia_*.zim"))
            if available:
                return list(archives) + available
        return list(archives)

    def page(self, book, query):
        books = {p.stem for p in self.archives}
        if not books or not self.tool:
            return "<p>Run the first-launch setup from the source checkout to download Wikipedia, or open a packaged build with the archive included.</p>"
        if book not in books:
            book = self.preferred
        if book not in books:
            book = next((name for prefix in ("wikipedia_en_all_maxi_", "wikipedia_en-simple_all_maxi_", "wikipedia_en_all_")
                         for name in sorted(books, reverse=True) if name.startswith(prefix)), self.archives[0].stem)
        options = "".join(f'<option value="{escape(name)}"{" selected" if name == book else ""}>{escape(name)}</option>' for name in sorted(books))
        src = "/zim/search?" + urlencode({"content": book, "pattern": query}) if query else "/zim/content/" + quote(book) + "/"
        return f'<form><select name=book aria-label="Reference collection">{options}</select> <input type=search name=q aria-label="Search articles" placeholder="Search articles…" value="{escape(query)}"> <button>Browse</button></form><div class="wiki-surface"><iframe class="kit-document wiki-frame" sandbox="allow-same-origin" title="Offline articles" src="{escape(src)}"></iframe></div>'

    def port(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                return self.port_number
            if not self.tool or not self.archives:
                raise OSError("Offline archives unavailable")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            output = self.diagnostic_log.open("wb") if self.diagnostic_log else nullcontext(subprocess.DEVNULL)
            with output as stream:
                options = ["--threads=2", "--searchLimit=1"] if self.diagnostic_log else ["-a", str(os.getpid())]
                self.process = subprocess.Popen([self.tool, *options, "-i", "127.0.0.1", "-p", str(port), "-r", "/zim", "-n", "-b", *self.archives], stdout=stream, stderr=stream)
            self.port_number = port
            until = monotonic() + 12
            while self.process.poll() is None and monotonic() < until:
                try:
                    with closing(HTTPConnection("127.0.0.1",port,timeout=1)) as probe:
                        probe.request("HEAD","/zim/")
                        probe.getresponse().close()
                        return port
                except OSError:
                    sleep(.1)
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait()
            raise OSError("Offline reader failed to start")

    def close(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait()

    def serve(self, handler):
        with closing(HTTPConnection("127.0.0.1", self.port(), timeout=30)) as upstream:
            for attempt in range(2):
                try:
                    upstream.request("GET", handler.path)
                    response = upstream.getresponse()
                    break
                except (RemoteDisconnected,ConnectionResetError):
                    upstream.close()
                    if attempt:
                        raise OSError("Offline reader disconnected")
                    sleep(.15)
            location = response.getheader("Location")
            if location and (not location.startswith("/zim/") or urlsplit(location).netloc):
                handler.send_error(502)
                return
            search_html = (urlsplit(handler.path).path == "/zim/search" and response.status == 200
                           and "text/html" in (response.getheader("Content-Type") or "")
                           and not response.getheader("Content-Encoding"))
            payload = None
            html = "text/html" in (response.getheader("Content-Type") or "") and not response.getheader("Content-Encoding")
            if html:
                css = b"""<style>html,body{color-scheme:dark;background:#101c18!important;color:#e2f1e8!important}
body{padding:1rem;line-height:1.5;font-family:system-ui,sans-serif}body *{color:inherit!important;background-color:transparent!important}
body a,body a *{color:#8de5bb!important}body a:visited{color:#c0b4e5!important}
li{padding:.45rem 0}body ::selection{background:#446b59!important;color:white!important}</style>"""
                base = b'<meta name="color-scheme" content="dark"><style>:root,body{color-scheme:dark;background:#101c18!important;color:#e2f1e8}body a{color:#8de5bb}</style>'
                # Kiwix text-only archives keep map labels and captions but omit the
                # map image that normally gives their positioning container height.
                base += b"""<style>
.locmap:not(:has(img)), .locmap:not(:has(img)) > div,
.locmap:not(:has(img)) div:has(> .od) {max-width:100%!important}
.locmap:not(:has(img)) .od, .locmap:not(:has(img)) .od :is(.pl,.pr,.pv) {
 position:static!important; width:auto!important; text-align:center!important}
.locmap:not(:has(img)) .od .id {display:none!important}
html:root .mw-parser-output .locmap:not(:has(img)) .od,
html:root .mw-parser-output .locmap:not(:has(img)) .od :is(.pl,.pr,.pv)>div {
 display:block!important; float:none!important; background:transparent!important; color:inherit!important}
</style>"""
                document = response.read()
                head = re.search(br"<head(?:\s[^>]*)?>", document, re.I)
                if head:
                    insert = head.end()
                    payload = document[:insert] + base + document[insert:]
                else:
                    payload = base + document
                if search_html:
                    payload = payload.replace(b"</head>", css+b"</head>", 1)
            handler.send_response(response.status)
            for header in ("Content-Type", "Content-Length", "Content-Encoding", "Location"):
                if header == "Content-Length" and payload is not None:
                    handler.send_header(header,str(len(payload)))
                elif response.getheader(header):
                    handler.send_header(header, response.getheader(header))
            handler.send_header("Content-Security-Policy", "sandbox allow-same-origin; default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-ancestors 'self'")
            handler.end_headers()
            if payload is None:
                copyfileobj(response, handler.wfile)
            else:
                handler.wfile.write(payload)
