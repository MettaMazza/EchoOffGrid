"""Regional public feeds. Coordinates are longitude, latitude throughout."""
from datetime import datetime, timezone
from gzip import GzipFile
from hashlib import sha256
from io import BytesIO
from math import cos, isfinite, radians
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re
import time
import zlib
import struct

# id, layer, publisher, coverage, minimum refresh interval, access, retention, publisher URL
SOURCES = {
    "air": ("Aircraft", "adsb.lol", "Worldwide receiver network", 300, "Public API", "ODbL 1.0", "https://www.adsb.lol/docs/open-data/api"),
    "ships": ("Vessels", "Fintraffic AIS", "Finnish waterways", 120, "Public API", "Fintraffic · CC BY 4.0", "https://www.digitraffic.fi/en/marine-traffic/"),
    "ais": ("Vessels", "AISStream", "Worldwide receiver network", 120, "Personal key", "Live display only", "https://aisstream.io/documentation"),
    "cams": ("Cameras", "Fintraffic road cameras", "Finland", 300, "Public API", "Fintraffic · CC BY 4.0", "https://www.digitraffic.fi/en/road-traffic/"),
    "scotland": ("Cameras", "Traffic Scotland", "Scotland", 0, "Official viewer", "Publisher link only", "https://www.traffic.gov.scot/traffic-information/traffic-cameras"),
    "maui": ("Cameras", "Charley Young Beach live camera", "Kihei, Maui", 0, "In-app live video", "Publisher player only", "https://www.mauirealestate.net/live/"),
    "nature": ("Cameras", "Explore live nature cameras", "Worldwide", 0, "Official viewer", "Publisher link only", "https://explore.org/livecams"),
    "orbit": ("Satellites", "CelesTrak", "Worldwide", 7200, "Public API", "Local orbital calculations", "https://celestrak.org/NORAD/documentation/gp-data-formats.php"),
    "imagery": ("Earth imagery", "NASA Worldview / GIBS", "Worldwide", 1800, "Public API", "NASA GIBS · MODIS / Terra", "https://www.earthdata.nasa.gov/data/tools/worldview"),
    "quakes": ("Hazards & sea", "USGS earthquakes", "Worldwide", 300, "Public API", "US Geological Survey", "https://earthquake.usgs.gov/earthquakes/feed/v1.0/index.php"),
    "buoys": ("Hazards & sea", "NOAA buoy observations", "Participating stations worldwide", 600, "Public API", "NOAA National Data Buoy Center", "https://www.ndbc.noaa.gov/"),
    "local": ("Local receiver", "Local receiver import", "Your receiving station", 0, "File import", "Local observation", ""),
}
REGIONS = {"world": ("World overview", 0, 0), "maui": ("Kihei, Maui", 20.72, -156.45), "aberdeen": ("Aberdeen & North Sea", 57.15, -2.10), "finland": ("Helsinki & Gulf of Finland", 60.17, 24.94)}
GIBS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
CAM_API = "https://tie.digitraffic.fi/api/weathercam/v1/stations"


def region(key):
    if key in REGIONS:
        return REGIONS[key]
    if not re.fullmatch(r"[-+]?\d{1,2}(?:\.\d{1,3})?,[-+]?\d{1,3}(?:\.\d{1,3})?",key):
        raise ValueError("Choose a region or enter latitude and longitude.")
    lat, lon = map(float,key.split(","))
    if abs(lat)>85 or abs(lon)>180:
        raise ValueError("Choose a map centre between 85° S and 85° N.")
    return f"{lat:.2f}°, {lon:.2f}°", lat, lon


def extent(key):
    if key=="world":return [-180,-85,180,85]
    _, lat, lon = region(key)
    width = min(35, 2.8/max(.1,cos(radians(lat))))
    return [max(-180,lon-width),max(-85,lat-2),min(180,lon+width),min(85,lat+2)]


def inside(bounds, lon, lat):
    return bounds[0]<=lon<=bounds[2] and bounds[1]<=lat<=bounds[3]


