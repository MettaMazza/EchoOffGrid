"""Serve the EchoOffGrid setup and archive on localhost."""
import argparse
from contextlib import closing
import csv
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
import fcntl
import discovery
import library_sources
import spotlight
from urllib.error import HTTPError, URLError
from email.utils import parsedate_to_datetime
import http.client
import private_browser
import media_previews
import history_view
from intel import screen as intel_screen
from intel.service import Intel
import opengov
import opencorpo
import personal_library
import narrator
from news import News
import hashlib
import hmac
from html import escape
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
import os
import re
from pathlib import Path
import secrets
from shutil import copyfileobj
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from threading import Event, Lock, Thread
from time import monotonic
from urllib.parse import parse_qs, quote, urlencode, urlsplit, unquote

from archive import CATALOG, binary_format, connect, eligible, feed_text, fetch, search
try:
    import storage_policy
except ModuleNotFoundError:
    from android import storage_policy
from wiki_editions import Editions
from references import Wiki, dictionary
from kit_library import GROUPS, audio_cover, carousel, category_grid, kit_cards, listing, poster, resolve_asset, send_asset, viewer
from evidence import KitReceptionLogs, DEFAULT_DATABASE, MAX_LOG_BYTES, capture_receiver, import_records, import_scotmesh, normalized_time, timeline


STYLE = """
:root{color-scheme:dark;font:16px/1.55 system-ui;background:#09110f;color:#e7f5ef;--mint:#91f4c7;--line:#274439;--panel:#111e19;--muted:#a4bcb1}
*{box-sizing:border-box}
html{cursor:default}
a[href],summary,button:enabled,select,input[type=checkbox],input[type=file],label:has(input[type=checkbox]){cursor:pointer}
textarea:enabled,input:not([type]):enabled,input[type=text]:enabled,input[type=search]:enabled,.reader,pre{cursor:text}
body{max-width:72rem;margin:0 auto;padding:1.75rem clamp(1rem,5vw,3rem) 4rem}
a{color:var(--mint);text-underline-offset:.2em}a:hover{color:#c7ffe4}
header{border-bottom:1px solid var(--line);margin-bottom:2rem;padding-bottom:1rem}
h1{font:700 clamp(1.6rem,5vw,2.35rem)/1.2 ui-monospace,monospace;color:var(--mint);margin:0 0 1rem;letter-spacing:-.055em}
h1::before{content:"";display:inline-block;width:.5em;height:.5em;background:var(--mint);box-shadow:.15em .15em 0 #356950;margin-right:.65em;vertical-align:.13em}
nav{display:flex;flex-wrap:wrap;align-items:center;gap:.5rem 1rem}
header nav a{text-decoration:none;padding:.35rem .6rem;border:1px solid transparent}
header nav a:hover,header nav a[aria-current=page]{background:var(--panel);border-color:var(--line)}
h2{font-size:clamp(1.55rem,4vw,2rem);line-height:1.2;margin:0 0 1rem}
h3,legend{color:var(--mint);font:600 .95rem/1.4 ui-monospace,monospace}
fieldset,article,details{border:1px solid var(--line);background:var(--panel);border-radius:.35rem;padding:1rem;margin:1rem 0}
article strong{font-size:1.08rem}article p:empty{display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,15rem),1fr));gap:.65rem}
label{display:block;padding:.65rem;background:#14251d;border:1px solid #234233;border-radius:.25rem;overflow-wrap:anywhere}
small{display:block;color:var(--muted);margin:.35rem 0}
button,input,select,textarea{font:inherit;accent-color:var(--mint)}
button{background:var(--mint);color:#0a1d14;font-weight:650;border:1px solid transparent;border-radius:.25rem;padding:.5rem .85rem;cursor:pointer}
button:hover{background:#beffdd}button:disabled{cursor:default;opacity:.6}
input:not([type=checkbox]),select,textarea{color:inherit;background:#08110d;border:1px solid var(--line);border-radius:.25rem;padding:.45rem .55rem;max-width:100%}
input[type=search]{width:min(65%,24rem)}textarea{width:100%;resize:vertical}
:focus-visible{outline:2px solid var(--mint);outline-offset:3px}
.reader{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55}
#download-state{margin:1rem 0}#download-state ul{padding-left:1.25rem}
.hero{padding:clamp(1.2rem,4vw,2.6rem);background:linear-gradient(120deg,#14261d,#101e18 62%);border:1px solid var(--line);margin-bottom:1.2rem}
.hero p{max-width:38rem;color:var(--muted)}.hero strong{color:var(--mint)}
.launchpad,.collection{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,17rem),1fr));gap:.8rem}
.tile,.collection article{padding:1rem;margin:0;min-width:0}
.tile{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:.35rem}
.tile:hover,.tile:focus-visible{border-color:var(--mint);background:#182d22;color:inherit}
.tile strong{color:var(--mint);font-size:1.05rem}.tile small{margin-top:.4rem}
.tag{color:var(--mint);font:600 .75rem ui-monospace,monospace}
.card-actions{display:flex;gap:.6rem;flex-wrap:wrap}.card-actions a{font-size:.9rem}
video,audio{width:100%;max-width:64rem}video{max-height:72vh;background:#000}.kit-document{width:100%;height:72vh;border:0}.activity{margin-top:1rem}.status-line{color:var(--muted)}

.shelf{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,12rem),1fr));gap:1.2rem;margin:1rem 0 2rem}
.item{display:flex;flex-direction:column;justify-content:end;text-decoration:none;color:inherit;min-width:0;overflow-wrap:anywhere;border-bottom:1px solid var(--line);padding:.6rem 0}
.item:hover,.item:focus-visible{color:var(--mint);transform:translateY(-2px)}
.item img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:.4rem;margin-bottom:.5rem}
.books{grid-template-columns:repeat(auto-fill,minmax(min(100%,9rem),1fr));gap:1.4rem .7rem}
.books .item{font:600 1.15rem/1.23 Georgia,serif;padding:1.3rem .8rem .85rem 1.25rem;min-height:12rem;background:linear-gradient(90deg,#0005 4%,transparent 6%),#284b48;color:#fbf3dc;border-radius:2px 6px 6px 2px;box-shadow:0 4px #4b4133,inset 0 -3px #ddcfac;border-left:4px solid #ffffff21}
.books .item:nth-child(3n+2){background-color:#46405c}.books .item:nth-child(3n){background-color:#724837}
.books small{font:normal .8rem system-ui;color:#fff8df}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin-top:2rem}
.section-head h2{font-size:1.45rem;margin:0}.pills{display:flex;flex-wrap:wrap;gap:.55rem;margin:1rem 0}.pills a{border-radius:2rem;padding:.35rem .8rem;background:var(--panel);text-decoration:none;border:1px solid var(--line)}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:1rem 0}
.metrics a{display:grid;align-content:start;padding:1rem;color:inherit;background:var(--panel);text-decoration:none}.metrics b{font:600 1.4rem ui-monospace,monospace;color:var(--mint)}.metrics small{margin:0}
.update{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;padding:.6rem 0;border-bottom:1px solid var(--line);text-decoration:none}.update small{white-space:nowrap}.event{border:0;border-left:3px solid var(--mint);border-radius:0;margin:.35rem 0;padding:.65rem 1rem}.event details{padding:.35rem .7rem;margin:.35rem 0}
.lanes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem;margin:1rem 0 1.6rem}.lanes section{padding:1.1rem 1.25rem;border-top:3px solid #84d8b2;background:linear-gradient(130deg,#183329,#111d18)}.lanes section:nth-child(2){border-color:#a6afde}.lanes h3{margin:0 0 .65rem}.lanes b{font-size:1.7rem}.lanes h3 b{float:right}.job{border-top:1px solid var(--line);padding:.55rem 0}.scroll-table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:.65rem .55rem;border-bottom:1px solid var(--line)}thead th{color:var(--mint)}.source-group{background:transparent;border-width:0 0 1px;padding:.65rem 0}.source-group summary{font-weight:650;color:var(--mint);margin-bottom:.7rem}.source-group summary small{display:inline;margin-left:.5rem}.regions .grid{display:flex;flex-wrap:wrap}.regions label{border-radius:2rem}.regions label:has(:checked),.source-group label:has(:checked){background:#234834;border-color:#5e9c7d}
.result-card{display:grid;grid-template-rows:auto 1fr auto;border-top:3px solid #8bd6b5;padding:1.15rem}.result-card p{color:#d1e7dc;font-size:.96rem;line-height:1.5;margin:.7rem 0}.result-card time{font:500 .8rem ui-monospace,monospace}.result-card:nth-child(2){border-top-color:#acb9e8}.result-card:nth-child(3){border-top-color:#dcbe85}
.cart-bar{position:sticky;bottom:.5rem;background:#142a20;padding:.75rem 1rem;border:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:1rem}#discover-results label{cursor:pointer}#discover-results label:has(:checked){border-color:var(--mint);background:#203d30}#discover-results{margin:1rem 0}#discover-results p{font-size:.92rem;line-height:1.45}.pills a[aria-current=true]{box-shadow:inset 0 0 0 1px var(--mint)}
[hidden]{display:none!important}

"""

LIVE_UPDATES = """
(() => {
    const grid=document.querySelector('#discover-results');
    const more=document.querySelector('#more-titles');
    if(grid){
        const form=grid.closest('form');
        let edits=Promise.resolve();
        grid.addEventListener('change',event=>{
            const box=event.target;
            if(box.name!=='item')return;
            const body=new URLSearchParams({token:form.elements.token.value,item:box.value,checked:box.checked?'1':'0'});
            edits=edits.then(async()=>{
                const r=await fetch('/discover/pick',{method:'POST',body,keepalive:true});
                if(!r.ok)throw Error();
                document.querySelector('#cart-count').textContent=(await r.text())+' selected';
            }).catch(()=>{box.checked=!box.checked;document.querySelector('#cart-count').textContent='Selection could not be saved';});
        });
        form.addEventListener('submit',async event=>{
            event.preventDefault();await edits;
            for(const box of grid.querySelectorAll('input[name=item]'))box.disabled=true;
            form.submit();
        });
    }
    if(grid && more) {
        let loading=false;
        async function appendPage(event) {
            if(event)event.preventDefault();
            if(loading || more.hidden)return;
            loading=true;
            more.textContent='Loading titles…';
            try{
                const response=await fetch(more.href);
                if(!response.ok)throw Error();
                const doc=new DOMParser().parseFromString(await response.text(),'text/html');
                const next=doc.querySelector('#discover-results');
                if(!next?.children.length)throw Error();
                grid.append(...Array.from(next.children));
                const following=doc.querySelector('#more-titles');
                if(following)more.href=following.getAttribute("href");
                else more.hidden=true;
                more.textContent='More titles →';
            }catch{more.textContent='Try loading more titles';}
            finally{loading=false;}
        }
        more.addEventListener('click',appendPage);
        const observer=new IntersectionObserver(entries=>{
            if(entries[0].isIntersecting && window.scrollY>0)appendPage();
        });
        observer.observe(more);
    }
    const filter = document.querySelector('#shelf-search');
    if (filter) filter.addEventListener('input', () => {
        let shown = 0;
        document.querySelectorAll('.shelf .item').forEach(item => {
            item.hidden = !item.textContent.toLowerCase().includes(filter.value.trim().toLowerCase());
            if (!item.hidden) shown++;
        });
        document.querySelector('#match-count').textContent = shown + ' matching titles';
    });
    const catalog = document.querySelector('#catalog-search');
    if (catalog) {
        const form = catalog.form;
        const sources = [...form.querySelectorAll('input[name=source]')];
        function updateCatalog() {
            const query = catalog.value.trim().toLowerCase();
            for (const input of sources) {
                const label = input.closest('label');
                label.hidden = !label.textContent.toLowerCase().includes(query);
            }
            for (const group of form.querySelectorAll('.source-group')) {
                group.hidden = !group.querySelector('label:not([hidden])');
            }
            form.querySelector('output').textContent = sources.filter(input => input.checked).length + ' selected';
        }
        form.addEventListener('input', updateCatalog);
        updateCatalog();
    }
    const chat = document.querySelector('#echolite-chat');
    if (chat) {
        chat.addEventListener('submit', () => {
            chat.querySelector('button').disabled = true;
            chat.querySelector('[role=status]').textContent = 'EchoLite is responding…';
        });
    }
    const live = document.querySelector('#archive-live');
    if (!live) return;
    const notice = document.querySelector('#connection-status');
    let previousMarkup=live.innerHTML;
    async function update() {
        try {
            const response = await fetch(live.dataset.url || location.href, {cache: 'no-store'});
            if (!response.ok) throw new Error('Archive unavailable');
            const doc=new DOMParser().parseFromString(await response.text(),'text/html');
            const replacement=doc.querySelector('#archive-live');
            const news=document.querySelector('#home-news'), fresh=doc.querySelector('#home-news');
            if(news && fresh && !news.contains(document.activeElement) && news.innerHTML!==fresh.innerHTML) news.replaceChildren(...fresh.childNodes);
            if (!replacement) throw new Error('Archive section missing');
            if (!live.contains(document.activeElement) && previousMarkup !== replacement.innerHTML) {
                previousMarkup = replacement.innerHTML;
                const oldActivity = live.querySelector('#activity');
                const newActivity = replacement.querySelector('#activity');
                if (oldActivity && newActivity) newActivity.open = oldActivity.open;
                const offsets = new Map(Array.from(live.querySelectorAll('.rail'), el => [el.getAttribute('aria-label'), el.scrollLeft]));
                live.replaceChildren(...replacement.childNodes);
                live.querySelectorAll('.rail').forEach(el => { el.scrollLeft = offsets.get(el.getAttribute('aria-label')) || 0; });
                live.dispatchEvent(new Event('railschanged', {bubbles:true}));
            }
            notice.textContent = '';
        } catch {
            notice.textContent = 'Waiting for EchoOffGrid to reconnect…';
        } finally {
            setTimeout(update, document.hidden ? 10000 : 2000);
        }
    }
    setTimeout(update, 1500);
})();
"""


