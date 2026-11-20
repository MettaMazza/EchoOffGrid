"""Offline federated search and immutable case exhibits."""
from contextlib import closing
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryFile
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED
import json
import sqlite3
import uuid
import time

from . import providers

LIMIT = 30
MAX_FILE = 32 * 1024**2


def connection(service):
    db = sqlite3.connect(service.archive, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("ATTACH DATABASE ? AS intel", (str(service.path),))
    return db


def initialize(service):
    with closing(connection(service)) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS investigation(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS case_identity(owner INTEGER PRIMARY KEY REFERENCES investigation,uuid TEXT NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS exhibit_blob(hash TEXT PRIMARY KEY, payload BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS exhibit(id INTEGER PRIMARY KEY, owner INTEGER REFERENCES investigation,
                citation TEXT NOT NULL, hash TEXT REFERENCES exhibit_blob, UNIQUE(owner,citation,hash));
            CREATE INDEX IF NOT EXISTS exhibit_owner ON exhibit(owner,id);
        """)


def listing(service, owner=0):
    with closing(connection(service)) as db:
        cases = [dict(r) for r in db.execute("SELECT id,title FROM investigation ORDER BY id DESC")]
        items = []
        for number,row in enumerate(db.execute("SELECT citation,hash FROM exhibit WHERE owner=? ORDER BY citation,hash",(owner,)),1):
            items.append(dict(json.loads(row["citation"]), exhibit=number, sha256=row["hash"]))
    return dict(cases=cases, items=items)


def create(service, title):
    title = title.strip()
    if not 1 <= len(title) <= 120:
        raise ValueError("Enter a case name of 1–120 characters")
    with closing(connection(service)) as db, db:
        owner=db.execute("INSERT INTO investigation(title) VALUES (?)",(title,)).lastrowid
        db.execute("INSERT INTO case_identity VALUES(?,?)",(owner,str(uuid.uuid4())))
        return owner


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds") if stamp else None


def window(start, end):
    lower = date.fromisoformat(start) if start else date.min
    upper = date.fromisoformat(end) if end else None
    if upper and lower > upper:
        raise ValueError("End date precedes start date")
    def midnight(d):
        return int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp())
    return midnight(lower), midnight(upper) + 86400 if upper else 253402300800


# Each branch exposes the same projection. Original BLOBs are read only on attachment.
SOURCES = {
    "archive": """SELECT CAST(s.id AS TEXT) key,s.title,s.source publisher,s.url,s.rights,
        CAST(strftime('%s',min(f.checked_at)) AS INTEGER) stamp,'First retrieved' basis,
        substr(x.body,1,500) preview,x.body searchable,'Publisher file' material
        FROM snapshot s JOIN fetch f ON f.snapshot_id=s.id JOIN search x ON x.rowid=s.id GROUP BY s.id""",
    "news": """SELECT CAST(n.id AS TEXT) key,n.title,n.edition publisher,n.link url,'' rights,n.published stamp,
        'Feed date' basis,n.summary preview,n.edition||' '||n.summary||' '||n.body searchable,
        CASE WHEN o.id IS NULL THEN 'Saved news extract' ELSE 'Publisher HTML' END material
        FROM news_story n LEFT JOIN news_original o ON o.id=n.id AND o.link=n.link""",
    "documents": """SELECT id key,title,provider publisher,url,rights,case_file_time(filename) stamp,
        'Local file modified' basis,preview,preview searchable,'Document file' material
        FROM discovery_item WHERE kind='Documents' AND filename IS NOT NULL""",
}
OBS = """SELECT region||'/'||id key,json_extract(body,'$.title') title,source_name(json_extract(body,'$.source')) publisher,
    coalesce(json_extract(body,'$.retrieval_url'),json_extract(body,'$.image_url'),'') url,'' rights,
    json_extract(body,'$.time') stamp,coalesce(json_extract(body,'$.time_basis'),'Observation') basis,
    json_extract(body,'$.detail') preview,region||' '||region_name(region)||' '||json_extract(body,'$.detail') searchable,
    CASE WHEN media IS NULL THEN 'Normalised observation' ELSE 'Original image' END material FROM """


def register(db, service):
    def filetime(name):
        p = service.archive.parent/'Content'/str(name)
        if p.parent != service.archive.parent/'Content' or p.is_symlink():
            return None
        try: return int(p.stat().st_mtime)
        except OSError: return None
    db.create_function("case_file_time",1,filetime)
    db.create_function("source_name",1,lambda s:providers.SOURCES.get(s,("",s))[1])
    db.create_function("region_name",1,lambda s:providers.REGIONS.get(s,(s,))[0])


def query(db):
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
    branches = {k:v for k,v in SOURCES.items() if {"archive":"snapshot","news":"news_story","documents":"discovery_item"}[k] in tables}
    if "news" in branches and "news_original" not in tables:
        branches["news"] = branches["news"].replace("news_original o","(SELECT NULL id,NULL link) o")
    branches["observation"] = OBS.replace("WHEN media IS NULL","WHEN EXISTS(SELECT 1 FROM intel.import_record ir WHERE ir.id=obs.id AND ir.region=obs.region) THEN 'Imported GeoJSON' WHEN media IS NULL")+"intel.obs UNION ALL "+OBS+"intel_saved WHERE NOT EXISTS (SELECT 1 FROM intel.obs o WHERE o.id=intel_saved.id AND o.region=intel_saved.region)"
    return " UNION ALL ".join("SELECT '"+k+"' collection,t.* FROM ("+v+") t" for k,v in branches.items())


def version(row):
    identity=[row[k] for k in ("collection","key","title","publisher","url","stamp","material")]
    return sha256(json.dumps(identity).encode()).hexdigest()


def search(service, place="", start="", end="", page=0):
    if not 0 <= page <= 100000: raise ValueError("Invalid page")
    lower, upper = window(start,end)
    with closing(connection(service)) as db:
        register(db,service)
        sql = "SELECT collection,key,title,publisher,url,stamp,basis,substr(preview,1,320) preview,material FROM ("+query(db)+""")
            WHERE stamp>=? AND stamp<? AND instr(lower(title||' '||publisher||' '||coalesce(searchable,'')),lower(?))>0
            ORDER BY stamp DESC,collection,key LIMIT ? OFFSET ?"""
        rows = [dict(r) for r in db.execute(sql,(lower,upper,place.strip(),LIMIT+1,page*LIMIT))]
    for row in rows:row["version"]=version(row)
    return dict(rows=rows[:LIMIT],more=len(rows)>LIMIT)


def attach(service, owner, collection, key, expected):
    with closing(connection(service)) as db, db:
        register(db,service)
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM investigation WHERE id=?",(owner,)).fetchone():
            raise ValueError("Select a case first")
        meta = db.execute("SELECT * FROM ("+query(db)+") WHERE collection=? AND key=?",(collection,key)).fetchone()
        if not meta: raise ValueError("Source record is no longer available")
        if expected!=version(meta):raise ValueError("Source record changed. Search again before saving it.")
        citation = {k:meta[k] for k in ("collection","key","title","publisher","url","basis","material","rights")}
        citation["date_utc"]=iso(meta["stamp"])
        if collection=="archive":
            row=db.execute("SELECT body,sha256 FROM snapshot WHERE id=?",(key,)).fetchone()
            payload=row["body"]
            if sha256(payload).hexdigest()!=row["sha256"]:raise ValueError("Archived file failed its integrity check")
        elif collection=="documents":
            name=db.execute("SELECT filename FROM discovery_item WHERE id=?",(key,)).fetchone()[0]
            path=service.archive.parent/'Content'/name
            if path.parent!=service.archive.parent/'Content' or path.is_symlink() or not path.is_file():raise ValueError("Local document unavailable")
            with path.open('rb') as stream:payload=stream.read(MAX_FILE+1)
        elif collection=="news":
            row=db.execute("SELECT title,summary,body,link FROM news_story WHERE id=?",(key,)).fetchone()
            citation["publisher"]=urlsplit(row["link"]).hostname
            if meta["material"]=="Publisher HTML":
                payload, acquired=db.execute("SELECT body,acquired FROM news_original WHERE id=? AND link=?",(key,row["link"])).fetchone()
                citation["retrieved_utc"]=iso(acquired)
            else:payload="\n\n".join(row[k] for k in ("title","summary","body") if row[k]).encode()
        else:
            region,uid=key.rsplit("/",1)
            row=db.execute("SELECT body,media FROM intel.obs WHERE region=? AND id=? UNION ALL SELECT body,media FROM intel_saved WHERE region=? AND id=? LIMIT 1",(region,uid,region,uid)).fetchone()
            record=json.loads(row["body"])
            citation["record"]=record
            citation["rights"]=providers.SOURCES[record["source"]][5]
            if meta["material"]=="Imported GeoJSON":
                payload=db.execute("SELECT body FROM intel.import_original JOIN intel.import_record USING(hash) WHERE region=? AND id=?",(region,uid)).fetchone()[0]
            else:payload=row["media"] or row["body"].encode()
        if not payload or len(payload)>MAX_FILE:raise ValueError("Evidence file is empty or exceeds 32 MiB")
        digest=sha256(payload).hexdigest()
        db.execute("INSERT OR IGNORE INTO exhibit_blob VALUES(?,?)",(digest,payload))
        db.execute("INSERT OR IGNORE INTO exhibit(owner,citation,hash) VALUES(?,?,?)",(owner,json.dumps(citation,sort_keys=True),digest))
        return digest


def export(service, owner):
    output=TemporaryFile()
    try:
        with closing(connection(service)) as db, ZipFile(output,"w",ZIP_DEFLATED) as bundle:
            db.execute("BEGIN")
            case=db.execute("SELECT title FROM investigation WHERE id=?",(owner,)).fetchone()
            if not case:raise ValueError("Case unavailable")
            manifest=dict(case=case[0],exported_utc=iso(time.time()),exhibits=[])
            lines=[case[0],""]
            for number,r in enumerate(db.execute("""SELECT e.citation,e.hash,b.payload FROM exhibit e JOIN exhibit_blob b ON b.hash=e.hash
                    WHERE owner=? ORDER BY e.citation,e.hash""",(owner,)),1):
                c=json.loads(r["citation"]); data=r["payload"]
                if sha256(data).hexdigest()!=r["hash"]:raise ValueError("Evidence failed verification")
                ext=next((e for prefix,e in [(b"%PDF","pdf"),(b"\x89PNG","png"),(b"\xff\xd8","jpg"),(b"PK","zip")] if data.startswith(prefix)),None)
                ext=ext or {"Imported GeoJSON":"geojson","Publisher HTML":"html","Normalised observation":"json","Saved news extract":"txt"}.get(c["material"],"bin")
                path=f"evidence/{number}.{ext}"
                bundle.writestr(path,data)
                c.update(file=path,sha256=r["hash"],number=number)
                manifest["exhibits"].append(c)
                lines.extend([f"[{number}] {c['title']}",f"{c['publisher']} · {c['basis']} {c['date_utc']} · {c['material']}",c["url"] or "Local record "+c["key"],path,"SHA-256 "+r["hash"],""])
            bundle.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
            bundle.writestr("citations.txt","\n".join(lines))
        output.seek(0)
        return output
    except BaseException:
        output.close()
        raise