def fetch(url, limit=12_000_000):
    request = Request(url,headers={"User-Agent":"EchoOffGrid/OpenIntel","Accept-Encoding":"gzip","Digitraffic-User":"EchoOffGrid/OpenIntel"})
    with urlopen(request,timeout=12) as response:
        with GzipFile(fileobj=response) if response.headers.get("Content-Encoding")=="gzip" else response as stream:
            data=stream.read(limit+1)
        if len(data)>limit:
            raise ValueError("Publisher response exceeded local size limit")
        return data


def feed(url):
    return json.loads(fetch(url))


def utc(text):
    stamp=datetime.fromisoformat(text.rstrip("Z"))
    if stamp.tzinfo is None:
        stamp=stamp.replace(tzinfo=timezone.utc)
    return int(stamp.timestamp())


def observation(source, obj, title, lat, lon, stamp, detail, **extra):
    lat,lon=float(lat),float(lon)
    stamp=int(stamp)
    if not (-90<=lat<=90 and -180<=lon<=180 and 0<stamp<=time.time()+86400):
        raise ValueError("Invalid observation coordinates or time")
    obj=str(obj)[:96]
    uid=sha256(f"{source}|{obj}|{stamp}|{lat:.6f}|{lon:.6f}".encode()).hexdigest()
    return dict(id=uid, source=source, object=obj, title=str(title)[:180], lat=lat, lon=lon,
                time=stamp, detail=str(detail)[:1400], **extra)


def aircraft(key):
    _,lat,lon=region(key)
    data=feed(f"https://api.adsb.lol/v2/point/{lat}/{lon}/100")
    now=float(data["now"])
    if now>1e11:now/=1000
    for a in data["ac"]:
        if not all(k in a for k in ("hex","lat","lon","seen_pos")) or a.get("dbFlags",0)&1:
            continue
        yield observation("air",a["hex"],str(a.get("flight") or a.get("r") or a["hex"]).strip(),a["lat"],a["lon"],
                          now-a["seen_pos"],f'{a.get("t") or "Aircraft"} · altitude {a.get("alt_baro","unknown")} ft · ground speed {a.get("gs","unknown")} kt')


def finnish_ships(key):
    bounds=extent(key)
    for row in feed("https://meri.digitraffic.fi/api/ais/v1/locations")["features"]:
        lon,lat=row["geometry"]["coordinates"][:2]
        p=row["properties"]
        if inside(bounds,lon,lat) and p.get("timestampExternal"):
            yield observation("ships",p["mmsi"],f'Vessel {p["mmsi"]}',lat,lon,p["timestampExternal"]/1000,
                              f'Course {p.get("cog","unknown")}° · speed {p.get("sog","unknown")} kt')


def cameras(key):
    bounds=extent(key)
    _,lat,lon=region(key)
    nearby=[]
    for row in feed(CAM_API)["features"]:
        x,y=row["geometry"]["coordinates"][:2]
        if inside(bounds,x,y):
            nearby.append(((x-lon)**2*cos(radians(lat))**2+(y-lat)**2,row,x,y))
    updated={v["id"]:v for v in feed(CAM_API+"/data")["stations"]}
    for _,row,x,y in sorted(nearby,key=lambda v:v[0])[:12]:
        presets=updated.get(row["id"],{}).get("presets",[])
        if not presets:continue
        p=presets[0]
        if not re.fullmatch(r"C\d+",p["id"]) or not p.get("measuredTime"):continue
        yield observation("cams",p["id"],row["properties"]["name"].replace("_"," "),y,x,utc(p["measuredTime"]),
                          "Road-weather camera · still image",image_url=f'https://weathercam.digitraffic.fi/{p["id"]}.jpg?thumbnail=true')


def earthquakes(key):
    bounds=extent(key)
    for row in feed("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson")["features"]:
        x,y,depth=row["geometry"]["coordinates"]
        p=row["properties"]
        if inside(bounds,x,y):
            yield observation("quakes",row["id"],p["title"],y,x,p["time"]/1000,f"Depth {depth:g} km · {p.get('status','reported')}")