STYLE += Path(__file__).with_name("workspace.css").read_text()
STYLE += (intel_screen.ROOT/"style.css").read_text()
LIVE_UPDATES += Path(__file__).with_name("workspace.js").read_text()
LIVE_UPDATES += Path(__file__).with_name("reader.js").read_text()

CATALOG_KINDS = {"books":"Books","watch":"Films","shows":"Shows","listen":"Audiobooks","software":"Software","games":"Games","pictures":"Pictures"}

# Five-pixel glyphs keep the workstation mark crisp at integer display scales.
PIXELS = {
    "E": ("11111","10000","10000","11110","10000","10000","11111"),
    "C": ("01111","10000","10000","10000","10000","10000","01111"),
    "H": ("10001","10001","10001","11111","10001","10001","10001"),
    "O": ("01110","10001","10001","10001","10001","10001","01110"),
    "F": ("11111","10000","10000","11110","10000","10000","10000"),
    "G": ("01111","10000","10000","10111","10001","10001","01110"),
    "R": ("11110","10001","10001","11110","10100","10010","10001"),
    "I": ("11111","00100","00100","00100","00100","00100","11111"),
    "D": ("11110","10001","10001","10001","10001","10001","11110"),
}
def pixel_mark():
    word = "ECHOOFFGRID"
    path = "".join(f"M{i*6+x} {y}h1v1h-1z" for i,char in enumerate(word)
                   for y,row in enumerate(PIXELS[char]) for x,bit in enumerate(row) if bit=="1")
    return f'<svg aria-hidden="true" viewBox="0 0 {len(word)*6-1} 7" shape-rendering="crispEdges"><path fill="currentColor" d="{path}"/></svg>'

WORKSTATION_MARK = pixel_mark()

def page(section, body, token=""):
    links = [("/", "Home"), ("/library", "Library"), ("/news","News"), ("/openintel","OpenIntel"), ("/opengov","OpenGov"), ("/opencorpo","OpenCorpo"), ("/history","History"), ("/wikipedia", "Wikipedia"),
             ("/dictionary", "Dictionary"), ("/maps", "Maps"), ("/downloads", "Downloads"),
             ("/private-browser","Private Browser"), ("/echolite", "EchoLite"), ("/devices", "Devices")]
    primary = {"Compare packets":"Devices","Receiver log":"Devices","ScotMesh reports":"Devices",
               "Documents":"Library","Games":"Library","Discover":"Library","Software":"Library","Regional feeds":"Library"}
    navigation = "".join(
        f'<a href="{href}"{" aria-current=page" if title == primary.get(section,section) or (title == "Library" and section in ["Saved sources", *[item[0] for item in GROUPS.values()]]) else ""}>{title}</a>'
        for href, title in links
    )
    return f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=color-scheme content=dark><meta name=viewport content="width=device-width,initial-scale=1">
