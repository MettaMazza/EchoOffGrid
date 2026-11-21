"""Offline landmark clues from dated OpenStreetMap extracts."""
from contextlib import closing
from hashlib import sha256
from math import cos,radians
import json
import time
from urllib.parse import urlencode

from . import providers
from .service import connect

FILTERS = (("man_made", "lighthouse|pier|bridge|breakwater"),
           ("harbour", "yes"), ("water", "harbour|dock"), ("waterway", "dock"),
           ("railway", "station"), ("historic", "castle|monument"))
LIMIT = 2 * 1024 * 1024


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS landmark_pack(
        region TEXT PRIMARY KEY, collected INTEGER, source_url TEXT, payload BLOB)""")


def acquire(service, region):
    if region == "world":
        raise ValueError("Select a regional centre for the 8 km landmark extract.")
    _, lat, lon = providers.region(region)
    height = 8 / 111.2
    width = height / cos(radians(lat))
    bbox = f"{lat-height:.5f},{max(-180,lon-width):.5f},{lat+height:.5f},{min(180,lon+width):.5f}"
    filters = []
    for key, choices in FILTERS:
        if "|" in choices:
            filters.append(f'nwr["{key}"~"^({choices})$"]({bbox});')
        else:
            filters.append(f'nwr["{key}"="{choices}"]({bbox});')
    endpoints = [("overpass-api.de","meta"), ("overpass.private.coffee","meta")]
    if region == "aberdeen":
        # The regional server publishes current features without edit metadata.
        endpoints.insert(0, ("overpass.atownsend.org.uk","body"))
    for index,(host,detail) in enumerate(endpoints):
        query = "[out:json][timeout:25];(" + "".join(filters) + f");out {detail} center 3001;"
        url = "https://" + host + "/api/interpreter?" + urlencode({"data":query})
        try:
            payload = providers.fetch(url, LIMIT, timeout=42)
            parsed = json.loads(payload)
            if parsed.get("remark") or not isinstance(parsed.get("elements"),list):
                raise ValueError("The publisher returned an incomplete landmark extract.")
            break
        except (OSError,ValueError):
            if index == len(endpoints)-1:
                raise
    with closing(connect(service.path)) as db, db:
        db.execute("INSERT OR REPLACE INTO landmark_pack VALUES(?,?,?,?)",
                   (region, int(time.time()), url, payload))
        db.execute("""DELETE FROM landmark_pack WHERE region IN (
            SELECT region FROM landmark_pack ORDER BY collected DESC,rowid DESC LIMIT -1 OFFSET 12)""")


def search(service, region, clue, page=0):
    providers.region(region)
    if not 0 <= page <= 10000 or len(clue) > 180:
        raise ValueError("Invalid landmark query.")
    with closing(connect(service.path)) as db:
        pack = db.execute("SELECT * FROM landmark_pack WHERE region=?", (region,)).fetchone()
    if not pack:
        return dict(rows=[], count=0, acquired=None, more=False)
    payload = json.loads(pack["payload"])
    tokens = clue.casefold().replace("harbor","harbour").split()
    matches = []
    for feature in payload["elements"][:3000]:
        if feature.get("type") not in ("node","way","relation") or not isinstance(feature.get("id"),int):
            continue
        tags = feature.get("tags",{})
        coords = feature.get("center",feature)
        if "lat" not in coords or "lon" not in coords:
            continue
        kinds = [("harbour" if k=="harbour" else tags[k]) for k,choices in FILTERS
                 if k in tags and tags[k] in choices.split("|")]
        title = tags.get("name") or tags.get("ref") or ", ".join(kinds).title()
        searchable = " ".join([title,*kinds,*[str(v) for v in tags.values()]]).casefold().replace("harbor","harbour")
        if not all(token in searchable for token in tokens):
            continue
        key = f"{feature['type']}/{feature['id']}"
        matches.append(dict(key=key,title=title,kinds=kinds,lat=coords["lat"],lon=coords["lon"],
                            url="https://www.openstreetmap.org/"+key,edited=feature.get("timestamp"),
                            version=feature.get("version"),centre="center" in feature))
    matches.sort(key=lambda r:(r["title"].casefold(),r["key"]))
    return dict(rows=matches[page*25:(page+1)*25],count=len(matches),more=(page+1)*25<len(matches),
                acquired=pack["collected"],digest=sha256(pack["payload"]).hexdigest(),snapshot=payload.get("osm3s",{}).get("timestamp_osm_base"),
                capped=len(payload["elements"])>3000)