def buoys(key):
    bounds=extent(key)
    data=fetch("https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt").decode().splitlines()
    columns=data[0].strip("#").split()
    for line in data[2:]:
        p=dict(zip(columns,line.split()))
        x,y=float(p["LON"]),float(p["LAT"])
        if inside(bounds,x,y):
            stamp=datetime(*(int(p[k]) for k in ("YYYY","MM","DD","hh","mm")),tzinfo=timezone.utc)
            fields=[p[k]+" "+unit for k,unit in (("WSPD","m/s wind"),("WVHT","m waves"),("PRES","hPa")) if p[k]!="MM"]
            yield observation("buoys",p["STN"],"Station "+p["STN"],y,x,stamp.timestamp()," · ".join(fields) or "Station report")


def image_row(key,day):
    stamp=datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc)
    if stamp.date()>datetime.now(timezone.utc).date():raise ValueError("Choose today or an earlier imagery date.")
    name,lat,lon=region(key)
    box=extent(key)
    query=urlencode(dict(SERVICE="WMS",REQUEST="GetMap",VERSION="1.1.1",LAYERS="MODIS_Terra_CorrectedReflectance_TrueColor",
                         STYLES="",SRS="EPSG:4326",BBOX=",".join(map(str,box)),WIDTH=768,HEIGHT=512,FORMAT="image/png",TRANSPARENT="TRUE",TIME=day))
    return observation("imagery",key+"-"+day,name+" · "+day,lat,lon,stamp.timestamp(),
                       "Terra MODIS true colour · daily composite. Clouds, darkness and missing swaths affect coverage.",
                       image_url=GIBS+"?"+query,bounds=box)


def available_image(data):
    """A transparent GIBS tile contains zero alpha throughout, including filtered rows."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data)<33:
        return False
    width,height,depth,kind,_,_,interlace=struct.unpack(">IIBBBBB",data[16:29])
    if (width,height,depth,kind,interlace)!=(768,512,8,6,0):
        return False
    parts=[]
    pos=8
    while pos+12<=len(data):
        length=int.from_bytes(data[pos:pos+4],"big")
        if pos+12+length>len(data):return False
        if data[pos+4:pos+8]==b"IDAT":parts.append(data[pos+8:pos+8+length])
        pos+=12+length
    stride=width*4+1
    raw=zlib.decompressobj().decompress(b"".join(parts),height*stride+1)
    if len(raw)!=height*stride:return False
    # Until the first nonzero alpha, every PNG filter predicts zero for alpha.
    return any(any(raw[i+4:i+stride:4]) for i in range(0,len(raw),stride))


def ais_live(key,token):
    from websockets.sync.client import connect
    w,s,e,n=extent(key)
    started=time.monotonic()
    stream=connect("wss://stream.aisstream.io/v0/stream",open_timeout=8,close_timeout=1,max_size=65536)
    try:
        stream.send(json.dumps({"APIKey":token,"BoundingBoxes":[[[s,w],[n,e]]],"FilterMessageTypes":["PositionReport"]}))
        while time.monotonic()-started<15:
            try: msg=json.loads(stream.recv(timeout=max(.2,15-(time.monotonic()-started))))
            except TimeoutError:break
            if msg.get("error") or msg.get("Error"):raise ValueError("AISStream rejected the subscription")
            p=msg.get("MetaData") or {}
            report=msg.get("Message",{}).get("PositionReport",{})
            if p.get("MMSI") and report:
                stamp=str(p["time_utc"]).split(" +")[0].replace(" ","T")
                yield observation("ais",p["MMSI"],p.get("ShipName","").strip() or str(p["MMSI"]),
                                  p["latitude"],p["longitude"],utc(stamp),f'Speed {report.get("Sog","unknown")} kt · course {report.get("Cog","unknown")}°')
    finally:stream.close()