<title>{escape(section)} | EchoOffGrid</title><style>{STYLE}</style>
<script defer src="/dashboard.js"></script>
<header class="workstation-header"><h1><a class="brand" href="/" aria-label="EchoOffGrid home">{WORKSTATION_MARK}<span>EchoOffGrid</span></a></h1><button type=button class="workstation-back" aria-label="Back to previous page">‹ Back</button><button class="reader-toggle" aria-expanded="false" aria-controls="reader-tools">Reader</button><nav aria-label="Dashboard">{navigation}</nav></header>
<aside id="reader-tools" class=speech aria-label="Audio reader" data-token="{escape(token)}">
<button id=read-all>Read all</button><button id=read-pause disabled>Pause</button><button id=read-stop disabled>Stop</button>
<input id=read-seek type=range min=0 max=1000 value=0 aria-label="Playback position" disabled><span id=read-clock>0:00</span>
<select id=read-speed aria-label="Playback speed"><option>0.75×</option><option selected>1×</option><option>1.25×</option><option>1.5×</option><option>2×</option></select>
<output id=read-status role=status>Emma · Offline voice</output></aside>
<div id=read-selection hidden><a id=define-selection hidden>Look up word</a><button id=speak-selection>▶ Play selection</button></div>
<main>{f"<h2>{escape(section)}</h2>" if section not in {"Home","OpenIntel"} else ""}{body}</main></html>"""


def checkbox(name, value, label, selected, detail=""):
    checked = " checked" if value in selected else ""
    info = f"<small>{escape(detail)}</small>" if detail else ""
    return (f'<label><input type="checkbox" name="{name}" value="{escape(value)}"{checked}> '
            f'{escape(label)}{info}</label>')


class Downloads:
    def __init__(self, database_path, catalog):
        self.database_path = database_path
        self.sources = {item["id"]: item for item in catalog["sources"]}
        self.wakeup = Event()
        self.stopping = Event()
        self.next_refresh_check = 0
        with closing(connect(database_path)) as database, database:
            database.execute("""
                CREATE TABLE IF NOT EXISTS refresh_preference (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    enabled INTEGER NOT NULL
                )
            """)
            discovery.init(database)
            spotlight.seed(database)
            opengov.seed(database,database_path.parent)
            opencorpo.seed(database,database_path.parent)
            database.execute("UPDATE discovery_item SET kind='Games' WHERE kind='Emulators'")
            personal_library.seed_pictures(database,database_path.parent)
            database.execute("CREATE INDEX IF NOT EXISTS fetch_source_time ON fetch(source, checked_at)")
            database.execute("""
                CREATE TABLE IF NOT EXISTS pending_download (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'Queued'
                )
            """)
            database.execute("""CREATE TABLE IF NOT EXISTS content_download (
                id INTEGER PRIMARY KEY, source TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'Queued')""")
            database.execute("CREATE TABLE IF NOT EXISTS download_backoff(source TEXT PRIMARY KEY, due INTEGER, attempts INTEGER)")
            # Older workstation processes only understand feed IDs in pending_download.
            database.execute("""INSERT OR IGNORE INTO content_download(source,title,state)
                SELECT source,title,CASE WHEN state='Interrupted: ' || quote(source) OR state='Downloading'
                    THEN 'Queued' ELSE state END FROM pending_download WHERE source LIKE 'discover-%'""")
            database.execute("DELETE FROM pending_download WHERE source LIKE 'discover-%'")
            database.execute("CREATE TABLE IF NOT EXISTS chosen_download(source TEXT PRIMARY KEY,title TEXT NOT NULL,snapshot_id INTEGER)")
            database.execute("CREATE TABLE IF NOT EXISTS chosen_feed_job(source TEXT PRIMARY KEY)")
            database.execute("CREATE TRIGGER IF NOT EXISTS clear_chosen_feed AFTER DELETE ON pending_download BEGIN DELETE FROM chosen_feed_job WHERE source=OLD.source; END")
            database.execute("INSERT OR IGNORE INTO chosen_download(source,title) SELECT source,title FROM content_download")
        self.worker = Thread(target=self.run, daemon=True, name="EchoOffGrid downloads")
        self.worker.start()

    @staticmethod
    def enqueue(database, sources):
        for item in sources:
            database.execute("INSERT OR IGNORE INTO chosen_download(source,title) VALUES(?,?)",(item["id"],item["title"]))
            if not item["id"].startswith("discover-"):
                database.execute("INSERT OR IGNORE INTO chosen_feed_job VALUES(?)",(item["id"],))
            database.execute("DELETE FROM cancelled_transfer WHERE source=?",(item["id"],))
            table = "content_download" if item["id"].startswith("discover-") else "pending_download"
            database.execute(f"""INSERT INTO {table}(source,title) VALUES(?,?)
                ON CONFLICT(source) DO UPDATE SET state='Queued'
                WHERE state NOT IN ('Queued','Downloading')""",(item["id"],item["title"]))

    def progress(self, database):
        return database.execute("""SELECT jobs.source,title,state,received,total,b.due AS retry_due,
            (jobs.source LIKE 'discover-%' OR EXISTS(SELECT 1 FROM chosen_feed_job m WHERE m.source=jobs.source)) AS chosen FROM (
            SELECT * FROM pending_download UNION ALL SELECT * FROM content_download
        ) jobs LEFT JOIN transfer_progress ON transfer_progress.id=jobs.source LEFT JOIN download_backoff b ON b.source=jobs.source ORDER BY jobs.id""").fetchall()

    def queue_due_sources(self, database):
        if monotonic() < self.next_refresh_check:
            return
        self.next_refresh_check = monotonic() + 60
        row = database.execute("""
            SELECT selection.sources
            FROM refresh_preference JOIN selection USING (id)
            WHERE refresh_preference.enabled = 1
        """).fetchone()
        if row is None:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        for source_id in json.loads(row["sources"]):
            source = self.sources.get(source_id)
            if source is None or source["kind"] == "Books":
                continue
            recent = database.execute("""
                SELECT 1 FROM fetch WHERE source=? AND checked_at>? LIMIT 1
            """, (source_id, cutoff)).fetchone()
            if recent is None:
                database.execute("""
                    INSERT OR IGNORE INTO pending_download(source,title) VALUES (?,?)
                """, (source_id, source["title"]))

    @staticmethod
    def remove_local(db,root,key):
        if not re.fullmatch(r"(?:personal-)?[0-9a-f]{64}",key):
            raise ValueError("Invalid library item")
        # Managed files use this exact key followed by an extension or a part suffix.
        for file in root.glob(key+"*"):
            if file.name.startswith((key+".",key+"-")) and file.is_file():
                file.unlink(missing_ok=True)
                (root/".thumbnails"/(file.name+".jpg")).unlink(missing_ok=True)
        db.execute("INSERT OR IGNORE INTO removed_item VALUES(?)",(key,))
        for table in ("discovery_file","series_parts","discovery_cart","remove_download"):
            db.execute(f"DELETE FROM {table} WHERE id=?",(key,))
        db.execute("UPDATE discovery_item SET filename=NULL WHERE id=?",(key,))
        for table,col in (("content_download","source"),("download_backoff","source"),("transfer_progress","id")):
            db.execute(f"DELETE FROM {table} WHERE {col}=?",("discover-"+key,))

    def run_one(self):
        database_path = self.database_path.resolve()
        lock_path = database_path.with_name(database_path.name + ".download.lock")
        with lock_path.open("ab") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            with closing(connect(self.database_path)) as database:
                # The OS releases the lock when the previous worker exits.
                with database:
                    for (source,) in database.execute("SELECT source FROM cancelled_transfer").fetchall():
                        for table in ("content_download","pending_download","download_backoff","cancelled_transfer"):
                            database.execute(f"DELETE FROM {table} WHERE source=?",(source,))
                        database.execute("DELETE FROM transfer_progress WHERE id=?",(source,))
                    for (key,) in database.execute("SELECT id FROM remove_download").fetchall():
                        self.remove_local(database,database_path.parent/"Content",key)
                    self.queue_due_sources(database)
                    for table in ("content_download", "pending_download"):
                        database.execute(f"UPDATE {table} SET state='Queued' WHERE state='Downloading'")
                        row = database.execute(f"SELECT id,source FROM {table} WHERE state='Queued' AND NOT EXISTS (SELECT 1 FROM download_backoff b WHERE b.source={table}.source AND b.due>strftime('%s','now')+0) ORDER BY id LIMIT 1").fetchone()
                        if row is not None:
                            break
                    if row is None:
                        return False
                    database.execute(f"UPDATE {table} SET state='Downloading' WHERE id=?", (row["id"],))
                try:
                    if row["source"].startswith("discover-"):
                        item = database.execute("SELECT * FROM discovery_item WHERE id=?", (row["source"][9:],)).fetchone()
                        if item is None:
                            raise ValueError("Catalogue entry missing")
                        if discovery.download(database, database_path.parent / "Content", item) is False:
                            # Give each selected series a turn after one episode.
                            with database:
                                database.execute("DELETE FROM content_download WHERE id=?",(row["id"],))
                                if not database.execute("SELECT 1 FROM cancelled_transfer WHERE source=?",(row["source"],)).fetchone():
                                    self.enqueue(database,[{"id":row["source"],"title":item["title"]}])
                            return True
                    else:
                        result = fetch(database, self.sources[row["source"]])
                        if "error" in result:
                            raise ValueError(result["error"])
                except HTTPError as error:
                    with database:
                        prior=database.execute("SELECT attempts FROM download_backoff WHERE source=?",(row["source"],)).fetchone()
                        attempts=(prior[0] if prior else 0)+1
                        if error.code in {429,502,503,504} and attempts<=5:
                            delay=60*2**(attempts-1)
                            retry=error.headers.get("Retry-After","")
                            if retry.isdecimal():delay=max(delay,int(retry))
                            elif retry:
                                try:delay=max(delay,int(parsedate_to_datetime(retry).timestamp()-datetime.now().timestamp()))
                                except (TypeError,ValueError,OverflowError):pass
                            database.execute("INSERT OR REPLACE INTO download_backoff VALUES(?,strftime('%s','now')+?,?)",(row["source"],delay,attempts))
                            database.execute(f"UPDATE {table} SET state='Queued' WHERE id=?",(row["id"],))
                        else:
                            database.execute("DELETE FROM download_backoff WHERE source=?",(row["source"],))
                            database.execute(f"UPDATE {table} SET state=? WHERE id=?",(f"Interrupted: publisher returned HTTP {error.code}",row["id"]))
                except (OSError, HTTPException, ValueError, KeyError) as error:
                    with database:
                        prior=database.execute("SELECT attempts FROM download_backoff WHERE source=?",(row["source"],)).fetchone()
                        attempts=(prior[0] if prior else 0)+1
                        if isinstance(error,(ConnectionError,TimeoutError,HTTPException,URLError)) and attempts<=5:
                            database.execute("INSERT OR REPLACE INTO download_backoff VALUES(?,strftime('%s','now')+?,?)",(row["source"],min(300,5*2**attempts),attempts))
                            database.execute(f"UPDATE {table} SET state='Queued' WHERE id=?",(row["id"],))
                        else:
                            database.execute(f"UPDATE {table} SET state=? WHERE id=?",(f"Interrupted: {error}",row["id"]))
                else:
                    with database:
                        database.execute("DELETE FROM download_backoff WHERE source=?",(row["source"],))
                        if table=="pending_download":
                            database.execute("""UPDATE chosen_download SET snapshot_id=(SELECT snapshot_id FROM fetch WHERE source=? AND error IS NULL ORDER BY id DESC LIMIT 1)
                                WHERE source=? AND source IN (SELECT source FROM chosen_feed_job)""",(row["source"],row["source"]))
                        database.execute(f"DELETE FROM {table} WHERE id=?", (row["id"],))
            return True

    def run(self):
        while not self.stopping.is_set():
            self.wakeup.clear()
            if not self.stopping.is_set() and not self.run_one():
                self.wakeup.wait(2)


class WorkspaceServer(ThreadingHTTPServer):
    downloads = None
    wiki = None
    news = None

    def server_close(self):
        super().server_close()
        if self.downloads:
            self.downloads.stopping.set()
            self.downloads.wakeup.set()
            self.downloads.worker.join()
        if getattr(self,"private_browser",None):
            self.private_browser.close()
        if getattr(self,"intel",None):
            self.intel.close()
        if self.wiki:
            self.wiki.close()
        if self.news:
            self.news.close()


class Dashboard(BaseHTTPRequestHandler):
    def local_request(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def send_page(self, title, body, status=200):
        payload = page(title, body, self.server.token).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self'; media-src 'self' blob:; frame-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def home(self, summary_only=False):
        with closing(connect(self.server.database)) as database:
            self.server.kit_logs.refresh(database)
            saved = database.execute("SELECT count(DISTINCT source) FROM snapshot").fetchone()[0]
            queue = [job for job in self.server.downloads.progress(database) if job["chosen"]]
            last = database.execute("SELECT checked_at FROM fetch ORDER BY id DESC LIMIT 1").fetchone()
            mix="" if summary_only else spotlight.mix(database,spotlight.collection_titles(self.server.kit))
            timeline(database, limit=0)
            activity = dict(database.execute("SELECT category, max(event_at) FROM evidence WHERE category IN ('local_decode','public_packet_feed') GROUP BY category"))
        running = sum(row["state"] in ("Queued", "Downloading") for row in queue)
        metrics = [("/archive", str(saved), "Saved sources", "Last check " + last[0] if last else "Awaiting first download"),
                   ("/downloads", str(running), "Queued or downloading", f"{len(queue)-running} need attention")]
        for kind, title, source in [("local_decode","Last local decode","HackRF"), ("public_packet_feed","Last public packet report","ScotMesh")]:
            stamp = activity.get(kind)
            metrics.append(("/evidence?source=" + source, stamp[11:19] if stamp else "—", title, stamp[:10] + " UTC" if stamp else "No imported observation"))
        stats = "".join(f'<a href="{url}"><b>{escape(value)}</b>{label}<small>{escape(detail)}</small></a>' for url,value,label,detail in metrics)
        live=f'<section id="archive-live" data-url="/home-status"><div class=metrics>{stats}</div>{self.server.intel.home()}</section>'
        newsroom='<div id="home-news">'+self.server.news.render(self.server.token,home=True)+'</div>'
        if summary_only:
            self.send_page("Home",live+newsroom)
            return
        self.send_page("Home", (self.server.editions.panel(self.server.token) if not self.server.editions.choice.exists() else "") + '<div class=section-head><h2>At a glance</h2><span><button class=next id=cycle>Next discovery →</button> <button class=motion id=motion>Pause rotation</button></span></div>' + live + mix + newsroom + '<small id="connection-status" role=status></small>' + self.collections(preview=True))

    def collections(self, preview=False):
        tiles = [
            ("/wikipedia","Wikipedia",f"{len(self.server.wiki.archives)} local reference collections"),
            ("/dictionary","Dictionary","Look up words in the offline dictionary"),
            ("/maps","Maps","Explore the offline atlas"),
            ("/library/games","Games","Open the local puzzle collection"),
            ("/library/software","Software","Open tools or find more software"),
            ("/archive","Regional feeds","Read saved reports and choose feeds")]
        if not preview:
            tiles = [(f"/library/{kind}", title, "Browse your collection") for kind,(title,_,_) in GROUPS.items()] + tiles
        features = "".join(f'<a class=tile href="{url}"><strong>{title}</strong><small>{detail}</small></a>' for url,title,detail in tiles)
        sections = []
        with closing(connect(self.server.database)) as db:
            downloaded = db.execute("SELECT id,title,kind FROM discovery_item WHERE filename IS NOT NULL ORDER BY title").fetchall()
        for kind in ("watch","shows","books","listen"):
            name = GROUPS[kind][0]
            extra = self.download_cards(kind, (row for row in downloaded if row["kind"] == CATALOG_KINDS[kind]))
            items = listing(self.server.kit,kind,on_load=preview,extra_cards=extra)
            if not items:items=self.catalogue_samples(kind)
            if items:
                sections.append(f'<div class=section-head><h2>{name}</h2><a href="/library/{kind}">Browse {name.lower()}</a></div>{items}')
        games = self.game_cards(self.installed_games()) + self.personal_cards(downloaded, {"Games"})
        if games:
            sections.append('<div class=section-head><h2>Games</h2><a href="/library/games">Browse games</a></div>' +
                            carousel("Games", games, "shelf games", "data-on-load" if preview else ""))
        if not games:
            sections.append('<div class=section-head><h2>Games</h2><a href="/library/games">Browse games</a></div>'+self.catalogue_samples("games"))
        document_cards=self.personal_cards(downloaded,{"Documents"})
        sections.append('<div class=section-head><h2>Documents</h2><a href="/library/documents">Browse documents</a></div>'+carousel("Documents",document_cards,"shelf"))
        if preview:
            pictures=self.personal_cards(downloaded,{"Pictures"})
            if pictures:sections.append('<div class=section-head><h2>Pictures</h2><a href="/library/pictures">Browse pictures</a></div>'+carousel("Pictures",pictures,"shelf"))
            topics = [
                ("Wikipedia", [("/wikipedia?q="+word,word,"Search offline articles") for word in ("Aberdeen","Navigation","Astronomy")]),
                ("Dictionary", [("/dictionary?q="+word,word,"Look up the definition") for word in ("waypoint","signal","latitude")]),
                ("Maps", [("/maps","World atlas","Browse the offline map"),("/library/maps","Printable maps","Open a local sheet")]),
                ("Software", [("/library/software","Your tools","Open software in the library"),("/discover?kind=Software","Discover software","Find an open-source tool")]),
            ]
            panels = []
            for label, choices in topics:
                faces = "".join(f'<a class=tile href="{url}"><small>{label}</small><strong>{escape(title)}</strong><span>{caption}</span></a>' for url,title,caption in choices)
                panels.append(f'<div data-on-load data-count="1">{faces}</div>')
            features = "".join(panels)
        features = carousel("Explore your library", features, "feature-grid")
        if preview:
            sections.insert(1,features)
            return "".join(sections)
        software = [row for row in downloaded if row["kind"]=="Software"]
        sections.insert(1, '<div class="section-head"><h2><a class="shelf-title" href="/library/software">Software</a></h2>'
                           '<a href="/library/software">Browse software</a></div>'+self.software_shelf(software))
        pictures=self.personal_cards(downloaded,{"Pictures"})
        sections.append('<div class=section-head><h2><a href="/library/pictures">Pictures</a></h2><a href="/library/pictures">Browse pictures</a></div>'+carousel("Pictures",pictures,"shelf"))
        return features + "".join(sections) + '<a href="/discover">Discover all catalogues</a>'

    def catalogue_samples(self,kind,layout=carousel):
        grouped=CATALOG_KINDS.get(kind)
        if not grouped:return ""
        with closing(connect(self.server.database)) as db:
            rows=db.execute("SELECT id,title,preview,provider FROM discovery_item WHERE kind=? AND filename IS NULL ORDER BY RANDOM() LIMIT 4",(grouped,)).fetchall()
        cards="".join(spotlight.card(spotlight.LABEL[grouped],r["title"],r["preview"],r["provider"],"/discover/item/"+r["id"]) for r in rows)
        return '<small>Available to download</small>'+layout(grouped,cards,"collection") if rows else ""

    def personal_thumb(self,key,title,kind):
        raw="/content-file/"+key
        root=self.server.database.parent/"Content"
        src = ("/personal-cover/"+key if (root/(key+".cover")).is_file() else
               raw if kind=="Pictures" else "/content-poster/"+key if kind in ("Films","Shows") else "")
        if src:
            clip = f' data-clip="{raw}"' if kind in ("Films","Shows") else ""
            return f'<span class="thumb"{clip}><img alt="" loading=lazy src="{src}"></span>'
        symbols={"Games":"✜","Software":"▤","Books":"▥","Pictures":"▧"}
        return audio_cover(title) if kind=="Audiobooks" else f'<span class="personal-cover" aria-hidden=true>{symbols.get(kind,"▤")}</span>'

    def personal_cards(self,rows,kinds):
        return "".join(f'<a class=item href="/content/{r["id"]}">{self.personal_thumb(r["id"],r["title"],r["kind"])}<strong>{escape(r["title"])}</strong></a>'
                       for r in rows if r["kind"] in kinds)

    def download_cards(self, kind, saved):
        cards=[]
        for row in saved:
            url = "/content/" + row["id"]
            thumb = audio_cover(row["title"]) if kind == "listen" else ""
            if kind in ("watch","shows"):
                src = "/content-file/" + row["id"]
                thumb = f'<span class=thumb data-clip="{src}"><img alt="" loading=lazy src="/content-poster/{row["id"]}"></span>'
            if row["id"].startswith("personal-"):
                thumb=self.personal_thumb(row["id"],row["title"],personal_library.SHELVES[kind])
            cards.append(f'<a class=item href="{url}">{thumb}<strong>{escape(row["title"])}</strong></a>')
        return "".join(cards)

    def up_next(self, current):
        items=[]
        with closing(connect(self.server.database)) as db:
            for shelf in ("watch","shows"):
                rows=db.execute("SELECT id,title FROM discovery_item WHERE kind=? AND filename IS NOT NULL ORDER BY title,id",(CATALOG_KINDS[shelf],))
                items.extend(("/content/"+row["id"],self.download_cards(shelf,[row])) for row in rows)
                items.extend(kit_cards(self.server.kit,shelf))
        index=next((i for i,item in enumerate(items) if item[0]==current),-1)
        following=items[index+1:]
        suggestions=following+items[:max(index,0)]
        if not suggestions:
            return '<p><a href="/discover?kind=Films">Find more videos</a></p>'
        next_url=escape(following[0][0],quote=True) if following else ""
        return (f'<section class="up-next" data-next="{next_url}"><div class=section-head><h3>Up next</h3>'
                '<label class="autoplay-control">Autoplay next video <input type=checkbox role=switch id=video-autoplay><span class="switch-track" aria-hidden=true></span></label></div>'
                +carousel("Suggested videos","".join(card for _,card in suggestions[:24]),"shelf watch")+'</section>')

    def software_shelf(self, saved, layout=carousel):
        builtins = [("/wikipedia","Kiwix","Offline encyclopedia","W"),
                    ("/atlas/","MapLibre","Offline atlas","⌖"),
                    ("/library/games","Portable Puzzle Collection","Logic games","▦"),
                    ("/library/watch","VLC","Media player","▶")]
        cards = []
        if saved:
            cards.extend(f'<a class="tile item software-card" href="/content/{escape(row["id"])}">{self.personal_thumb(row["id"],row["title"],"Software")}<strong>{escape(row["title"])}</strong></a>' for row in saved)
        cards.extend(f'<a class="tile item software-card" href="{url}"><span aria-hidden="true">{symbol}</span><strong>{title}</strong><small>{detail}</small></a>'
                     for url,title,detail,symbol in builtins)
        return layout("Software","".join(cards),"shelf software")

    def import_form(self,shelf):
        name=personal_library.SHELVES[shelf]
        accepts=personal_library.FORMATS.get(name,"").replace(" ",",")
        label={"watch":"videos","listen":"audio","software":"software"}.get(shelf,name.lower())
        return f'''<details class="import-panel"><summary>Import {label}</summary>
          <form class="personal-import" data-android="{int(getattr(self.server,'android',False))}" action="/library/{shelf}/import" data-token="{self.server.token}">
          <label>Files <input name=files type=file multiple required accept="{accepts}"></label>
          <button>Import {label}</button><output role=status></output></form></details>'''

    def library(self, path):
        kind, _, relative = path.partition("/")
        if not kind:
            self.send_page("Library", self.collections())
            return
        if kind not in personal_library.SHELVES:
            self.send_error(404)
            return
        name = GROUPS[kind][0] if kind in GROUPS else personal_library.SHELVES[kind]
        if relative:
            asset = resolve_asset(self.server.kit, kind, relative)
            if asset is None:
                self.send_error(404)
                return
            self.send_page(asset.stem, f'<p><a href="/library/{kind}">Back to {name}</a></p>' + viewer(kind, relative, asset) + (self.up_next(f'/library/{kind}/{relative}') if kind in ('watch','shows') else ''))
            return
        catalogue = CATALOG_KINDS.get(kind)
        browse = "/discover?" + urlencode({"kind":catalogue}) if catalogue else ("/sources?category=Maps" if kind=="maps" else "/sources?category=Guidance")
        if kind=="documents":browse="/opengov"
        body = f'<div class=section-head><input type=search id=shelf-search aria-label="Filter titles" placeholder="Filter this collection"><a href="{browse}">Browse more {name.lower()} →</a></div><small id=match-count role=status></small>'
        saved = []
        if catalogue:
            with closing(connect(self.server.database)) as db:
                saved=db.execute("SELECT id,title FROM discovery_item WHERE kind=? AND filename IS NOT NULL ORDER BY title",(catalogue,)).fetchall()
        if kind in {"pictures","guides","maps","documents"}:
            with closing(connect(self.server.database)) as db:
                rows=db.execute("SELECT id,kind,title FROM discovery_item WHERE kind=? AND filename IS NOT NULL ORDER BY title",(name,)).fetchall()
            if kind in {"pictures","documents"}:
                body=self.import_form(kind)+body+category_grid(name,self.personal_cards(rows,{name}),"shelf")
                if kind=="documents":body+=self.server.intel.library()
                self.send_page(name,body);return
            saved=rows
        body=self.import_form(kind)+body
        if kind=="software":
            body += self.software_shelf(saved,category_grid)
        else:
            body += listing(self.server.kit,kind,extra_cards=self.download_cards(kind,saved),layout=category_grid) or self.catalogue_samples(kind,category_grid)
        self.send_page(name,body)

    def kit_file(self, path):
        kind, _, relative = path.partition("/")
        asset = resolve_asset(self.server.kit, kind, relative)
        if asset is None:
            self.send_error(404)
            return
        send_asset(self, asset)

    def discover(self, params):
        kind=params.get("kind",["Books"])[0]
        query=params.get("q",[""])[0][:160]
        pg=params.get("page",["1"])[0]
        if kind not in discovery.KINDS or not pg.isascii() or not pg.isdigit() or len(pg)>6 or int(pg)<1:
            self.send_error(400)
            return
        pg=int(pg)
        selected=params.get("provider",[""])[0]
        if selected not in library_sources.PROVIDERS[kind]:selected=""
        base={"kind":kind,"q":query,"provider":selected}
        options='<option value="">All catalogues</option>'+''.join(f'<option{" selected" if source==selected else ""}>{escape(source)}</option>' for source in library_sources.PROVIDERS[kind])
        def link(**values):
            return "/discover?"+escape(urlencode(dict(base,**values)))
        tabs="".join(f'<a href="{link(kind=k,q="",page=1)}" aria-current="{str(k==kind).lower()}">{"Videos" if k=="Films" else k}</a>' for k in discovery.KINDS)
        picks="".join(f'<a href="{link(q=title,page=1)}">{escape(title)}</a>' for title in discovery.PICKS[kind])
        index=Path(__file__).with_name("gutenberg-index.csv.gz")
        items,more,notice=library_sources.browse(self.server.database,kind,query,pg,selected,index)
        starters=discovery.featured(kind)
        with closing(connect(self.server.database)) as db:
            discovery.remember(db,kind,"__featured__",1,starters,False)
            cart={r[0] for r in db.execute("SELECT id FROM discovery_cart")}
        if pg==1 and not query and not selected:
            selected_ids={r["id"] for r in starters}
            items=starters + [r for r in items if r["id"] not in selected_ids]
        choices="".join(f'<label class=tile><a href="/discover/item/{r["id"]}" aria-label="Preview {escape(r["title"],quote=True)}">{media_previews.tag(r["id"],r["title"])}</a><input type=checkbox name=item value="{r["id"]}" {"checked" if r["id"] in cart else ""}> <strong>{escape(r["title"])}</strong><p>{escape(r["preview"])}</p><small>{escape(r["provider"])} · {escape(r["rights"])}</small></label>' for r in items)
        paging=(f'<a href="{link(page=pg-1)}">Previous page</a>' if pg>1 else "")+(f'<a id=more-titles href="{link(page=pg+1)}">More titles →</a>' if more else "")
        group = next((key for key,label in CATALOG_KINDS.items() if label==kind), "books")
        self.send_page("Discover",f'''<a href="/library/{group}">← Your {"videos" if kind=="Films" else escape(kind.lower())}</a><nav class=pills>{tabs}</nav><form><input type=hidden name=kind value="{kind}"><label>Source <select name=provider>{options}</select></label> <input type=search name=q value="{escape(query)}" placeholder="Search {"videos" if kind=="Films" else kind.lower()}" aria-label="Search catalogue"> <button>Search</button></form>
<nav class=pills aria-label="Suggested searches">{picks}</nav><p role=status>{escape(notice)}</p>
<form method=post action="/discover/save"><input type=hidden name=token value="{self.server.token}"><div class=collection id=discover-results>{choices}</div><div class=cart-bar><output id=cart-count>{len(cart)} selected</output> <button>Download selections</button></div></form><nav class=pills>{paging}</nav>''')

    def content(self, key, raw=False, sequence=None, cover=False):
        with closing(connect(self.server.database)) as db:
            row=db.execute("SELECT * FROM discovery_item WHERE id=? AND filename IS NOT NULL",(key,)).fetchone()
            files=db.execute("SELECT * FROM discovery_file WHERE id=? ORDER BY sequence",(key,)).fetchall()
            episodes=db.execute("SELECT sequence,title FROM series_parts WHERE id=? ORDER BY sequence",(key,)).fetchall()
        if not row:
            self.send_error(404)
            return
        collection_view=bool(episodes and sequence is None and not raw and not cover)
        if sequence is None:
            sequence=files[0]["sequence"] if files else 0
        selected=next((v for v in files if v["sequence"]==sequence),None)
        if (files and not selected) or (not files and sequence!=0):
            self.send_error(404)
            return
        filename = selected["filename"] if selected else row["filename"]
        if Path(filename).name != filename:
            self.send_error(404)
            return
        path=self.server.database.parent / "Content" / filename
        if not path.is_file():
            self.send_error(404)
            return
        if cover:
            if path.suffix.lower() not in {".mp4",".webm",".ogv",".m4v",".mkv",".mov",".avi"}:
                self.send_error(404)
                return
            folder=path.parent/".thumbnails"
            target=folder/(path.name+".jpg")
            tool=Path(__file__).with_name("make-poster")
            updated=max(path.stat().st_mtime_ns,tool.stat().st_mtime_ns if tool.is_file() else 0)
            if not target.is_file() or target.stat().st_mtime_ns < updated:
                if not tool.is_file():
                    self.send_error(404)
                    return
                folder.mkdir(exist_ok=True)
                try:
                    subprocess.run([tool,path,target],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                except (OSError,subprocess.SubprocessError):
                    self.send_error(404)
                    return
            send_asset(self,target)
            return
        if raw:
            send_asset(self,path)
            return
        source="/content-file/"+key+"?part="+str(sequence)
        if key == discovery.ZIP_ID:
            body = '<label>Open a local ZIP <input id="inspect-zip" type="file" accept=".zip,application/zip"></label><p id="zip-summary" role="status"></p><ol id="zip-entries"></ol>'
        elif path.suffix in {".mp4",".m4v",".mov",".mkv",".webm",".ogv",".avi"}:
            body = (f'<video controls playsinline preload="metadata" poster="/content-poster/{key}?part={sequence}" src="{source}"></video>'
                    f'<p><a href="/player/content/{key}?part={sequence}">Play with the in-app VLC player</a></p>')
            if episodes and selected:body=f'<h3>{escape(Path(selected["title"]).stem)}</h3>'+body
            body += self.up_next("/content/"+key)
        elif path.suffix in {".ogg",".oga",".mp3",".aac",".flac",".m4a",".wav"}:
            body=f'<audio controls src="{source}"></audio>'
        elif row["kind"]=="Pictures" and path.suffix in {".jpg",".jpeg",".webp",".png",".gif"}:
            body=f'<img class=personal-picture alt="{escape(row["title"])}" src="{source}">'
        elif row["kind"]=="Games" and path.suffix in {".html",".htm"}:
            body=f'<iframe sandbox="allow-scripts" class="kit-document puzzle-frame" title="Imported game" src="/personal-game/{key}"></iframe>'
        elif path.suffix==".json" and row["kind"]=="Documents" and row["provider"] in ("GLEIF","ProPublica Nonprofit Explorer"):
            body=opencorpo.json_reader(path.read_bytes())
        elif path.suffix==".epub":
            value=parse_qs(urlsplit(self.path).query).get("chapter",["0"])[0]
            body=personal_library.epub_page(path,key,int(value) if re.fullmatch(r"[0-9]{1,6}",value) else 0)
        elif path.suffix==".pdf":
            body=f'<iframe class=kit-document src="{source}" title="Book"></iframe>'
        elif path.suffix==".txt":
            with path.open(encoding="utf-8-sig",errors="replace") as f:
                excerpt = f.read(200000)
                body = f'<pre class=reader data-source="{source}">{escape(excerpt)}</pre>'
                if f.read(1):
                    body += f'<a href="{source}">Read complete book</a>'
        else:
            body=""
        if key.startswith("personal-") or row["kind"] in {"Software","Games"}:
            native=getattr(self.server,"android",False)
            label="Open with another app" if native else "Show file in Finder"
            body += f'<p><a href="/personal-open/{key}">{label}</a></p>'
            if (native and path.suffix==".apk") or (not native and row["preview"]=="Mac application"):
                body += f'<p><a href="/personal-launch/{key}">Launch installed app</a></p>'
        playlist = "".join(f'<a href="/content/{key}?part={f["sequence"]}">{escape(f["title"])}</a>' for n,f in enumerate(files)) if len(files)>1 else ""
        if episodes:
            ready={v["sequence"] for v in files}
            cards=[]
            for index,ep in enumerate(episodes):
                n=ep["sequence"]
                label=escape(Path(ep["title"]).stem)
                if n in ready:
                    poster=f'/content-poster/{key}?part={n}'
                    loading="eager" if index<4 else "lazy"
                    cards.append(f'<li><a class="item" href="/content/{key}?part={n}"><span class="thumb"><img loading="{loading}" src="{poster}" alt=""></span><strong>{label}</strong></a></li>')
                else:
                    cards.append(f'<li class="episode-pending"><strong>{label}</strong><small>Pending download</small></li>')
            cover=f"/content-poster/{quote(key,safe='')}?part={files[0]['sequence'] if files else 0}"
            grid=f'<section aria-label="Episodes" style="--collection-cover:url({cover})"><h3>Episodes · {len(ready)} of {len(episodes)} saved</h3><ol class="episode-grid">{"".join(cards)}</ol></section>'
            playlist=""
            if collection_view:
                body=f'<img class="series-hero" src="/content-poster/{key}?part={sequence}" alt="">{grid}'
            else:
                body=f'<p><a href="/content/{key}">All episodes</a></p>{body}{grid}'
        remove=self.remove_form(key)
        if row["provider"]=="Internet Archive" and row["kind"] in ("Films","Shows"):
            remove+=f'<form method=post action="/discover/add"><input type=hidden name=token value="{self.server.token}"><input type=hidden name=item value="{key}"><button>Check for missing episodes</button></form>'
        save_link="" if collection_view else f'<a href="{source}" download="{escape(row["title"].replace("/", "-")+"".join(path.suffixes))}">Save original file</a>'
        self.send_page(row["title"],f'<nav class=pills>{playlist}</nav><small>{escape(row["rights"])}</small>{save_link}{body}{remove}')

    def remove_form(self,key):
        return (f'<details><summary>Remove download</summary><form method="post" action="/download/remove">'
                f'<input type="hidden" name="token" value="{self.server.token}"><input type="hidden" name="item" value="{escape(key,quote=True)}">'
                '<p>This deletes the local files for this title, including downloaded episodes and partial transfers.</p>'
                '<button>Delete from this device</button></form></details>')

    def installed_games(self):
        kit = self.server.kit
        folder = kit / "04-Entertainment/Games/Browser Puzzles" if kit else None
        return [file[:-5] for file in self.server.puzzles if file.endswith(".html") and folder and
                all((folder / (file[:-5] + ext)).is_file() for ext in (".html", ".js", ".wasm"))]

    @staticmethod
    def game_cards(names):
        return "".join(f'<a class=item href="/library/games?play={name}"><span class=game-cover>'
                       f'<img loading=lazy alt="" src="/puzzle-cover/{name}.png"></span>'
                       f'<strong>{escape(name.title())}</strong></a>' for name in names)

    def games(self, name):
        installed = self.installed_games()
        if name:
            if name not in installed:
                self.send_error(404)
                return
            self.send_page("Games", f'<h3>{escape(name.title())}</h3><nav class=pills><a href="/library/games">All puzzles</a></nav><iframe title="{name.title()} puzzle" class="kit-document puzzle-frame" src="/puzzle-file/{name}.html"></iframe>')
            return
        with closing(connect(self.server.database)) as db:
            imported=db.execute("SELECT id,title,kind FROM discovery_item WHERE kind='Games' AND filename IS NOT NULL ORDER BY title").fetchall()
        cards = self.game_cards(installed)
        personal=self.personal_cards(imported,{"Games"})
        self.send_page("Games", '<a href="/discover?kind=Games">Browse more games →</a>'
                       +self.import_form("games")+
                       (('<h3>Your games</h3>'+category_grid("Your games",personal,"shelf games")) if personal else "") +
                       (('<h3>Portable Puzzle Collection</h3>'+category_grid("Puzzles",cards,"shelf games")) if cards else self.catalogue_samples("games",category_grid)))

    def puzzle_file(self, name):
        if name not in self.server.puzzles or not self.server.kit:
            self.send_error(404)
            return
        path = self.server.kit / "04-Entertainment/Games/Browser Puzzles" / name
        if not path.is_file() or not path.resolve().is_relative_to(self.server.kit):
            self.send_error(404)
            return
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != self.server.puzzles[name]:
            self.send_error(409, "Puzzle version does not match this build")
            return
        if path.suffix==".html":
            body=body.replace(b"</head>",Path(__file__).with_name("puzzle-mobile.html").read_bytes()+b"</head>",1)
        elif path.suffix==".js":
            body=body.replace(b"colours[colour_number] = UTF8ToString(colour_string);",
                              b"colours[colour_number] = boardColour(colour_number,UTF8ToString(colour_string));",1)
        types = {".wasm":"application/wasm", ".js":"application/javascript", ".html":"text/html"}
        self.send_response(200)
        self.send_header("Content-Type", types[path.suffix])
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'wasm-unsafe-eval' 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; frame-ancestors 'self'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def atlas(self, path):
        if path in ("", "index.html","openintel.html"):
            payload = ((intel_screen.ROOT/"map.html") if path=="openintel.html" else Path(__file__).with_name("atlas.html")).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
            return
        roots = [Path(__file__).parent / "vendor/starter-atlas"]
        if self.server.kit:
            roots.insert(0,self.server.kit / "03-Maps/Atlas")
        for root in roots:
            base = root.resolve()
            asset = (base / unquote(path)).resolve()
            allowed = path in {"World.pmtiles", "UK.pmtiles", "Aberdeen.pmtiles"} or (
                asset.is_relative_to(base / "vendor") and asset.suffix in {".js",".css",".pbf",".png",".json"})
            if allowed and asset.is_relative_to(base) and asset.is_file():
                send_asset(self,asset)
                return
        self.send_error(404)

    def do_HEAD(self):
        target = urlsplit(self.path)
        if self.local_request() and target.path.startswith("/content-file/"):
            self.do_GET()
        elif self.local_request() and target.path.startswith("/atlas/"):
            self.atlas(target.path[7:])
        elif self.local_request() and target.path.startswith("/kit-file/"):
            self.kit_file(target.path[len("/kit-file/"):])
        else:
            self.send_error(404)

    def show_sources(self, regions, selected, refresh):
        catalog = self.server.catalog
        boxes = "".join(checkbox("region", key, name, regions)
                        for key, name in catalog["regions"].items())
        groups = {}
        for item in sorted(eligible(catalog, regions), key=lambda source: source["title"].casefold()):
            groups.setdefault(item["kind"], []).append(
                checkbox("source", item["id"], item["title"], selected, item["rights"])
            )
        sources = "".join(f'<details open data-category="{escape(kind)}" class=source-group><summary>{escape(kind)} <small>{len(items)} available</small></summary><div class=grid>{"".join(items)}</div></details>'
                          for kind, items in sorted(groups.items()))
        region_inputs = "".join(f'<input type=hidden name=region value="{escape(region)}">'
                                for region in regions)
        self.send_page("Regional feeds", f"""<a href="/archive">Read saved reports</a>
