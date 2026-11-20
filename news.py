"""Local news editions and bounded, persistent offline article storage."""
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from html.parser import HTMLParser
from http.client import HTTPException
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import re
from html import unescape
from concurrent.futures import ThreadPoolExecutor
import publishers
import media_previews
from threading import Event, Thread
from time import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from kit_library import carousel

GLOBAL = "World"
EDITIONS = {
    GLOBAL: "world", "United Kingdom": "uk", "England": "england",
    "Scotland": "scotland", "Aberdeen, Aberdeenshire, Orkney and Shetland": "scotland/north_east_orkney_and_shetland",
    "Edinburgh, Fife and East Scotland": "scotland/edinburgh_east_and_fife",
    "Glasgow and West Scotland": "scotland/glasgow_and_west",
    "Highlands and Islands": "scotland/highlands_and_islands",
    "Tayside and Central Scotland": "scotland/tayside_and_central",
    "London": "england/london", "Manchester": "england/manchester",
    "Wales": "wales", "Northern Ireland": "northern_ireland",
    "Africa": "world/africa", "Asia": "world/asia", "Australia": "world/australia",
    "Europe": "world/europe", "Latin America and the Caribbean": "world/latin_america",
    "Middle East": "world/middle_east", "US and Canada": "world/us_and_canada",
}


def fetch(url, limit):
    req = Request(url, headers={"User-Agent": "EchoOffGrid/1.7 offline reader"})
    with urlopen(req, timeout=8) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Response exceeded size limit")
    return data


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.article = self.paragraph = False
        self.parts = []
        self.lines = []

    def handle_starttag(self, tag, attrs):
        if tag == "article":
            self.article = True
        if self.article and tag == "p":
            self.paragraph = True
            self.parts = []

    def handle_data(self, text):
        if self.paragraph:
            self.parts.append(text)

    def handle_endtag(self, tag):
        if tag == "p" and self.paragraph:
            line = " ".join("".join(self.parts).split())
            if line:
                self.lines.append(line)
            self.paragraph = False
        if tag == "article":
            self.article = self.paragraph = False


