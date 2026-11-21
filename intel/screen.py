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
from . import visuals, orbits, cases, places
from shutil import copyfileobj

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
<details class="intel-tools" id="case-workspace"><summary>Investigations · Search evidence and manage cases</summary>
<section><h3>Landmark clues</h3>
<form id="case-places"><label>Search regional landmarks<input name="clue" type="search" maxlength="180" placeholder="Harbour, lighthouse, station…"></label>
<button>Search extract</button><button type="button" id="case-map-clues">Search visible map</button><button type="button" id="case-places-fetch">Download regional landmarks</button></form>
<output id="case-places-status" role="status"></output><div id="case-places-results"></div>
<div class="visual-pages"><button id="case-places-prev" disabled>Previous landmarks</button><button id="case-places-next" disabled>Next landmarks</button></div></section>
<section><h3>Observation coverage</h3>
<form id="case-coverage"><label>From (UTC)<input name="start" type="datetime-local" required></label>
<label>Until (UTC, exclusive)<input name="end" type="datetime-local" required></label><button>Check selected region</button></form>
<output id="case-coverage-status" role="status"></output><div id="case-coverage-results"></div></section>
<form id="case-search" novalidate><label>Place or search term<input name="place" type="search" placeholder="Aberdeen, North Sea…"></label>
<label>From (UTC)<input type="date" name="start"></label><label>Through (UTC)<input type="date" name="end"></label><button>Search local sources</button></form>
<p>Search place names, regional labels and text across retained observations, news, source snapshots and downloaded documents. Each result identifies the date used.</p>
<form id="case-create"><label>New case<input required maxlength="120" name="title" placeholder="Investigation name"></label><button>Create case</button></form>
<label>Current case <select id="case-owner"></select></label> <a id="case-export" hidden>Export case ZIP</a>
<div id="case-exhibits"></div>
<section id="case-analysis" hidden><h3>Case timeline</h3><ol id="case-timeline"></ol><h3>Entity relationships</h3><div id="case-relationships"></div>
<details><summary>Record a reviewed relationship</summary><form id="case-relationship">
<label>Entity<input name="subject" maxlength="160" placeholder="First organisation or person" required></label>
<label>Relationship<input name="predicate" maxlength="160" placeholder="e.g. issued a permit to" required></label>
<label>Related entity<input name="object" maxlength="160" required></label>
<label>Cited exhibit<select name="ref" required></select></label>
<label>Review assessment<select name="assessment" required><option value="">Select assessment</option><option>Supported</option><option>Disputed</option><option>Uncertain</option></select></label>
<label>Passage or page reviewed<textarea name="passage" maxlength="2000" required></textarea></label><button>Save relationship</button></form></details>
<h3>Findings</h3><div id="case-findings"></div>
<form id="case-finding"><label>Finding<textarea name="statement" maxlength="2000" required></textarea></label>
<label>Still unknown<textarea name="unknowns" maxlength="2000"></textarea></label>
<fieldset id="case-links"><legend>Evidence for this finding</legend></fieldset><button>Save finding</button></form></section><output id="case-status" role="status"></output><div id="case-results"></div><div class="visual-pages"><button id="case-prev" disabled>Previous</button><span id="case-page"></span><button id="case-next" disabled>Next</button></div></details>
<script defer src="/openintel/cases.js"></script><section id="visual-browser" data-android="{int(android)}" aria-label="Cameras and satellite imagery">
<div class="visual-heading"><h3>Cameras &amp; satellite imagery</h3><label>Collection <select id="visual-kind"><option value="all">All visuals</option><option value="video">Video cameras · live and clips</option><option value="still">Still cameras</option><option value="viewers">Publisher camera viewers</option><option value="space">Satellite imagery</option></select></label></div>
<details class="intel-tools" id="compare-imagery"><summary>Compare dated satellite imagery</summary>
<form id="compare-dates"><label>Sensor <select name="sensor"><option value="terra">Terra MODIS</option><option value="aqua">Aqua MODIS</option><option value="noaa20">NOAA-20 VIIRS</option></select></label>
<label>Earlier day <input type="date" name="earlier" required></label><label>Later day <input type="date" name="later" required></label>
<button>Compare local images</button></form><output id="compare-status" role="status"></output><div id="compare-frames"></div></details>
<div class="visual-controls"><input type="search" id="visual-search" aria-label="Search camera and satellite directory" placeholder="Find a place, camera or satellite"><select id="visual-provider" aria-label="Publisher"><option value="">All publishers</option></select><label>Composite date <input type="date" id="visual-date"></label></div>
<div id="visual-cards" aria-live="polite"></div><div class="visual-pages"><button type="button" id="visual-prev">Previous</button><output id="visual-count"></output><button type="button" id="visual-next">Next</button></div>
<dialog id="visual-detail"><button type="button" id="visual-close">Close</button><div id="visual-content"></div></dialog></section>
<details class="intel-tools" id="orbit-explorer"><summary>Satellite orbits and passes · {len(orbits.directory())} objects</summary>
<form id="orbit-form"><label>Search by name or NORAD number <input type="search" id="orbit-find" placeholder="ISS, NOAA, Sentinel…"></label><label>Satellite <select id="orbit-choice"></select></label>
<button>Show predicted orbit</button><button type="button" id="orbit-refresh">Refresh orbital elements</button></form><output id="orbit-detail" role="status"></output></details>
<form id="intel-custom" hidden><label>Latitude <input type="number" name="lat" min="-85" max="85" step=".001" required></label>
<label>Longitude <input type="number" name="lon" min="-180" max="180" step=".001" required></label><button>View region</button></form>
<div class="intel-tabs" role="group" aria-label="Observation mode"><button data-view="reports">Latest</button><button data-view="saved">Saved</button><button data-view="sample">Offline samples</button></div>
<div class="intel-work"><section class="intel-map"><iframe id="intel-map" title="Offline observation map" src="/atlas/openintel.html"></iframe>
<div class="intel-time"><button id="intel-play" aria-label="Play observation history">▶ Replay</button><input id="intel-time" aria-label="Replay time" type="range"><output id="intel-clock"></output><button id="intel-now">Now</button></div></section>
<aside class="intel-detail" id="intel-detail" aria-label="Selected observation"></aside></div>
<dialog id="track-history"><button type="button" id="track-close">Close</button><h3 id="track-title"></h3>
<p id="track-summary" role="status"></p><ol id="track-reports"></ol><div class="visual-pages"><button id="track-prev">Newer reports</button><button id="track-next">Older reports</button></div></dialog>
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
<script defer src="/openintel/visuals.js"></script><script defer src="/openintel/app.js"></script></section>'''


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
            handler.send_header("Location","/private-browser?to=https%3A%2F%2Fwww.mauirealestate.net%2Flive%2Fembed.html")
            handler.end_headers()
        elif path=="/openintel/cases.js":
            send(handler,(ROOT/"cases.js").read_bytes(),"application/javascript")
        elif path=="/openintel/cases":
            respond(handler,cases.listing(service,int(first("owner","0"))))
        elif path=="/openintel/places":
            respond(handler,places.search(service,first("region","aberdeen"),first("clue",""),int(first("page","0"))))
        elif path=="/openintel/history":
            respond(handler,service.track_history(first("region","aberdeen"),first("source",""),first("object",""),
                    int(first("until","0")),int(first("page","0"))))
        elif path=="/openintel/coverage":
            respond(handler,service.coverage(first("region","aberdeen"),first("start",""),first("end","")))
        elif path=="/openintel/search":
            respond(handler,cases.search(service,first("place",""),first("start",""),first("end",""),int(first("page","0"))))
        elif re.fullmatch(r"/openintel/cases/[0-9]+/exhibits/[a-f0-9]{64}",path):
            _,_,_,owner,_,ref=path.split("/")
            payload=cases.exhibit_original(service,int(owner),ref)
            mime=next((mime for signature,mime in [(b"%PDF-","application/pdf"),(b"\xff\xd8\xff","image/jpeg"),
                      (b"\x89PNG\r\n\x1a\n","image/png")] if payload.startswith(signature)),None)
            if not mime:
                try:
                    payload.decode("utf-8")
                    mime="text/plain; charset=utf-8"
                except UnicodeDecodeError:
                    mime="application/octet-stream"
            handler.send_response(200)
            handler.send_header("Content-Security-Policy","sandbox; default-src 'none'")
            handler.send_header("X-Content-Type-Options","nosniff")
            handler.send_header("Cache-Control","no-store")
            handler.send_header("Content-Type",mime)
            handler.send_header("Content-Length",str(len(payload)))
            handler.end_headers()
            handler.wfile.write(payload)
        elif re.fullmatch(r"/openintel/cases/[0-9]+/export",path):
            owner=int(path.split("/")[-2])
            with cases.export(service,owner) as file:
                size=file.seek(0,2);file.seek(0)
                handler.send_response(200)
                handler.send_header("Content-Type","application/zip")
                handler.send_header("Content-Length",str(size))
                handler.send_header("Content-Disposition",f'attachment; filename="EchoOffGrid-case-{owner}.zip"')
                handler.send_header("Cache-Control","no-store")
                handler.end_headers()
                copyfileobj(file,handler.wfile)
        elif path=="/openintel/visuals.js":
            send(handler,(ROOT/"visuals.js").read_bytes(),"application/javascript")
        elif path=="/openintel/orbits":
            respond(handler,[dict(number=n,name=r["OBJECT_NAME"],group=r["group"]) for n,r in orbits.directory().items()])
        elif path=="/openintel/composite":
            respond(handler,visuals.local_composite(service,first("sensor","terra"),first("region","aberdeen"),first("day","")))
        elif path=="/openintel/visuals":
            respond(handler,visuals.response(params))
        elif path.startswith("/openintel/poster/"):
            name=path.split("/")[-1]
            if name in ("terra","crater","east","west"):
                send(handler,(ROOT/"previews"/(name+".jpg")).read_bytes(),"image/jpeg")
            else:handler.send_error(404)
        elif path.startswith("/openintel/frame/"):
            with service.lock:blob=service.preview_frames.get(path.split("/")[-1])
            if blob:send(handler,blob,"image/jpeg")
            else:handler.send_error(404)
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
        if action=="case-create":value={"id":cases.create(service,first("title"))}
        elif action=="case-landmark":
            value={"sha256":cases.attach_landmark(service,int(first("owner")),key,first("feature"),first("digest"))}
        elif action=="places-fetch":
            try:places.acquire(service,key)
            except (OSError,TimeoutError):raise ValueError("Could not reach OpenStreetMap. Try searching your saved extract.")
        elif action=="case-relationship":
            value={"id":cases.add_relationship(service,int(first("owner")),first("subject"),first("predicate"),
                       first("object"),first("assessment"),first("ref"),first("passage"))}
        elif action=="case-finding":value={"id":cases.add_finding(service,int(first("owner")),first("statement"),first("unknowns"),json.loads(first("links","{}")))}
        elif action=="case-attach":value={"sha256":cases.attach(service,int(first("owner")),first("collection"),first("key"),first("version"))}
        elif action=="orbit-choice":
            value=orbits.selected_prediction(service,key,first("number"),first("refresh")=="1")
        elif action=="visual-frame":
            from urllib.error import URLError
            try:value=visuals.collect(service,first("id"),key,first("day"))
            except (URLError,TimeoutError,OSError):raise ValueError("Publisher unavailable. Try again or choose another source.")
        elif action=="refresh":service.refresh(key,fields.get("sources",[]),first("day") or None)
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