<form action="/sources" method=get><fieldset class=regions><legend>Regional coverage</legend>
<div class=grid>{boxes}</div></fieldset><button>Show sources</button></form>
<form action="/sync" method=post>
<input type=hidden name=token value="{self.server.token}">{region_inputs}
<fieldset><legend>Choose what to save</legend><input type=search id=catalog-search placeholder="Find a source…" aria-label="Find a source"> <output></output>
{sources or "Choose at least one region."}</fieldset>
{checkbox("refresh", "1", "Refresh selected public data hourly while EchoOffGrid is open",
          {"1"} if refresh else set(), "Books are downloaded on request.")}
<button>Save selection and download</button></form>""")

    def archive(self, query, downloads=False):
        with closing(connect(self.server.database)) as database:
            results = search(database, query) if query else database.execute("""
                SELECT s.id, s.source, s.title, s.rights, '' AS excerpt
                FROM snapshot s
                JOIN (SELECT max(id) AS id FROM snapshot GROUP BY source) latest ON s.id=latest.id
                ORDER BY s.title
            """).fetchall()
            latest = database.execute("""
                SELECT f.source, f.checked_at, f.error, s.title
                FROM fetch f LEFT JOIN snapshot s ON s.id=f.snapshot_id
                JOIN (SELECT max(id) AS id FROM fetch GROUP BY source) last ON last.id=f.id
                ORDER BY f.checked_at DESC
            """).fetchall()
            completed = database.execute("""SELECT i.id,i.title,i.kind FROM discovery_item i JOIN chosen_download c ON c.source='discover-'||i.id
                WHERE i.filename IS NOT NULL AND NOT EXISTS(SELECT 1 FROM content_download q WHERE q.source=c.source) ORDER BY i.title""").fetchall() if downloads else []
            saved_feeds=database.execute("SELECT title,snapshot_id FROM chosen_download WHERE snapshot_id IS NOT NULL ORDER BY title").fetchall() if downloads else []
            progress = self.server.downloads.progress(database)
        kinds = {item["id"]: item["kind"] for item in self.server.catalog["sources"]}
        groups = {}
        for row in results:
            kind = kinds.get(row["source"], "Other saved sources")
            groups.setdefault(kind, []).append(
                f'<article><strong>{escape(row["title"])}</strong><p>{escape(row["excerpt"] or "")}</p>'
                f'<small>{escape(row["rights"])}</small><div class=card-actions>'
                f'<a href="/read/{row["id"]}">Read saved copy</a>'
                f'<a href="/snapshot/{row["id"]}">Download original</a></div></article>')
        sections = []
        jumps = []
        for kind, cards in sorted(groups.items()):
            anchor = "category-" + kind.lower().replace(" ", "-")
            jumps.append(f'<a href="#{escape(anchor)}">{escape(kind)} ({len(cards)})</a>')
            sections.append(f'<section id="{escape(anchor)}" class=saved-category><h3>{escape(kind)} <small>{len(cards)}</small></h3>'
                            f'<div class=collection>{"".join(cards)}</div></section>')
        snippets = ('<nav class=pills aria-label="Saved categories">' + "".join(jumps) + '</nav>' + "".join(sections)) if groups else ""
        progress=[row for row in progress if bool(row["chosen"])==downloads]
        current = [r for r in progress if r["state"] in ("Queued", "Downloading")]
        failed = [r for r in progress if r not in current]
        def lane(title, items, empty):
            contents = ""
            for row in items:
                meter = ""
                if row["state"]=="Downloading" and row["received"] is not None:
                    total = row["total"]
                    received = row["received"]
                    bar = f'<progress value="{received}" max="{total}"></progress>' if total else '<progress></progress>'
                    meter = f'{bar} <small>{received/1048576:.1f} MiB received</small>'
                if row["retry_due"] and row["retry_due"]>datetime.now().timestamp():
                    meter="<small>Publisher requested a pause. Retrying at "+datetime.fromtimestamp(row["retry_due"]).strftime("%H:%M:%S")+".</small>"
                retry = ""
                if row in failed:
                    retry = f'<form method=post action="/retry"><input type=hidden name=return_to value="{"downloads" if downloads else "archive"}"><input type=hidden name=token value="{self.server.token}"><input type=hidden name=source value="{escape(row["source"])}"><button>{"Retry download" if downloads else "Retry refresh"}</button></form>'
                if row["state"]=="Queued" or row["source"].startswith("discover-"):
                    retry+=f'<form method=post action="/download/cancel"><input type=hidden name=token value="{self.server.token}"><input type=hidden name=source value="{escape(row["source"],quote=True)}"><button>Cancel transfer</button></form>'
                if row["source"].startswith("discover-"): retry+=self.remove_form(row["source"][9:])
                contents += f'<div class=job><strong>{escape(row["title"])}</strong><small>{escape(row["state"])}</small>{meter}{retry}</div>'
            return f'<section><h3>{title} <b>{len(items)}</b></h3>{contents or f"<p>{empty}</p>"}</section>'
        if downloads:
            library_links = "".join(f'<a class=tile href="/content/{r["id"]}"><strong>{escape(r["title"])}</strong><small>{escape(r["kind"])}</small></a>' for r in completed)
            library_links+="".join(f'<a class=tile href="/read/{r["snapshot_id"]}"><strong>{escape(r["title"])}</strong></a>' for r in saved_feeds)
            saved_downloads = '<h3>Saved to your library</h3><div class=collection>'+library_links+'</div>' if library_links else ""
            self.send_page("Downloads", f'''<nav class=pills><a href="/sources">Choose downloads</a><a href="/archive">Open saved sources</a></nav>
<small id="connection-status" role=status></small><section id=archive-live><div class=lanes>
{lane("Transfer queue", current, "No active transfers.")}{lane("Needs attention", failed, "No interrupted transfers.")}</div>
{saved_downloads}</section>''')
            return
        history = "".join(f'<tr><th>{escape(row["title"] or row["source"])}</th><td>{escape(row["error"] or "Saved")}</td><td>{escape(row["checked_at"])}</td></tr>' for row in latest)
        backup = ('<a href="/archive/backup">Download archive backup</a>' if getattr(self.server,"android",False)
                  else f'<form method=post action="/archive/backup"><input type=hidden name=token value="{self.server.token}"><button>Download archive backup</button></form>')
        self.send_page("Saved sources", f"""
