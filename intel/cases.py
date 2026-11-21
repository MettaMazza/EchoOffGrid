"""Offline federated search and immutable case exhibits."""
from contextlib import closing
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryFile
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED
import base64
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
            CREATE TABLE IF NOT EXISTS case_finding(uuid TEXT PRIMARY KEY,case_uuid TEXT NOT NULL REFERENCES case_identity(uuid),
                written_utc TEXT NOT NULL,statement TEXT NOT NULL,unknowns TEXT NOT NULL,links TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS case_relationship(
                uuid TEXT PRIMARY KEY,case_uuid TEXT NOT NULL REFERENCES case_identity(uuid),
                written_utc TEXT NOT NULL,subject TEXT NOT NULL,predicate TEXT NOT NULL,object TEXT NOT NULL,
                assessment TEXT NOT NULL,exhibit_ref TEXT NOT NULL,passage TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS relationship_case ON case_relationship(case_uuid,written_utc);
            CREATE INDEX IF NOT EXISTS finding_case ON case_finding(case_uuid,written_utc);
            CREATE INDEX IF NOT EXISTS exhibit_owner ON exhibit(owner,id);
        """)


def exhibit_ref(citation, digest):
    return sha256((citation+"\n"+digest).encode()).hexdigest()


def findings(db, owner):
    rows=db.execute("""SELECT f.* FROM case_finding f JOIN case_identity c ON c.uuid=f.case_uuid
        WHERE c.owner=? ORDER BY f.written_utc,f.uuid""",(owner,))
    return [dict(uuid=r["uuid"],written_utc=r["written_utc"],statement=r["statement"],
                 unknowns=r["unknowns"],links=json.loads(r["links"])) for r in rows]


def add_finding(service, owner, statement, unknowns, links):
    statement,unknowns=statement.strip(),unknowns.strip()
    if not statement or len(statement)>2000 or len(unknowns)>2000:
        raise ValueError("Enter a finding and keep each text field within 2,000 characters")
    if not isinstance(links,dict) or len(links)>100:
        raise ValueError("Choose up to 100 exhibits")
    with closing(connection(service)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        case=db.execute("SELECT uuid FROM case_identity WHERE owner=?",(owner,)).fetchone()
        if not case:raise ValueError("Select a case first")
        valid={exhibit_ref(*r) for r in db.execute("SELECT citation,hash FROM exhibit WHERE owner=?",(owner,))}
        if any(ref not in valid or role not in ("supports","contradicts") for ref,role in links.items()):
            raise ValueError("Choose exhibits from this case")
        key=str(uuid.uuid4())
        db.execute("INSERT INTO case_finding VALUES(?,?,?,?,?,?)",(key,case[0],iso(time.time()),statement,unknowns,json.dumps(links,sort_keys=True)))
        return key


def relationships(db, owner):
    return [dict(row) for row in db.execute("""
        SELECT r.* FROM case_relationship r JOIN case_identity c ON c.uuid=r.case_uuid
        WHERE c.owner=? ORDER BY r.written_utc,r.uuid""", (owner,))]


def add_relationship(service, owner, subject, predicate, obj, assessment, ref, passage):
    terms = [term.strip() for term in (subject, predicate, obj)]
    if any(not term or len(term) > 160 for term in terms):
        raise ValueError("Enter two entities and a relationship, up to 160 characters each.")
    passage = passage.strip()
    if assessment not in ("Supported", "Disputed", "Uncertain") or not 1 <= len(passage) <= 2000:
        raise ValueError("Choose an assessment and enter the passage or page you reviewed.")
    with closing(connection(service)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        case = db.execute("SELECT uuid FROM case_identity WHERE owner=?", (owner,)).fetchone()
        if not case or not any(exhibit_ref(*row) == ref for row in
                               db.execute("SELECT citation,hash FROM exhibit WHERE owner=?", (owner,))):
            raise ValueError("Select a cited exhibit from this case.")
        ident = str(uuid.uuid4())
        db.execute("INSERT INTO case_relationship VALUES(?,?,?,?,?,?,?,?,?)",
                   (ident, case[0], iso(time.time()), *terms, assessment, ref, passage))
    return ident


def listing(service, owner=0):
    with closing(connection(service)) as db:
        cases = [dict(r) for r in db.execute("SELECT id,title FROM investigation ORDER BY id DESC")]
        items = []
        for number,row in enumerate(db.execute("SELECT citation,hash FROM exhibit WHERE owner=? ORDER BY citation,hash",(owner,)),1):
            items.append(dict(json.loads(row["citation"]), exhibit=number, ref=exhibit_ref(row["citation"],row["hash"]), sha256=row["hash"]))
        notes=findings(db,owner)
        edges=relationships(db,owner)
    return dict(cases=cases, items=items, findings=notes, relationships=edges)


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
            row=db.execute("SELECT body,media,received FROM intel.obs WHERE region=? AND id=? UNION ALL SELECT body,media,json_extract(body,'$.received') received FROM intel_saved WHERE region=? AND id=? LIMIT 1",(region,uid,region,uid)).fetchone()
            record=json.loads(row["body"])
            if row["received"]:citation["retrieved_utc"]=iso(row["received"])
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


def attach_landmark(service, owner, region, feature_key, expected):
    with closing(connection(service)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM investigation WHERE id=?",(owner,)).fetchone():
            raise ValueError("Select a case first.")
        pack = db.execute("SELECT * FROM intel.landmark_pack WHERE region=?", (region,)).fetchone()
        if not pack or sha256(pack["payload"]).hexdigest() != expected:
            raise ValueError("The extract changed. Search again to review the current landmark.")
        feature = next((f for f in json.loads(pack["payload"])["elements"]
                        if f"{f['type']}/{f['id']}" == feature_key), None)
        if not feature:
            raise ValueError("Landmark unavailable.")
        citation = dict(collection="landmarks",key=feature_key,title=feature.get("tags",{}).get("name") or feature_key,
                        publisher="OpenStreetMap contributors",rights="ODbL 1.0",material="Original OSM extract",
                        url="https://www.openstreetmap.org/"+feature_key,extract_url=pack["source_url"],
                        basis="Map edit" if feature.get("timestamp") else "Retrieved",
                        date_utc=feature.get("timestamp") or iso(pack["collected"]),retrieved_utc=iso(pack["collected"]),
                        feature_version=feature.get("version"))
        db.execute("INSERT OR IGNORE INTO exhibit_blob VALUES(?,?)",(expected,pack["payload"]))
        db.execute("INSERT OR IGNORE INTO exhibit(owner,citation,hash) VALUES(?,?,?)",
                   (owner,json.dumps(citation,sort_keys=True),expected))
    return expected


def capture_page(service, owner, page):
    from private_browser import link_address
    if not isinstance(page,dict) or any(not isinstance(page.get(k),str) for k in ("url","title","html","text","captured")):
        raise ValueError("Incomplete browser capture.")
    if len(page["url"])>4096 or len(page["title"])>1000:
        raise ValueError("Page address or title is too long.")
    url=link_address(page["url"])
    stamp=datetime.fromisoformat(page["captured"].replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Capture needs a timezone.")
    captured=iso(stamp.timestamp())
    html=page["html"].encode()
    if not html or len(html)>8*1024*1024:
        raise ValueError("Rendered page is empty or exceeds 8 MiB.")
    records=[("Rendered HTML",html)]
    if page.get("viewport"):
        if not isinstance(page["viewport"],str) or len(page["viewport"])>8*1024*1024:
            raise ValueError("Viewport image exceeds the capture limit.")
        jpeg=base64.b64decode(page["viewport"], validate=True)
        if not jpeg.startswith(b"\xff\xd8\xff") or not jpeg.endswith(b"\xff\xd9"):
            raise ValueError("Invalid viewport image.")
        records.append(("Browser viewport",jpeg))
    if page["text"].strip():
        records.append(("Rendered page text",page["text"].encode()))
    with closing(connection(service)) as db,db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM investigation WHERE id=?",(owner,)).fetchone():
            raise ValueError("Select a case first.")
        for material,payload in records:
            digest=sha256(payload).hexdigest()
            citation=dict(collection="browser",key=url,title=page["title"] or url,publisher=urlsplit(url).hostname,
                          url=url,rights="See publisher",basis="Browser capture",date_utc=captured,
                          retrieved_utc=captured,material=material)
            db.execute("INSERT OR IGNORE INTO exhibit_blob VALUES(?,?)",(digest,payload))
            db.execute("INSERT OR IGNORE INTO exhibit(owner,citation,hash) VALUES(?,?,?)",
                       (owner,json.dumps(citation,sort_keys=True),digest))
    return {"count":len(records)}


def exhibit_original(service, owner, ref):
    with closing(connection(service)) as db:
        for row in db.execute("SELECT citation,hash FROM exhibit WHERE owner=?", (owner,)):
            if exhibit_ref(row["citation"],row["hash"]) != ref:
                continue
            payload = db.execute("SELECT payload FROM exhibit_blob WHERE hash=?", (row["hash"],)).fetchone()
            if not payload or sha256(payload[0]).hexdigest() != row["hash"]:
                raise ValueError("Stored evidence failed its integrity check.")
            return payload[0]
    raise ValueError("Exhibit unavailable in this case.")


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
                ext=ext or {"Rendered HTML":"html.txt","Rendered page text":"txt","Original OSM extract":"json","Imported GeoJSON":"geojson","Publisher HTML":"html","Normalised observation":"json","Saved news extract":"txt"}.get(c["material"],"bin")
                path=f"evidence/{number}.{ext}"
                bundle.writestr(path,data)
                c.update(file=path,sha256=r["hash"],number=number,ref=exhibit_ref(r["citation"],r["hash"]))
                manifest["exhibits"].append(c)
                lines.extend([f"[{number}] {c['title']}",f"{c['publisher']} · {c['basis']} {c['date_utc']} · {c['material']}",c["url"] or "Local record "+c["key"],path,"SHA-256 "+r["hash"],""])
            manifest["findings"]=findings(db,owner)
            numbers={e["ref"]:e["number"] for e in manifest["exhibits"]}
            for f in manifest["findings"]:
                lines.extend(["Finding · "+f["written_utc"],f["statement"]])
                for ref,role in f["links"].items():
                    lines.append(f"Exhibit [{numbers[ref]}] {role} this finding")
                if f["unknowns"]:lines.append("Still unknown: "+f["unknowns"])
                lines.append("")
            manifest["relationships"]=relationships(db,owner)
            for edge in manifest["relationships"]:
                lines.extend([f"{edge['subject']} · {edge['predicate']} · {edge['object']}",
                              f"{edge['assessment']} · Reviewed {edge['written_utc']}",
                              f"Exhibit [{numbers[edge['exhibit_ref']]}] · {edge['passage']}", ""])
            bundle.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
            bundle.writestr("citations.txt","\n".join(lines))
        output.seek(0)
        return output
    except BaseException:
        output.close()
        raise