def date_label(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%d %b %Y · %H:%M UTC")


class News:
    def __init__(self, database):
        self.path = database
        self.wake = Event()
        self.stop = Event()
        self.worker = None
        with closing(sqlite3.connect(database)) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS news_original(id INTEGER PRIMARY KEY,link TEXT NOT NULL,acquired INTEGER NOT NULL,body BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS news_art(link TEXT PRIMARY KEY,url TEXT);
                CREATE TABLE IF NOT EXISTS news_setting(id INTEGER PRIMARY KEY, place TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS news_check(edition TEXT PRIMARY KEY, attempt INTEGER, success INTEGER, error TEXT);
                CREATE TABLE IF NOT EXISTS news_story(id INTEGER PRIMARY KEY, edition TEXT, link TEXT, title TEXT,
                    summary TEXT, published INTEGER, body TEXT DEFAULT '', UNIQUE(edition,link));
            """)

    def start(self):
        self.worker = Thread(target=self.run, name="Offline news", daemon=True)
        self.worker.start()

    def close(self):
        self.stop.set()
        self.wake.set()
        if self.worker:
            self.worker.join()

    @staticmethod
    def location(db):
        row = db.execute("SELECT place FROM news_setting WHERE id=1").fetchone()
        return row[0] if row else ""

    def choose(self, place):
        if place and (place not in EDITIONS or place == GLOBAL):
            raise ValueError("Choose a listed edition")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO news_setting VALUES(1,?)", (place,))
        self.wake.set()

    def refresh(self, db, edition):
        now = int(time())
        def read(source):
            name,url,domain=source
            root=ElementTree.fromstring(fetch(url,3_000_000))
            rows=[]
            art=[]
            for item in root.findall(".//{*}item")[:16]:
                link=urlsplit(item.findtext("{*}link") or "")
                title=item.findtext("{*}title") or ""
                if link.scheme not in ("http","https") or not publishers.matches(link.geturl(),domain) or not title:continue
                value=item.findtext("{*}pubDate") or item.findtext("{*}date") or ""
                try:stamp=int(parsedate_to_datetime(value).timestamp())
                except (TypeError,ValueError,OverflowError):
                    try:stamp=int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp())
                    except (ValueError,OverflowError):stamp=now
                summary=unescape(re.sub(r"<[^>]*>"," ",item.findtext("{*}description") or ""))
                candidates=[node.get("url","") for node in item.iter() if node.tag.split("}")[-1] in {"thumbnail","content","enclosure"} and not (node.get("type") or "").startswith(("audio","video"))]
                thumbnail=next((url for url in candidates if media_previews.permitted(url)),"")
                if thumbnail:art.append((link._replace(scheme="https",fragment="").geturl(),thumbnail))
                rows.append((edition,link._replace(scheme="https",fragment="").geturl(),title," ".join(summary.split())[:1500],stamp))
            if not rows:raise ValueError("Empty feed")
            return rows,art
        available=0
        sources=publishers.feeds(edition,EDITIONS[edition])
        with ThreadPoolExecutor(max_workers=5) as pool:
            jobs={}
            for source in sources:
                key=edition+" · "+source[0]
                last=db.execute("SELECT attempt,success,error FROM news_check WHERE edition=?",(key,)).fetchone()
                if last and now-last[0]<900:
                    available+=int(bool(last[1] and not last[2]))
                else:
                    jobs[pool.submit(read,source)]=key
            if not jobs:return
            for job,key in jobs.items():
                try:
                    rows,art=job.result()
                    with db:
                        db.executemany("INSERT OR REPLACE INTO news_art VALUES(?,?)",art)
                        db.executemany("""INSERT INTO news_story(edition,link,title,summary,published) VALUES(?,?,?,?,?)
                            ON CONFLICT(edition,link) DO UPDATE SET title=excluded.title,summary=excluded.summary,published=excluded.published""",rows)
                        db.execute("INSERT OR REPLACE INTO news_check VALUES(?,?,?,'')",(key,now,now))
                    available+=1
                except (OSError,HTTPException,ValueError,ElementTree.ParseError):
                    with db:
                        db.execute("""INSERT INTO news_check VALUES(?,?,NULL,'Refresh unavailable') ON CONFLICT(edition)
                            DO UPDATE SET attempt=excluded.attempt,error=excluded.error""",(key,now))
        with db:
            db.execute("""INSERT INTO news_check VALUES(?,?,?,?) ON CONFLICT(edition) DO UPDATE SET
                attempt=excluded.attempt,success=coalesce(excluded.success,success),error=excluded.error""",
                (edition,now,now if available else None,"" if available else "Refresh unavailable"))
            db.execute("""DELETE FROM news_story WHERE edition=? AND id NOT IN
                (SELECT id FROM news_story WHERE edition=? ORDER BY published DESC,id DESC LIMIT 450)""",(edition,edition))

    def fill_articles(self, db, edition):
        rows = db.execute("""SELECT id,link FROM news_story WHERE edition=? AND body=''
            ORDER BY published DESC,id DESC LIMIT 16""", (edition,)).fetchall()
        for key, link in rows:
            if self.stop.is_set() or self.wake.is_set():
                break
            if publishers.publisher(link)=="BBC News" and "/articles/" not in urlsplit(link).path:
                continue
            try:
                parser = Paragraphs()
                original = fetch(link, 4_000_000)
                parser.feed(original.decode("utf-8", "replace"))
                if parser.lines:
                    with db:
                        db.execute("INSERT OR REPLACE INTO news_original VALUES(?,?,?,?)",(key,link,int(time()),original))
                        db.execute("DELETE FROM news_original WHERE id NOT IN (SELECT id FROM news_story) OR id IN (SELECT id FROM (SELECT id,sum(length(body)) OVER(ORDER BY acquired DESC,id DESC) total FROM news_original) WHERE total>?)",(32*1024**2,))
                        db.execute("UPDATE news_story SET body=? WHERE id=?", ("\n\n".join(parser.lines)[:150000],key))
            except (OSError, HTTPException, ValueError):
                continue

    def run(self):
        with closing(sqlite3.connect(self.path, timeout=15)) as db:
            while not self.stop.is_set():
                self.wake.clear()
                editions = [GLOBAL]
                place = self.location(db)
                if place:
                    editions.append(place)
                for edition in editions:
                    if not self.stop.is_set():
                        self.refresh(db, edition)
                for edition in reversed(editions):
                    self.fill_articles(db, edition)
                self.wake.wait(900)

    @staticmethod
    def field_notes(slug=None):
        photos = json.loads((Path(__file__).parent/"vendor/picture-samples/credits.json").read_text())
        notes = {
            "96549557": ("Reading the horizon at Aberdeen beach", "The turbines in this view sit offshore. Look at the distance between their towers and then at the angle of the blades. A single photograph records their positions at one instant. It takes a sequence of observations to see their rotation or estimate wind direction."),
            "15728898": ("A mountain inside Tycho crater", "When a large impact excavates a crater, rock beneath the impact can rebound and form peaks in the centre. This Lunar Reconnaissance Orbiter image shows one of those peaks. The boundary between sunlight and shadow makes the relief visible even without a scale bar."),
            "19144988": ("Aurora above the Lyngen Alps", "The mountains and water in this photograph reflect moonlight. The light high above them has a different origin. Charged particles following Earth's magnetic field collide with atoms and molecules in the upper atmosphere, which emit light as they lose energy.")
        }
        cards=[]
        for photo in photos:
            key=Path(photo["file"]).stem
            if key not in notes:continue
            title,body=notes[key]
            asset="/content-file/"+sha256(photo["source"].encode()).hexdigest()
            image=f'<img loading=lazy class=personal-picture src="{asset}" alt="{escape(photo["title"],quote=True)}">'
            if key==slug:
                return (f'<a href="/news">Back to News</a><article class="reader news-story"><small>Offline field notes · EchoOffGrid</small><h2>{title}</h2>'
                        f'{image}<p>{escape(body)}</p><small>{escape(photo["artist"])} · {escape(photo["license"])}</small></article>')
            cards.append(f'<a class="tile" href="/news/field-notes/{key}">{image}<strong>{title}</strong></a>')
        return "" if slug else '<section><h3>Offline field notes</h3><div class="collection">'+"".join(cards)+'</div></section>'

    def render(self, token, home=False):
        with closing(sqlite3.connect(self.path)) as db:
            place = self.location(db)
            sections = []
            for edition in [e for e in (place, GLOBAL) if e]:
                status = db.execute("SELECT success,error FROM news_check WHERE edition=?", (edition,)).fetchone()
                stamp = date_label(status[0]) if status and status[0] else ""
                state = ("Refresh unavailable · " if status and status[1] else "") + ("Last saved " + stamp if stamp else "Waiting for first download")
                stories = db.execute("""SELECT id,title,summary,published,link FROM news_story
                    WHERE edition=? ORDER BY published DESC,id DESC LIMIT ?""", (edition,1 if home else 100)).fetchall()
                cards = self.story_cards(stories)
                layout = (f'<div class="collection">{cards}</div>' if home else
                          carousel(edition + " headlines", cards, "news-grid"))
                sections.append(f'<section class="edition"><h3>{escape(edition)}</h3><small>{state}</small>{layout}</section>')
        if not home or not stories:
            sections.append(self.field_notes())
        if home:
            return '<section class="news-home"><div class=section-head><h2>News</h2><a href="/news">Open newsroom →</a></div>' + "".join(sections) + '</section>'
        options = ''.join(f'<option{" selected" if e==place else ""}>{escape(e)}</option>' for e in sorted(EDITIONS) if e != GLOBAL)
        return (f'<form method=post action="/news/location"><input type=hidden name=token value="{escape(token)}">'
                f'<label>Regional edition <select name=place><option value="">Choose a location</option>{options}</select></label> '
                '<button>Save location</button></form><small>Checks every 15 minutes while EchoOffGrid is running. '
                'Saved stories are available offline on this device.</small><section id="archive-live">' + "".join(sections) + '</section><small id="connection-status" role=status></small>')

    @staticmethod
    def story_cards(stories):
        return "".join(
            f'<a class="tile result-card news-card" href="/news/{key}">{media_previews.tag("story-"+str(key),title)}<small>{escape(publishers.publisher(link))} · {date_label(pub)}</small>'
            f'<strong>{escape(title)}</strong><p>{escape(summary or "")}</p></a>'
            for key, title, summary, pub, link in stories)

    def story(self, key):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT title,summary,body,edition,published,link FROM news_story WHERE id=?", (key,)).fetchone()
            related = db.execute("""SELECT id,title,summary,published,link FROM news_story
                WHERE edition=? AND id<>? ORDER BY published DESC,id DESC LIMIT 12""",
                (row[3], key)).fetchall() if row else []
        if not row:
            return None
        title,summary,body,edition,published,link = row
        paragraphs = ''.join('<p>'+escape(p)+'</p>' for p in (body or summary).split('\n\n'))
        return (f'<a href="/news">← News</a><article class="reader news-story">{media_previews.tag("story-"+str(key),title,True)}<h2>{escape(title)}</h2>'
                f'<small>{escape(publishers.publisher(link))} · {escape(edition)} · {date_label(published)}</small>'
                f'<small>{"Saved article text" if body else "Saved feed summary"}</small>{paragraphs}</article>'
                f'<small>Publisher source · {escape(link)}</small>' +
                ('<section class="edition"><h3>More from ' + escape(edition) + '</h3>' +
                 carousel("Related articles", self.story_cards(related), "news-grid") + '</section>' if related else ''))
