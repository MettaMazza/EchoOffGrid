"""OpenIntel workspace, local HTTP actions and packaged assets."""
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode
import json
import re
import sqlite3
import time

from . import providers as p

ROOT=Path(__file__).resolve().parent


def page(params,android=False):
    key=params.get("region",["aberdeen"])[0]
    p.region(key)
    regions=dict(p.REGIONS)
    if key not in regions:regions[key]=p.region(key)
    options="".join(f'<option value="{escape(k)}" {"selected" if k==key else ""}>{escape(name)}</option>' for k,(name,*_) in regions.items())
    layers=list(dict.fromkeys(item[0] for item in p.SOURCES.values()))
    filters=''.join(f'<button type="button" aria-pressed="true" data-layer="{escape(name)}">{escape(name)}</button>' for name in layers)
    cards=[]
    for key,item in p.SOURCES.items():
        layer,title,coverage,delay,access,rights,url=item
        link=f'<a href="{escape(url)}" rel="noreferrer">Publisher ↗</a>' if url else ""
        player='<a href="/openintel/camera">Watch live</a>' if key=="maui" else ""
        cards.append(f'<article data-provider="{key}"><small>{escape(layer)} · {escape(coverage)}</small><strong>{escape(title)}</strong><span>{escape(access)} · {escape(rights)}</span>{link}{player}</article>')
    return f'''<section id="openintel"><div class="intel-heading"><div><h2>OpenIntel</h2></div>
<label>Region <select id="intel-region">{options}<option value="custom">Custom coordinates…</option></select></label>
<button id="intel-live" aria-pressed="false">Start live updates</button></div>
<form id="intel-custom" hidden><label>Latitude <input type="number" name="lat" min="-85" max="85" step=".001" required></label>
<label>Longitude <input type="number" name="lon" min="-180" max="180" step=".001" required></label><button>View region</button></form>
<div class="intel-tabs" role="group" aria-label="Observation mode"><button data-view="reports">Latest</button><button data-view="saved">Saved</button><button data-view="sample">Offline samples</button></div>
<div class="intel-work"><section class="intel-map"><iframe id="intel-map" title="Offline observation map" src="/atlas/openintel.html"></iframe>
<div class="intel-time"><button id="intel-play" aria-label="Play observation history">▶ Replay</button><input id="intel-time" aria-label="Replay time" type="range"><output id="intel-clock"></output><button id="intel-now">Now</button></div></section>
<aside class="intel-detail" id="intel-detail" aria-label="Selected observation"></aside></div>
<button id="intel-reopen" hidden>Show observation details</button><div class="intel-layers" aria-label="Visible layers">{filters}</div>
<p id="intel-message" role="status"></p><div class="section-head"><h3 id="intel-count">Observations</h3><input type="search" id="intel-find" aria-label="Filter observations" placeholder="Find a report…"></div>
<div id="intel-rows"></div>
<details class="intel-tools"><summary>Sources and coverage</summary><label>Search catalogue <input id="intel-catalog-search" type="search" placeholder="Region, layer, access or provider"></label>
<div id="intel-providers">{"".join(cards)}</div>
<form id="intel-key"><label>AISStream key for this session <input type="password" autocomplete="off" name="key" maxlength="200"></label><button>Connect key</button><button type="button" id="intel-forget">Forget key</button></form></details>
<details class="intel-tools"><summary>Regional imagery pack</summary><form id="intel-imagery"><label>NASA Terra daily composite <input type="date" name="day" required></label><button>Acquire regional image</button></form><p>Open the image observation and choose Save to keep the dated view offline.</p></details>
<details class="intel-tools"><summary>Import local receiver observations</summary>
<p>Import timestamped GeoJSON points from a compatible decoder. Each feature needs a title and UTC time in its properties.</p>
<form id="intel-import"><input type="file" name="file" required accept=".geojson,.json"><button>Import points</button></form></details>
<script defer src="/openintel/app.js"></script></section>'''


def send(handler,body,mime,status=200):
    handler.send_response(status)
    handler.send_header("Content-Type",mime)
    handler.send_header("Cache-Control","no-store")
    handler.send_header("X-Content-Type-Options","nosniff")
    handler.send_header("Content-Length",str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def respond(handler,value,status=200):
    send(handler,json.dumps(value,allow_nan=False).encode(),"application/json",status)


def read(handler,path,params):
    service=handler.server.intel
    try:
        first=lambda k,d:params.get(k,[d])[0]
        if path=="/openintel":
            handler.send_page("OpenIntel",page(params,getattr(handler.server,"android",False)))
        elif path=="/openintel/camera":
            handler.send_response(302)
            handler.send_header("Location","https://www.mauirealestate.net/live/embed.html")
            handler.end_headers()
        elif path=="/openintel/app.js":
            send(handler,(ROOT/"app.js").read_bytes(),"application/javascript")
        elif path=="/openintel/data":
            data=service.view(first("region","aberdeen"),int(first("at","0")),first("view","")=="saved",first("view","")=="sample")
            data["sources"]={k:dict(layer=v[0],title=v[1],rights=v[5],url=v[6],interval=v[3]) for k,v in p.SOURCES.items()}
            respond(handler,data)
        elif path.startswith("/openintel/image/"):
            uid=path.split("/")[-1]
            blob=service.media(uid) if re.fullmatch("[a-f0-9]{64}",uid) else None
            if blob:send(handler,blob,"image/png" if blob.startswith(b"\x89PNG") else "image/jpeg")
            else:handler.send_error(404)
        else:handler.send_error(404)
    except (ValueError,TypeError) as err:respond(handler,{"error":str(err)},400)


def write(handler,fields):
    service=handler.server.intel
    try:
        first=lambda k,d="":fields.get(k,[d])[0]
        key=first("region","aberdeen")
        p.region(key)
        action=first("action")
        value={}
        if action=="refresh":service.refresh(key,fields.get("sources",[]),first("day") or None)
        elif action=="save":
            stamp=int(first("at","0")) or int(time.time())
            if abs(stamp-time.time())>15*86400 and first("id").startswith("orbit-"):raise ValueError("Prediction outside available period")
            value["id"]=service.save(key,first("id"),stamp)
        elif action=="key":
            token=first("key")
            if token and not re.fullmatch(r"[A-Za-z0-9._-]{8,200}",token):raise ValueError("Invalid key format")
            with service.lock:
                service.ais_key=token
                service.live_ais.clear()
        elif action=="import":value["count"]=service.local(key,first("geojson"))
        else:raise ValueError("Unknown OpenIntel action")
        respond(handler,value)
    except (ValueError,KeyError,IndexError,TypeError,OverflowError) as err:
        respond(handler,{"error":str(err)[:200]},400)