<form><input type=search name=q value="{escape(query)}" placeholder="Search saved sources"
aria-label="Search saved sources"> <button>Search</button></form>
<nav class=pills><a href="/library">Browse library</a><a href="/sources">Add sources</a><a href="/downloads">Download activity</a></nav>
<section id="archive-live">{snippets or ("<p>No matching sources.</p>" if query else "<p>Your saved sources will appear here.</p>")}
<section id="activity"><h3>Source refresh activity</h3><div class=lanes>
{lane("Refresh queue",current,"No refreshes pending.")}{lane("Refresh errors",failed,"No refresh errors.")}</div><h3>Latest check by source</h3><div class=scroll-table><table><thead><tr><th>Source</th><th>Result</th><th>Checked at</th></tr></thead><tbody>{history}</tbody></table></div></section></section>
<small id="connection-status" role=status></small>
{backup}
<small>Includes saved sources, download history and imported evidence.</small>""")

    def evidence(self, params, notice="", *, export=False):
        checks = params.get("checks") == ["1"]
        source = params.get("source", [""])[0]
        start = params.get("start", [""])[0]
        end = params.get("end", [""])[0]
        try:
            if source not in {"", "HackRF", "ScotMesh"}:
                raise ValueError("Unknown evidence source")
            start_utc = normalized_time(start + "+00:00") if start and len(start) <= 19 else ""
            end_utc = normalized_time(end + "+00:00") if end and len(end) <= 19 else ""
            if (start and not start_utc) or (end and not end_utc):
                raise ValueError("Invalid UTC date and time")
            if start_utc and end_utc and start_utc >= end_utc:
                raise ValueError("The end must be later than the start")
        except ValueError as error:
            self.send_page("Evidence timeline", f'<p>{escape(str(error))}</p><a href="/evidence">Reset filters</a>', 400)
            return
        with closing(connect(self.server.database)) as database:
            self.server.kit_logs.refresh(database)
            rows = timeline(database, include_checks=checks, source=source, start=start_utc, end=end_utc)
        if export:
            self.export_evidence(rows)
            return
        export_query = urlencode({"source": source, "start": start, "end": end, "checks": int(checks)})
        events = []
        for row in rows:
            raw = json.loads(row["record"])
            detail = " · ".join(str(raw[key]) for key in
                                ("detail", "listening", "length", "bytes", "crc_status", "snr_db")
                                if key in raw and raw[key] not in ("", None))
            events.append(
                f'<article class=event><strong>{escape(row["source"])} · '
                f'{escape(row["category"].replace("_", " "))}</strong>'
                f'<p>{escape(row["event_at"])}'
                f'{" · " + escape(detail) if detail else ""}</p>'
                f'<small>Observed {escape(row["observed_at"])} · {escape(row["filename"])}</small>'
                f'<details><summary>Original record</summary><pre style="white-space:pre-wrap">'
                f'{escape(row["record"])}</pre></details></article>'
            )
        packets = [r for r in rows if r["category"] == "local_decode"]
        reports = [r for r in rows if r["category"] == "public_packet_feed"]
        def stat(label, items):
            latest = escape(items[0]["event_at"]) if items else "None in this view"
            return f'<section><h3>{label}</h3><b>{len(items)}</b><small>{latest}</small></section>'
        highlights = '<div class=lanes>' + (stat("Local decodes", packets) if source != "ScotMesh" else "") + (stat("Public packet reports", reports) if source != "HackRF" else "") + '</div>'
        comparison = ""
        if not source and reports:
            comparisons = []
            for report in reports[:12]:
                when = datetime.fromisoformat(report["event_at"])
                nearest = min(packets, key=lambda r: abs(datetime.fromisoformat(r["event_at"]) - when), default=None)
                if nearest:
                    offset = (datetime.fromisoformat(nearest["event_at"]) - when).total_seconds()
                    result = f'{escape(nearest["event_at"])} ({offset:+.0f} s)'
                else:
                    result = "No local decode in view"
                comparisons.append(f'<tr><th>{escape(report["event_at"])}</th><td>{result}</td></tr>')
            comparison = '<h3>Nearest local decode per public report</h3><div class=scroll-table><table><tr><th>Reported (UTC)</th><th>Local time and difference</th></tr>' + "".join(comparisons) + '</table></div>'
        options = "".join(
            f'<option value="{value}"{" selected" if value == source else ""}>{label}</option>'
            for value, label in (("", "Both sources"), ("HackRF", "HackRF"), ("ScotMesh", "ScotMesh"))
        )
        import_log = f"""<form method=post action="/evidence/import" enctype="multipart/form-data">
