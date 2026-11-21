"""Local observations, opt-in live feeds and offline playback."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import urlencode
import json
import os
import re
import sqlite3
import time

ROOT=Path(__file__).resolve().parent
from . import providers as p
from .orbits import predict

MAX_ROWS=24000
MAX_MEDIA=48*1024**2
DAY=86400


def connect(path):
    db=sqlite3.connect(path,timeout=10)
    db.row_factory=sqlite3.Row
    return db


class Intel:
    def __init__(self,archive):
        self.archive=archive
        self.root=archive.parent/"OpenIntel"
        self.root.mkdir(exist_ok=True)
        self.path=self.root/"observations.sqlite3"
        self.pool=ThreadPoolExecutor(3,thread_name_prefix="openintel")
        self.lock=Lock()
        self.pending=set()
        self.live_ais={}
        self.preview_frames={}
        # AIS credentials are intentionally session-only, including on Android external storage.
        self.ais_key=""
        with closing(connect(self.path)) as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS obs(region,source,object,stamp INTEGER,received INTEGER,id,body,media BLOB,PRIMARY KEY(region,id));
            CREATE TABLE IF NOT EXISTS import_original(hash TEXT PRIMARY KEY,body BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS import_record(region TEXT,id TEXT,hash TEXT,PRIMARY KEY(region,id));
            CREATE INDEX IF NOT EXISTS by_time ON obs(region,stamp);
            CREATE INDEX IF NOT EXISTS by_id ON obs(id);
            CREATE TABLE IF NOT EXISTS status(region,source,attempt INTEGER,next INTEGER,note,PRIMARY KEY(region,source));
            CREATE TABLE IF NOT EXISTS elements(received INTEGER PRIMARY KEY,body);
            CREATE TABLE IF NOT EXISTS prefs(key PRIMARY KEY,value);
            """)
            from . import places
            places.initialize(db)
            self.trim(db)
            db.execute("UPDATE status SET note='Refresh interrupted', next=0 WHERE note='Fetching…'")
            db.commit()
        with closing(connect(archive)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS intel_saved(id TEXT PRIMARY KEY,region TEXT,body TEXT,media BLOB)")
            db.commit()

        from .cases import initialize
        initialize(self)

    def close(self):
        self.pool.shutdown(wait=False,cancel_futures=True)

    def status(self,key):
        with closing(connect(self.path)) as db:
            return {r["source"]:dict(r) for r in db.execute("SELECT source,attempt,next,note FROM status WHERE region IN (?, '*') OR substr(region,1,length(?)+1)=? || ':' ORDER BY attempt",(key,key,key))}

    def track_history(self, key, source, obj, until, page=0):
        p.region(key)
        if source not in ("air", "ships") or not obj or len(obj) > 96:
            raise ValueError("Choose a recorded aircraft or vessel.")
        if page < 0 or page > 100000 or until <= 0:
            raise ValueError("Invalid history window.")
        with closing(connect(self.path)) as db:
            db.execute("ATTACH DATABASE ? AS library", (str(self.archive),))
            records = db.execute("""
                WITH history AS (
                    SELECT id, stamp, body, received FROM obs
                    WHERE region=? AND source=? AND object=? AND stamp<=?
                    UNION ALL
                    SELECT id, json_extract(body,'$.time'), body, json_extract(body,'$.received')
                    FROM library.intel_saved WHERE region=? AND json_extract(body,'$.source')=?
                    AND json_extract(body,'$.object')=? AND json_extract(body,'$.time')<=?
                    AND NOT EXISTS (SELECT 1 FROM obs WHERE obs.region=library.intel_saved.region
                                    AND obs.id=library.intel_saved.id)
                )
                SELECT body, received FROM history ORDER BY stamp DESC,id DESC LIMIT 51 OFFSET ?
            """, (key, source, obj, until) * 2 + (page * 50,)).fetchall()
        rows = [dict(json.loads(r["body"]), received=r["received"]) for r in records]
        for newer, older in zip(rows, rows[1:]):
            newer["interval"] = newer["time"] - older["time"]
        return {"rows": rows[:50], "more": len(rows) > 50, "gap_seconds": 900,
                "publisher": p.SOURCES[source][1], "url": p.SOURCES[source][6]}

    def coverage(self, key, start, end):
        region_name = p.region(key)[0]
        try:
            bounds = [int(datetime.strptime(value, "%Y-%m-%dT%H:%M")
                          .replace(tzinfo=timezone.utc).timestamp()) for value in (start, end)]
        except (ValueError, OverflowError):
            raise ValueError("Enter both dates and times in UTC.") from None
        if bounds[0] >= bounds[1]:
            raise ValueError("The end must come after the start.")
        # UNION counts each record once even after it has been saved permanently.
        with closing(connect(self.path)) as db:
            db.execute("ATTACH DATABASE ? AS library", (str(self.archive),))
            rows = db.execute("""
                WITH records AS (
                    SELECT id, source, stamp FROM obs WHERE region=? AND stamp>=? AND stamp<?
                    UNION
                    SELECT id, json_extract(body,'$.source'), json_extract(body,'$.time')
                    FROM library.intel_saved WHERE region=? AND json_extract(body,'$.time')>=?
                    AND json_extract(body,'$.time')<?
                )
                SELECT source, count(*) AS count, min(stamp) AS first, max(stamp) AS last
                FROM records GROUP BY source
            """, (key, *bounds, key, *bounds))
            counts = {row["source"]: dict(row) for row in rows}
        sources = []
        for source, metadata in p.SOURCES.items():
            row = counts.get(source, {"count": 0, "first": None, "last": None})
            sources.append(dict(row, source=source, title=metadata[1], access=metadata[4]))
        return {"region": region_name, "sources": sources}

    def refresh(self,key,sources,day=None):
        _,lat,lon=p.region(key)
        if day:
            p.image_row(key,day)
        for source in sources:
            if source not in p.SOURCES:raise ValueError("Unknown source")
            if not p.SOURCES[source][3]:continue
            if source in ("ships","cams") and key!="world" and not(55<=lat<=72 and 15<=lon<=35):continue
            if source in ("air","ais","imagery") and key=="world":continue
            if source=="ais" and not self.ais_key:continue
            scope="*" if source=="orbit" else key
            # An explicit dated imagery request has a separate cache entry.
            scope_key=scope+":"+day if source=="imagery" and day else scope
            now=int(time.time())
            with self.lock,closing(connect(self.path)) as db,db:
                task=(scope_key,source)
                if task in self.pending or len(self.pending)>=14:continue
                prior=db.execute("SELECT next FROM status WHERE region=? AND source=?",task).fetchone()
                if prior and prior[0]>now:continue
                if source=="air":
                    previous=db.execute("SELECT max(attempt) FROM status WHERE source='air'").fetchone()[0]
                    if previous and now-previous<180:continue
                delay=p.SOURCES[source][3]
                db.execute("INSERT OR REPLACE INTO status VALUES (?,?,?,?,?)",(*task,now,now+delay,"Fetching…"))
                self.pending.add(task)
                self.pool.submit(self._run,key,task,day)

    def _run(self,key,task,day):
        scope,source=task
        count=0
        retry=0
        try:
            if source=="orbit":
                rows=p.feed("https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=JSON")
                chosen=[r for r in rows if r.get("NORAD_CAT_ID") in (25544,48274,67683)]
                if not chosen:raise ValueError("Provider returned no selected satellites")
                with closing(connect(self.path)) as db,db:
                    db.execute("INSERT OR REPLACE INTO elements VALUES (?,?)",(int(time.time()),json.dumps(chosen)))
                    db.execute("DELETE FROM elements WHERE received < ?",(time.time()-14*DAY,))
                count=len(chosen)
            elif source=="ais":
                session=self.ais_key
                rows=list(p.ais_live(key,session))[:200]
                now=int(time.time())
                with self.lock:
                    self.live_ais={k:v for k,v in self.live_ais.items() if now-v[0]<300}
                    if session==self.ais_key:self.live_ais[key]=(now,rows)
                count=len(rows)
            else:
                if source=="imagery":
                    date=day or (datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()
                    rows=[p.image_row(key,date)]
                else:
                    fn={"air":p.aircraft,"ships":p.finnish_ships,"cams":p.cameras,"quakes":p.earthquakes,"buoys":p.buoys}[source]
                    rows=fn(key)
                for row in rows:
                    if count>=450:break
                    media=None
                    url=row.pop("image_url",None)
                    if url:
                        with closing(connect(self.path)) as db:
                            if db.execute("SELECT 1 FROM obs WHERE region=? AND id=?",(key,row["id"])).fetchone():
                                count+=1
                                continue
                        media=p.fetch(url,2*1024**2)
                        if source=="imagery":
                            if not p.available_image(media):raise ValueError("No imagery coverage for this date and region")
                        elif not media.startswith(b"\xff\xd8\xff"):raise ValueError("Image unavailable")
                    self.store(key,row,media)
                    count+=1
            note=f"{count} reports" if count else "No reports in this region"
        except HTTPError as err:
            note=f"Publisher returned HTTP {err.code}"
            if err.code==429:
                value=err.headers.get("Retry-After","")
                retry=int(value) if value.isdigit() else 3600
        except ValueError as err:
            note=str(err)[:120] if source=="imagery" else "Source returned invalid data"
        except Exception as err:
            note=f"Source unavailable · {type(err).__name__}"
        finally:
            with self.lock,closing(connect(self.path)) as db,db:
                db.execute("UPDATE status SET note=?,next=max(next,?) WHERE region=? AND source=?",(note,time.time()+retry,*task))
                self.pending.discard(task)
                self.trim(db)

    def store(self,key,row,media=None):
        with closing(connect(self.path)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            previous=db.execute("SELECT body,media FROM obs WHERE region=? AND id=?",(key,row["id"])).fetchone()
            if previous:
                if json.loads(previous["body"])==row and previous["media"]==media:return
                original=row["id"]
                version=sha256(json.dumps(row,sort_keys=True).encode()+(media or b"")).hexdigest()
                row=dict(row,id=sha256((original+version).encode()).hexdigest(),revises=original)
            db.execute("INSERT OR IGNORE INTO obs VALUES (?,?,?,?,?,?,?,?)",(key,row["source"],row["object"],row["time"],int(time.time()),row["id"],json.dumps(row),media))

    def trim(self,db):
        db.execute("DELETE FROM obs WHERE received<?",(time.time()-2*DAY,))
        db.execute("DELETE FROM obs WHERE rowid IN (SELECT rowid FROM obs ORDER BY received DESC,rowid DESC LIMIT -1 OFFSET ?)",(MAX_ROWS,))
        db.execute("DELETE FROM obs WHERE rowid IN (SELECT rowid FROM (SELECT rowid,sum(length(media)) OVER (ORDER BY received DESC,rowid DESC) AS total FROM obs WHERE media IS NOT NULL) WHERE total>?)",(MAX_MEDIA,))
        db.execute("DELETE FROM import_record WHERE NOT EXISTS(SELECT 1 FROM obs WHERE obs.region=import_record.region AND obs.id=import_record.id)")
        db.execute("DELETE FROM import_original WHERE hash NOT IN(SELECT hash FROM import_record)")
        db.execute("DELETE FROM status WHERE attempt<?",(time.time()-14*DAY,))

    def local(self,key,raw):
        data=json.loads(raw)
        features=data.get("features") if isinstance(data,dict) else None
        if not isinstance(features,list) or len(features)>100 or not features:raise ValueError("Import 1–100 timestamped GeoJSON points")
        rows=[]
        for f in features:
            if not isinstance(f,dict) or not isinstance(f.get("geometry"),dict) or not isinstance(f.get("properties"),dict):raise ValueError("Invalid GeoJSON feature")
            g=f["geometry"]; props=f["properties"]
            if g["type"]!="Point":raise ValueError("Receiver imports require Point geometry")
            x,y=g["coordinates"][:2]
            stamp=p.utc(str(props["time"]))
            if not p.inside(p.extent(key),x,y):raise ValueError("A point is outside the selected region")
            rows.append(p.observation("local",props.get("id",props["title"]),props["title"],y,x,stamp,props.get("detail","Received locally")))
        with closing(connect(self.path)) as db,db:
            payload=raw.encode()
            digest=sha256(payload).hexdigest()
            db.execute("INSERT OR IGNORE INTO import_original VALUES(?,?)",(digest,payload))
            for row in rows:
                inserted=db.execute("INSERT OR IGNORE INTO obs VALUES (?,?,?,?,?,?,?,NULL)",(key,row["source"],row["object"],row["time"],int(time.time()),row["id"],json.dumps(row)))
                if inserted.rowcount:db.execute("INSERT INTO import_record VALUES(?,?,?)",(key,row["id"],digest))
        with closing(connect(self.path)) as db,db:self.trim(db)
        return len(rows)

    def media(self,uid):
        for path,table in ((self.archive,"intel_saved"),(self.path,"obs")):
            with closing(connect(path)) as db:
                row=db.execute(f"SELECT media FROM {table} WHERE id=? AND media IS NOT NULL LIMIT 1",(uid,)).fetchone()
                if row:return row[0]
        return None

    def save(self,key,uid,at):
        with closing(connect(self.path)) as db:
            r=db.execute("SELECT body,media,received FROM obs WHERE region=? AND id=?",(key,uid)).fetchone()
        if r:
            body=json.loads(r["body"]); media=r["media"]
            body["received"]=r["received"]
        elif uid.startswith("orbit-"):
            body=next((x for x in self.orbits(key,at) if x["id"]==uid),None)
            if not body:raise ValueError("Prediction unavailable")
            media=None
            uid=sha256(f"{key}|{uid}|{at}".encode()).hexdigest()
            body["id"]=uid
        else:raise ValueError("Only retained local observations can be saved")
        body["media"]=bool(media)
        body["region"]=key
        with closing(connect(self.archive)) as db,db:
            db.execute("INSERT OR IGNORE INTO intel_saved VALUES (?,?,?,?)",(uid,key,json.dumps(body),media))
        return uid

    def orbits(self,key,at,cutoff=None):
        with closing(connect(self.path)) as db:
            r=db.execute("SELECT body,received FROM elements WHERE received<=? ORDER BY received DESC LIMIT 1",(cutoff or int(time.time()),)).fetchone()
        if not r:return []
        rows=predict(json.loads(r[0]),key,at)
        for row in rows:row["received"]=r[1]
        return rows

    def view(self,key,at=0,saved=False,sample=False):
        name,lat,lon=p.region(key)
        now=int(time.time())
        when=at or now
        if at<0 or when>now+2:raise ValueError("Choose a past replay time")
        with closing(connect(self.archive)) as db:
            pins={r["id"]:json.loads(r["body"]) for r in db.execute("SELECT id,body FROM intel_saved WHERE region=?",(key,))}
        with closing(connect(self.path)) as db:
            limits=db.execute("SELECT min(stamp),max(stamp) FROM obs WHERE region=? AND received>=?",(key,now-2*DAY)).fetchone()
            seen={}
            for r in db.execute("SELECT body,received,media IS NOT NULL AS image FROM obs WHERE region=? AND stamp<=? AND received>=? ORDER BY stamp DESC,rowid DESC LIMIT 4800",(key,when,now-2*DAY)):
                obj=json.loads(r[0]);group=(obj["source"],obj["object"])
                if group not in seen:
                    obj.update(received=r[1],media=bool(r[2]),trail=[])
                    seen[group]=obj
                selected=seen[group]
                if obj["source"] in ("air","ships","local") and len(selected["trail"])<40:
                    selected["trail"].append([obj["lon"],obj["lat"],obj["time"]])
            rows=list(seen.values())
        if saved:rows=list(pins.values())
        elif sample:
            rows=[r for r in json.loads((ROOT/"samples.json").read_text()) if r["region"]==key]
        else:
            rows.extend(self.orbits(key,when,when if at else None))
            if not at:
                received,live=self.live_ais.get(key,(0,[]))
                if now-received<=180:rows.extend(dict(obj,received=received) for obj in live)
        for row in rows:row["saved"]=row["id"] in pins
        return dict(region=key,name=name,center=[lon,lat],bounds=p.extent(key),rows=rows,now=now,at=when,
                    earliest=limits[0] or now,latest=limits[1] or now,status=self.status(key),keySet=bool(self.ais_key))

    def home(self):
        with closing(connect(self.path)) as db:
            row=db.execute("SELECT region,body FROM obs ORDER BY received DESC,stamp DESC LIMIT 1").fetchone()
        if not row:return '<a class="intel-home" href="/openintel"><small>OpenIntel</small><strong>Explore the observation map →</strong><span>Aircraft, sea conditions and public cameras</span></a>'
        obj=json.loads(row[1]);query=urlencode({"region":row[0],"item":obj["id"],"at":obj["time"]})
        stamp=datetime.fromtimestamp(obj["time"],timezone.utc).strftime("%d %b · %H:%M UTC")
        return f'<a class="intel-home" href="/openintel?{escape(query)}"><small>OpenIntel · {escape(p.SOURCES[obj["source"]][1])}</small><strong>{escape(obj["title"])}</strong><span>{stamp}</span></a>'

    def library(self):
        with closing(connect(self.archive)) as db:
            saved=list(db.execute("SELECT id,region,body FROM intel_saved ORDER BY rowid DESC LIMIT 100"))
        if not saved:return ""
        links=[]
        for uid,key,raw in saved:
            row=json.loads(raw)
            q=urlencode({"region":key,"view":"saved","item":uid})
            links.append(f'<a class="intel-home" href="/openintel?{escape(q)}"><small>OpenIntel · {escape(p.SOURCES[row["source"]][1])}</small><strong>{escape(row["title"])}</strong></a>')
        return '<h3>Saved observations</h3>'+''.join(links)