<input type=hidden name=token value="{self.server.token}">
<label>Import reception log <input type=file name=log accept=".csv,.jsonl" required></label>
<button>Import log</button></form>
"""
        import_node = f"""<details><summary>Import a saved ScotMesh node</summary>
<p>Download the ScotMesh public network snapshot from Regional feeds, then enter the full node name.</p>
<form method=post action="/evidence/scotmesh">
<input type=hidden name=token value="{self.server.token}">
<label>Node name <input name=node maxlength=120 required placeholder="Aberdeenshire_Obsever"></label>
<button>Import node timestamps</button></form></details>
"""
        capture = f"""<details><summary>Optional radio</summary>
<p>Save the current SDRangel decoder report from localhost port 18891.</p>
<form method=post action="/evidence/capture">
<input type=hidden name=token value="{self.server.token}">
<button>Capture receiver status</button></form></details>
"""
        self.send_page({"HackRF": "Receiver log", "ScotMesh": "ScotMesh reports"}.get(source, "Compare packets"), f"""
<small>Summary of the {len(rows)} displayed records</small>{highlights}{comparison}
<p>Public packet-feed timestamps indicate observer activity. Compare them
with local decodes by UTC time. Timing alone cannot identify the sender.</p>
{import_log + capture if source == "HackRF" else import_node if source == "ScotMesh" else '<p><a href="/evidence?source=HackRF">Manage receiver log</a> · <a href="/evidence?source=ScotMesh">Manage ScotMesh reports</a></p>'}
{f'<p role=status>{escape(notice)}</p>' if notice else ""}
<form method=get action="/evidence">
<details class=filter-panel><summary>Filter by source and time</summary><fieldset><legend>UTC interval</legend>
<div class=grid>
<label>Source <select name=source>{options}</select></label>
<label>From (UTC) <input type=datetime-local step=1 name=start value="{escape(start)}"></label>
<label>Before (UTC) <input type=datetime-local step=1 name=end value="{escape(end)}"></label>
{checkbox("checks", "1", "Show routine feed checks", {"1"} if checks else set())}
</div></fieldset>
<button>Apply filters</button> <a href="/evidence?source={source}">Reset</a></details></form>
<small>Showing {len(rows)} events, up to 250 newest matches.</small>
<a href="/evidence.csv?{escape(export_query)}" {"" if getattr(self.server,"android",False) else "download"}>Export matching events as CSV</a>
{"".join(events) or "<p>No packets or observations match these filters.</p>"}""")

    def export_evidence(self, rows):
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(("event_at_utc", "observed_at_utc", "source", "category", "filename", "original_record"))
        for row in rows:
            filename = row["filename"]
            if filename.lstrip().startswith(("=", "+", "-", "@")) or filename.startswith(("\t", "\r", "\n")):
                filename = "'" + filename
            writer.writerow((row["event_at"], row["observed_at"], row["source"], row["category"],
                             filename, row["record"]))
        payload = output.getvalue().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="EchoOffGrid-evidence.csv"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def read_snapshot(self, snapshot_id, requested_page):
        with closing(connect(self.server.database)) as database:
            row = database.execute("""
                SELECT s.*, min(f.checked_at) AS saved_at
                FROM snapshot s JOIN fetch f ON f.snapshot_id=s.id
                WHERE s.id=? GROUP BY s.id
            """, (snapshot_id,)).fetchone()
        if row is None:
            self.send_error(404)
            return
        file_type = binary_format(row["body"])
        if file_type:
            self.send_page(row["title"], f"""
<p>Saved {escape(row["saved_at"])} · {escape(row["rights"])}</p>
<small>{escape(row["url"])}</small>
<p><a href="/snapshot/{snapshot_id}">Download saved {file_type.upper()} file</a></p>""")
            return
        content = row["body"].decode("utf-8-sig")
        try:
            if content.lstrip().startswith(("{", "[")):
                data=json.loads(content)
                if row["source"]=="worldbank-population" and isinstance(data,list) and len(data)>1:
                    report=spotlight.population(data[1],snapshot_id)
                    if report:self.send_page("World population",report);return
                lines=list(discovery.record_lines(row["source"],data))
                if lines:
                    start=(requested_page-1)*24
                    entries="".join(f'<li>{escape(line)}</li>' for line in lines[start:start+24])
                    paging=" ".join(f'<a href="/read/{snapshot_id}?page={n}">{label}</a>' for n,label in [(requested_page-1,"Previous"),(requested_page+1,"Next")] if 0<n<=(len(lines)+23)//24)
                    self.send_page(row["title"],f'<small>Saved {escape(row["saved_at"])}</small><ul class="report-entries">{entries}</ul><nav>{paging}</nav><p><a href="/snapshot/{snapshot_id}">Download source data</a></p>')
                    return
                content="No readable entries in this saved feed."
            elif content.lstrip().startswith(("<?xml", "<feed", "<rss")):
                content = feed_text(content)
        except ValueError:
            pass
        size = 16000
        total = max(1, (len(content) + size - 1) // size)
        current = min(requested_page, total)
        offset = (current - 1) * size
        links = []
        if current > 1:
            links.append(f'<a href="/read/{snapshot_id}?page={current-1}">Previous</a>')
        if current < total:
            links.append(f'<a href="/read/{snapshot_id}?page={current+1}">Next</a>')
        controls = f'<nav aria-label="Reading pages">Page {current} of {total} {" ".join(links)}</nav>'
        self.send_page(row["title"], f"""
<p>Saved {escape(row["saved_at"])} · {escape(row["rights"])}</p>
<small>{escape(row["url"])}</small>
<a href="/snapshot/{snapshot_id}">Download original</a>
{controls}
<pre class=reader>{escape(content[offset:offset+size])}</pre>
{controls}""")

    def echolite(self, notice="", question="", answer=""):
        available = self.server.echolite is not None
        self.send_page("EchoLite", f"""
{f'<p role=status>{escape(notice)}</p>' if notice else ""}
{f'<article><strong>You</strong><p class=reader>{escape(question)}</p></article>' if question else ""}
{f'<article><strong>EchoLite</strong><p class=reader>{escape(answer)}</p></article>' if answer else ""}
<form id="echolite-chat" method=post action="/echolite">
<input type=hidden name=token value="{self.server.token}">
<label for=prompt>Message</label>
<textarea id=prompt name=prompt rows=4 required {'disabled' if not available else ''}></textarea>
<button {'disabled' if not available else ''}>Send</button><span role=status></span></form>
{'' if available else '<p>Open EchoLite → Set up EchoLite to connect an installation or install the local companion.</p>'}
""")

    def ask_echolite(self, prompt):
        if not prompt:
            self.echolite("Enter a message.")
            return
        executable = self.server.echolite
        if executable is None:
            self.echolite("EchoLite setup is required.")
            return
        if not self.server.chat_lock.acquire(blocking=False):
            self.echolite("EchoLite is still responding to the previous message.")
            return
        try:
            finished = subprocess.run(
                [str(executable), "chat", "echooffgrid", prompt],
                cwd=executable.parent, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, errors="replace", check=False,
            )
            answer = finished.stdout.strip() or finished.stderr.strip()
            self.echolite("EchoLite reported an error." if finished.returncode else "",
                          prompt, answer)
        except OSError as error:
            self.echolite(f"Could not start EchoLite: {error}", prompt)
        finally:
            self.server.chat_lock.release()

    def download(self, snapshot_id):
        with closing(connect(self.server.database)) as database:
            row = database.execute("SELECT body FROM snapshot WHERE id=?", (snapshot_id,)).fetchone()
        if row is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        extension = binary_format(row["body"]) or "bin"
        self.send_header("Content-Disposition", f'attachment; filename="snapshot-{snapshot_id}.{extension}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(row["body"])))
        self.end_headers()
        self.wfile.write(row["body"])

    def backup_archive(self):
        with TemporaryDirectory(prefix="echooffgrid-backup-") as folder:
            backup = Path(folder) / "EchoOffGrid.sqlite3"
            try:
                with closing(connect(self.server.database)) as original, closing(sqlite3.connect(backup)) as copy:
                    original.backup(copy, pages=256)
                    with copy:
                        copy.execute("DELETE FROM pending_download")
                        copy.execute("UPDATE refresh_preference SET enabled=0")
                    copy.execute("PRAGMA journal_mode=DELETE")
            except (OSError, sqlite3.Error) as error:
                self.send_page("Archive backup", f"<p>{escape(str(error))}</p>", 500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="EchoOffGrid.sqlite3"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(backup.stat().st_size))
            self.end_headers()
            with backup.open("rb") as stream:
                copyfileobj(stream, self.wfile)

    def do_GET(self):
        if not self.local_request():
            self.send_error(403)
            return
        target = urlsplit(self.path)
        params = parse_qs(target.query)
        if re.fullmatch(r"/publisher-art/(?:[0-9a-f]{64}|story-[0-9]+)",target.path):
            try:data=media_previews.resolve(self.server.database,target.path.rsplit("/",1)[1])
            except Exception:
                self.send_error(404,"Publisher artwork unavailable");return
            self.send_response(200);self.send_header("Content-Type",media_previews.mime(data))
            self.send_header("Cache-Control","private, max-age=86400");self.send_header("Content-Length",str(len(data)));self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
            return
        if re.fullmatch(r"/publisher-video/[0-9a-f]{64}",target.path):
            media_previews.film_preview(self,target.path.rsplit("/",1)[1]);return
        if target.path == "/private-browser":
            try:
                destination = private_browser.link_address(params["to"][0]) if "to" in params else ""
            except (ValueError, UnicodeError):
                self.send_page("Private Browser","<p>This link requires a public HTTPS address.</p>",400)
                return
            self.send_page("Private Browser",private_browser.screen(self.server.private_browser,self.server.token,destination))
            return
        if re.fullmatch(r"/private-image/[a-f0-9]{32}",target.path):
            try:
                mime,data=self.server.private_browser.image(target.path.rsplit("/",1)[1])
            except (OSError,ValueError,http.client.HTTPException):
                self.send_error(404);return
            self.send_response(200);self.send_header("Content-Type",mime);self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff");self.send_header("Content-Length",str(len(data)))
            self.end_headers();self.wfile.write(data);return
        if target.path == "/private-status":
            if params.get("phone")==["1"] and hasattr(self.server,"phone_proxy"):
                data=json.dumps({"port":self.server.phone_proxy.server_port}).encode()
                self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store")
                self.end_headers();self.wfile.write(data);return
            status,ready=self.server.private_browser.status()
            session=self.server.private_browser
            proxy=session.proxy
            process=session.process
            data=json.dumps({"status":status,"ready":ready,"country":session.location,
                             "enabled":process is not None and process.poll() is None,
                             "port":proxy.server_port if ready and proxy else 0}).encode()
            self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
            return
        if target.path == "/openintel" or target.path.startswith("/openintel/"):
            intel_screen.read(self,target.path,params)
            return
        if target.path == "/dashboard.js":
            payload = LIVE_UPDATES.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if target.path == "/integrations/jszip.js":
            asset = self.server.database.parent / "Content" / (discovery.ZIP_ID + ".js")
            if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != discovery.ZIP_DIGEST:
                self.send_error(404)
                return
            send_asset(self,asset)
            return
        if target.path.startswith(("/personal-game/","/personal-cover/","/personal-open/")):
            key=target.path.split("/")[-1]
            if not re.fullmatch(r"(?:personal-)?[0-9a-f]{64}",key):
                self.send_error(404);return
            root=self.server.database.parent/"Content"
            with closing(connect(self.server.database)) as db:
                row=db.execute("SELECT kind,filename FROM discovery_item WHERE id=?",(key,)).fetchone()
            if not row or Path(row["filename"]).name!=row["filename"]:
                self.send_error(404);return
            file=root/row["filename"]
            if target.path.startswith("/personal-open/"):
                self.send_page("Open file",f'<a download href="/content-file/{key}">Save a copy to open in another app</a>');return
            if target.path.startswith("/personal-cover/"):
                file=root/(key+".cover")
                if not file.is_file():self.send_error(404);return
                with file.open("rb") as f: ext=personal_library.image_format(f.read(16))
                if not ext:self.send_error(415);return
                mime="image/"+("jpeg" if ext==".jpg" else ext[1:])
                policy="default-src 'none'"
            elif row["kind"]=="Games" and file.suffix in {".html",".htm"}:
                mime="text/html";policy="sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; form-action 'none'; frame-ancestors 'self'"
            else:
                self.send_error(404);return
            with file.open("rb") as stream:
                self.send_response(200);self.send_header("Content-Type",mime);self.send_header("Content-Security-Policy",policy)
                self.send_header("Content-Length",str(file.stat().st_size));self.end_headers();copyfileobj(stream,self.wfile)
            return
        if target.path in ("/opengov/portal","/opencorpo/portal"):
            corpo=target.path.startswith("/opencorpo")
            try:
                with closing(connect(self.server.database)) as db:
                    body=opengov.govports.browse(db,params.get("country",[""])[0],params.get("url",[""])[0],self.server.token,directory=opencorpo.PORTALS if corpo else None,base="/opencorpo" if corpo else "/opengov")
                self.send_page("OpenCorpo" if corpo else "OpenGov",body)
            except ValueError as error:self.send_error(400,str(error))
        elif target.path in ("/opengov","/opencorpo"):
            corpo=target.path=="/opencorpo"
            with closing(connect(self.server.database)) as db:
                self.send_page("OpenCorpo" if corpo else "OpenGov",opengov.screen(db,params,self.server.token,opencorpo if corpo else None))
        elif target.path == "/news":
            self.send_page("News", self.server.news.render(self.server.token))
        elif target.path.startswith("/news/field-notes/"):
            article = self.server.news.field_notes(target.path.split("/")[-1])
            if article:self.send_page("Field notes",article)
            else:self.send_error(404)
        elif target.path.startswith("/news/"):
            key = target.path[6:]
            story = self.server.news.story(int(key)) if re.fullmatch(r"[0-9]{1,18}",key) else None
            if story is None:
                self.send_error(404)
            else:
                self.send_page("News",story)
        elif target.path.startswith("/discover/item/"):
            with closing(connect(self.server.database)) as db:
                row=db.execute("SELECT * FROM discovery_item WHERE id=?",(target.path.rsplit("/",1)[-1],)).fetchone()
            if row:self.send_page("Discover",spotlight.item_page(row,self.server.token))
            else:self.send_error(404)
        elif target.path == "/discover":
            self.discover(params)
        elif target.path.startswith(("/content/","/content-file/","/content-poster/")):
            part=params.get("part",["0"])[0]
            if not part.isascii() or not part.isdigit() or len(part)>6:
                self.send_error(400)
                return
            self.content(target.path.rsplit("/",1)[1],target.path.startswith("/content-file/"),int(part) if "part" in params else None,target.path.startswith("/content-poster/"))
        elif target.path in ("/games","/library/games"):
            self.games(params.get("play", [""])[0])
        elif target.path.startswith("/puzzle-cover/"):
            name = target.path[len("/puzzle-cover/"):]
            cover = Path(__file__).parent / "vendor/puzzle-covers" / name
            if not re.fullmatch(r"[a-z0-9]+\.png", name) or not cover.is_file():
                self.send_error(404)
            else:
                send_asset(self, cover)
        elif target.path.startswith("/puzzle-file/"):
            self.puzzle_file(target.path[13:])
        elif target.path == "/dictionary":
            self.send_page("Dictionary", dictionary(self.server.echolite, params.get("q", [""])[0][:160], parse_qs(target.query, keep_blank_values=True).get("prefix", [None])[0], params.get("page", ["1"])[0],params.get("phrases",["0"])[0]=="1", path=getattr(self.server,"dictionary_path",None)))
        elif target.path == "/history":
            self.send_page("History",history_view.article(self.server.wiki,params["read"][0]) if "read" in params else history_view.page(params))
        elif target.path == "/wiki-progress":
            data = json.dumps({"active": bool(self.server.editions.active), "status": self.server.editions.progress()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif target.path == "/wikipedia":
            self.server.wiki.refresh()
            self.send_page("Wikipedia", self.server.editions.panel(self.server.token) + self.server.wiki.page(params.get("book", [""])[0], params.get("q", [""])[0][:300]))
        elif target.path.startswith("/zim/"):
            try:
                self.server.wiki.serve(self)
            except (BrokenPipeError, ConnectionResetError):
                return
            except OSError:
                self.send_error(503, "Offline reader unavailable")
        elif target.path == "/maps":
            self.send_page("Maps", '<iframe class=kit-document title="Interactive offline atlas" src="/atlas/"></iframe><a href="/library/maps">Printable maps</a>')
        elif target.path.startswith("/atlas/"):
            self.atlas(target.path[7:])
        elif target.path == "/home-status":
            self.home(True)
        elif target.path == "/" and "region" not in params:
            self.home()
        elif target.path in {"/", "/sources"}:
            with closing(connect(self.server.database)) as database:
                row = database.execute("""
                    SELECT selection.regions, selection.sources, refresh_preference.enabled
                    FROM selection LEFT JOIN refresh_preference USING (id)
                    WHERE selection.id=1
                """).fetchone()
            regions = params.get("region", json.loads(row["regions"]) if row else ["WORLD"])
            regions = [region for region in dict.fromkeys(regions) if region in self.server.catalog["regions"]]
            self.show_sources(regions, json.loads(row["sources"]) if row else [], bool(row and row["enabled"]))
        elif target.path == "/library" or target.path.startswith("/library/"):
            self.library(target.path[len("/library"):].lstrip("/"))
        elif target.path == "/devices":
            links = [("/evidence?source=HackRF","Receiver log","Local decodes and receiver status"),
                     ("/evidence?source=ScotMesh","ScotMesh reports","Public mesh observations"),
                     ("/evidence","Compare packets","Compare public reports with local reception")]
            companion = ""
            status_path = getattr(self.server,"companion_status",None)
            if status_path and status_path.is_file():
                try:
                    status=json.loads(status_path.read_text())
                    checked=datetime.fromtimestamp(status["checked"],timezone.utc).strftime("%d %b · %H:%M UTC")
                    companion=f'<article><h3>Paired device sync</h3><strong>{escape(status["state"])}</strong><small>{checked}</small></article>'
                except (OSError,KeyError,ValueError,TypeError):
                    pass
            self.send_page("Devices", storage_policy.storage_page(self.server.database.parent, self.server.token) + companion + '<h3>HackRF &amp; mesh</h3><div class=feature-grid>' + "".join(f'<a class=tile href="{url}"><strong>{title}</strong><small>{detail}</small></a>' for url,title,detail in links) + '</div>')
        elif target.path.startswith("/preview/"):
            kind, _, relative = target.path[len("/preview/"):].partition("/")
            asset = resolve_asset(self.server.kit,kind,relative)
            clip = asset.parent / ".thumbnails" / (asset.name + ".preview.mp4") if asset and kind in {"watch","shows"} else None
            if clip and clip.is_file() and not clip.is_symlink() and not clip.parent.is_symlink():
                send_asset(self,clip)
            else:
                self.send_error(404)
        elif target.path.startswith("/poster/"):
            kind, _, relative = target.path[len("/poster/"):].partition("/")
            asset = resolve_asset(self.server.kit, kind, relative)
            thumb = poster(asset) if asset and kind in ("watch", "shows") else None
            if thumb:
                send_asset(self, thumb)
            else:
                self.send_error(404)
        elif target.path.startswith("/kit-file/"):
            self.kit_file(target.path[len("/kit-file/"):])
        elif target.path == "/echolite":
            self.echolite()
        elif target.path in {"/archive", "/downloads"}:
            self.archive(params.get("q", [""])[0][:300], target.path == "/downloads")
        elif target.path in {"/evidence", "/evidence.csv"}:
            self.evidence(params, export=target.path.endswith(".csv"))
        elif target.path.startswith(("/snapshot/", "/read/")):
            route, _, suffix = target.path[1:].partition("/")
            if not suffix.isascii() or not suffix.isdigit() or len(suffix) > 18:
                self.send_error(404)
                return
            snapshot_id = int(suffix)
            if route == "snapshot":
                self.download(snapshot_id)
            else:
                number = params.get("page", ["1"])[0]
                if not number.isascii() or not number.isdigit() or len(number) > 8 or int(number) < 1:
                    self.send_error(400)
                    return
                self.read_snapshot(snapshot_id, int(number))
        else:
            self.send_error(404)

    def import_evidence(self):
        length = self.headers.get("Content-Length", "")
        maximum = MAX_LOG_BYTES + 16384
        if not length.isascii() or not length.isdigit() or len(length) > len(str(maximum)) or int(length) > maximum:
            self.send_error(413)
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data;") or "\r" in content_type or "\n" in content_type:
            self.send_error(400)
            return
        envelope = f"Content-Type: {content_type}\r\n\r\n".encode()
        message = BytesParser(policy=policy.default).parsebytes(envelope + self.rfile.read(int(length)))
        fields = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name in fields or name not in {"token", "log"} or part.is_multipart():
                self.send_error(400)
                return
            fields[name] = part
        if fields.keys() != {"token", "log"}:
            self.send_error(400)
            return
        token = fields["token"].get_payload(decode=True) or b""
        if not hmac.compare_digest(token, self.server.token.encode()):
            self.send_error(403)
            return
        filename = Path(fields["log"].get_filename() or "").name
        payload = fields["log"].get_payload(decode=True) or b""
        if len(payload) > MAX_LOG_BYTES:
            self.send_error(413)
            return
        try:
            with closing(connect(self.server.database)) as database:
                added, skipped = import_records(
                    database, filename, StringIO(payload.decode("utf-8-sig"), newline="")
                )
        except (ValueError, csv.Error) as error:
            self.send_page("Evidence import", f"<p>{escape(str(error))}</p><a href='/evidence'>Back to evidence</a>", 400)
            return
        self.evidence({}, f"Imported {added} new records. Skipped {skipped} unreadable or unsupported rows.")

    def do_POST(self):
        if self.path == "/openintel/capture":
            if not self.local_request() or not hmac.compare_digest(self.headers.get("X-Library-Token",""),self.server.token):
                self.send_error(403);return
            size=self.headers.get("Content-Length","")
            if not size.isascii() or not size.isdigit() or len(size)>8 or not 0<int(size)<=16*1024*1024:
                intel_screen.respond(self,{"error":"Capture exceeds the 16 MiB limit."},413);return
            try:
                data=json.loads(self.rfile.read(int(size)))
                saved=intel_screen.cases.capture_page(self.server.intel,int(data["owner"]),data["page"])
            except (KeyError,TypeError,ValueError,OverflowError) as err:
                intel_screen.respond(self,{"error":str(err)[:200]},400);return
            intel_screen.respond(self,saved,201);return
        destination=re.fullmatch(r"/library/([a-z]+)/import",self.path)
        if destination and destination[1] in personal_library.SHELVES:
            kind=personal_library.SHELVES[destination[1]]
            headers=self.headers
            if not self.local_request() or not hmac.compare_digest(headers.get("X-Library-Token",""), self.server.token):
                self.send_error(403);return
            try:
                key=personal_library.save(self,kind,headers.get("X-Filename",""))
            except (ValueError,OSError) as error:
                self.send_error(400,str(error));return
            result=key.encode()
            self.send_response(201);self.send_header("Content-Length",str(len(result)));self.end_headers();self.wfile.write(result)
            return
        if self.local_request() and self.path == "/evidence/import":
            self.import_evidence()
            return
        if not self.local_request() or self.path not in {"/openintel/action", "/download/remove", "/download/cancel", "/storage", "/wiki-edition", "/private-browser", "/news/location", "/narrate", "/retry", "/discover/pick", "/discover/save", "/discover/add", "/sync", "/evidence/capture", "/evidence/scotmesh", "/archive/backup", "/echolite"}:
            self.send_error(403)
            return
        length = self.headers.get("Content-Length", "")
        if not length.isascii() or not length.isdigit() or len(length) > 5 or int(length) > 16384:
            self.send_error(400)
            return
        try:
            fields = parse_qs(self.rfile.read(int(length)).decode(), max_num_fields=300)
        except ValueError:
            self.send_error(400)
            return
        token = fields.get("token", [""])[0].encode()
        if not hmac.compare_digest(token, self.server.token.encode()):
            self.send_error(403)
            return
        if self.path == "/download/cancel":
            source=fields.get("source",[""])[0]
            table="content_download" if source.startswith("discover-") else "pending_download"
            with closing(connect(self.server.database)) as db,db:
                # The worker owns active files. Remove waiting jobs immediately.
                db.execute(f"INSERT OR IGNORE INTO cancelled_transfer SELECT source FROM {table} WHERE source=? AND state='Downloading'",(source,))
                db.execute(f"DELETE FROM {table} WHERE source=? AND state!='Downloading'",(source,))
                db.execute("DELETE FROM download_backoff WHERE source=?",(source,))
            self.server.downloads.wakeup.set()
            self.send_response(303);self.send_header("Location","/downloads");self.end_headers();return
        if self.path == "/download/remove":
            key=fields.get("item",[""])[0]
            if not re.fullmatch(r"(?:personal-)?[0-9a-f]{64}",key):
                self.send_error(400);return
            with closing(connect(self.server.database)) as db,db:
                db.execute("BEGIN IMMEDIATE")
                job=db.execute("SELECT state FROM content_download WHERE source=?",("discover-"+key,)).fetchone()
                if job and job[0]=="Downloading":
                    db.execute("INSERT OR IGNORE INTO remove_download VALUES(?)",(key,))
                else:
                    self.server.downloads.remove_local(db,self.server.database.parent/"Content",key)
            self.server.downloads.wakeup.set()
            self.send_response(303);self.send_header("Location","/downloads");self.end_headers();return
        if self.path == "/openintel/action":
            intel_screen.write(self,fields);return
        if self.path == "/storage":
            root = self.server.database.parent
            action = fields.get("action", [""])[0]
            if action == "allow":
                (root/storage_policy.ALLOWANCE).write_text(str(datetime.now(timezone.utc).timestamp()+600))
            elif action == "protect":
                (root/storage_policy.ALLOWANCE).unlink(missing_ok=True)
            elif action == "clean":
                storage_policy.clean(root, clear=True)
            else:
                self.send_error(400); return
            self.send_response(303)
            self.send_header("Location", "/devices")
            self.end_headers()
            return
        if self.path == "/wiki-edition":
            try:
                self.server.editions.select(fields.get("edition", [""])[0])
            except ValueError as error:
                self.send_error(400, str(error)); return
            self.send_response(303)
            self.send_header("Location", "/wikipedia")
            self.end_headers()
            return
        if self.path == "/private-browser":
            session=self.server.private_browser
            action=fields.get("action",["browse"])[0]
            url,article,message="","",""
            try:
                if action=="ensure":
                    session.start(fields.get("country",[session.location])[0])
                    self.send_response(204);self.end_headers();return
                if action in ("connect","disconnect","region"):
                    process=session.process
                    enabled=action=="connect" or (action=="region" and process is not None and process.poll() is None)
                    session.configure(enabled,fields.get("country",[session.location])[0])
                    if self.headers.get("X-Echo-Control")=="switch":
                        self.send_response(204);self.end_headers();return
                else:url,article=session.navigate(action,fields.get("url",[""])[0])
            except (OSError,ValueError,UnicodeError,http.client.HTTPException) as error:
                message=str(error) if isinstance(error,ValueError) else "Could not reach the website over Tor. Check the connection and try again."
            self.send_page("Private Browser",private_browser.screen(session,self.server.token,url,article,message))
            return
        if self.path == "/news/location":
            try:
                self.server.news.choose(fields.get("place",[""])[0])
            except ValueError:
                self.send_error(400)
                return
            self.send_response(303)
            self.send_header("Location","/news")
            self.end_headers()
            return
        if self.path == "/retry":
            source = fields.get("source", [""])[0]
            table = "content_download" if source.startswith("discover-") else "pending_download"
            with closing(connect(self.server.database)) as db, db:
                db.execute(f"UPDATE {table} SET state='Queued' WHERE source=? AND state LIKE 'Interrupted:%'", (source,))
            self.server.downloads.wakeup.set()
            self.send_response(303)
            self.send_header("Location", "/archive" if fields.get("return_to")==["archive"] else "/downloads")
            self.end_headers()
            return
        if self.path == "/narrate":
            try:
                payload = narrator.for_playback(narrator.render(fields.get("text", [""])[0]))
            except (ValueError, RuntimeError, ImportError) as error:
                self.send_error(422, str(error))
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if self.path == "/discover/pick":
            key=fields.get("item",[""])[0]
            with closing(connect(self.server.database)) as db, db:
                if fields.get("checked")==["1"]:
                    db.execute("INSERT OR IGNORE INTO discovery_cart SELECT id FROM discovery_item WHERE id=?",(key,))
                else:
                    db.execute("DELETE FROM discovery_cart WHERE id=?",(key,))
                count=db.execute("SELECT count(*) FROM discovery_cart").fetchone()[0]
            payload=str(count).encode()
            self.send_response(200)
            self.send_header("Content-Type","text/plain")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/discover/add":
            key=fields.get("item",[""])[0]
            with closing(connect(self.server.database)) as db,db:
                row=db.execute("SELECT title FROM discovery_item WHERE id=? AND (filename IS NULL OR (provider='Internet Archive' AND kind IN ('Films','Shows')))",(key,)).fetchone()
                if row:self.server.downloads.enqueue(db,[{"id":"discover-"+key,"title":row["title"]}])
            self.server.downloads.wakeup.set()
            self.send_response(303);self.send_header("Location","/downloads");self.end_headers();return
        if self.path == "/discover/save":
            with closing(connect(self.server.database)) as db, db:
                db.executemany("INSERT OR IGNORE INTO discovery_cart SELECT id FROM discovery_item WHERE id=?",((key,) for key in fields.get("item",[])))
                self.server.downloads.enqueue(db, ({"id":"discover-"+r["id"],"title":r["title"]} for r in db.execute("SELECT i.id,i.title FROM discovery_item i JOIN discovery_cart c ON c.id=i.id WHERE filename IS NULL")))
                db.execute("DELETE FROM discovery_cart")
            self.server.downloads.wakeup.set()
            self.send_response(303)
            self.send_header("Location","/downloads")
            self.end_headers()
            return
        if self.path == "/echolite":
            self.ask_echolite(fields.get("prompt", [""])[0].strip())
            return
        if self.path == "/archive/backup":
            self.backup_archive()
            return
        if self.path == "/evidence/scotmesh":
            node = fields.get("node", [""])[0].strip()
            if not node or len(node) > 120:
                self.send_error(400)
                return
            try:
                with closing(connect(self.server.database)) as database:
                    count, available = import_scotmesh(database, node)
                notice = (f"Imported {count} new records from {available} saved timestamps."
                          if available else "The saved node has no public packet or status timestamps.")
            except (ValueError, OverflowError, OSError, KeyError, TypeError) as error:
                notice = f"Could not import ScotMesh node: {error}"
            self.evidence({}, notice)
            return
        if self.path == "/evidence/capture":
            try:
                with closing(connect(self.server.database)) as database:
                    count = capture_receiver(database)
                notice = f"Saved {count} receiver reports." if count else "No running HackRF MeshCore receiver was found."
            except (OSError, ValueError, KeyError, TypeError) as error:
                notice = f"Could not read SDRangel: {error}"
            self.evidence({}, notice)
            return
        regions = list(dict.fromkeys(fields.get("region", [])))
        selected = set(fields.get("source", []))
        available = {item["id"]: item for item in eligible(self.server.catalog, regions)}
        if set(regions) - self.server.catalog["regions"].keys() or selected - available.keys():
            self.send_error(400)
            return
        with closing(connect(self.server.database)) as database:
            with database:
                database.execute("INSERT OR REPLACE INTO selection VALUES (1, ?, ?)",
                                 (json.dumps(regions), json.dumps(sorted(selected))))
                database.execute("INSERT OR REPLACE INTO refresh_preference VALUES (1, ?)",
                                 (int(fields.get("refresh") == ["1"]),))
                self.server.downloads.enqueue(database, (available[name] for name in sorted(selected)))
        self.server.downloads.wakeup.set()
        self.send_response(303)
        self.send_header("Location", "/downloads")
        self.end_headers()


def create_server(port, database_path, echolite=None, kit=None):
    with closing(connect(database_path)) as database, database:
        database.execute("""CREATE TABLE IF NOT EXISTS selection (
            id INTEGER PRIMARY KEY CHECK(id=1), regions TEXT NOT NULL, sources TEXT NOT NULL
        )""")
    server = WorkspaceServer(("127.0.0.1", port), Dashboard)
    try:
        server.private_browser = private_browser.Session(database_path.parent / "Tor")
        if server.private_browser.wanted and not os.environ.get("ANDROID_ROOT"):
            try:server.private_browser.start(server.private_browser.location)
            except OSError:pass
        server.card_previews = {}
        server.companion_status = database_path.parent / "Android/status.json"
        server.news = News(database_path)
        server.catalog = json.loads(CATALOG.read_text())
        server.database = database_path
        server.downloads = Downloads(database_path, server.catalog)
        server.token = secrets.token_urlsafe(32)
        server.echolite = echolite
        starter = Path(__file__).with_name("Starter Kit")
        server.kit = kit.resolve() if kit and kit.is_dir() else (starter.resolve() if starter.is_dir() else None)
        with closing(connect(database_path)) as db, db:
            personal_library.seed_empty_shelves(db, database_path.parent, server.kit)
        server.puzzles = json.loads(Path(__file__).with_name("puzzles.json").read_text())
        server.kit_logs = KitReceptionLogs(server.kit)
        edition_folder = database_path.parent / "Wikipedia"
        server.wiki = Wiki(server.kit, echolite, edition_folder)
        server.editions = Editions(edition_folder, server.wiki)
        server.intel = Intel(database_path)
        server.chat_lock = Lock()
        def maintain_cache():
            while not server.downloads.stopping.is_set():
                try:
                    storage_policy.clean(database_path.parent)
                except (OSError, sqlite3.Error):
                    pass
                if server.downloads.stopping.wait(3600):
                    break
        Thread(target=maintain_cache, daemon=True).start()
    except Exception:
        server.server_close()
        raise
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8778)
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--echolite", type=Path, help="Path to a provisioned EchoLite launcher")
    parser.add_argument("--kit", type=Path, help="Folder containing the OffGrid Kit")
    parser.add_argument("--parent-pid", type=int, help="Close the helper when its owning app exits")
    args = parser.parse_args()
    with create_server(args.port, args.db, args.echolite, args.kit) as server:
        server.news.start()
        if args.parent_pid is not None:
            def watch_owner():
                while os.getppid() == args.parent_pid:
                    if server.downloads.stopping.wait(1):
                        return
                server.shutdown()
            Thread(target=watch_owner, daemon=True, name="EchoOffGrid app lifetime").start()
        print(f"http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
