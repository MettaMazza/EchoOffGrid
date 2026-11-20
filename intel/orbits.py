"""Local SGP4 ground positions and geometric passes above an observer."""
from functools import lru_cache
from math import atan2, cos, degrees, hypot, radians, sin, sqrt
import json

from sgp4.api import Satrec
from sgp4.omm import initialize
from sgp4.propagation import gstime

from .providers import region, utc


@lru_cache(maxsize=48)
def satellite(elements):
    model=Satrec()
    initialize(model,json.loads(elements))
    return model


def earth_fixed(model, stamp):
    day, fraction=divmod(stamp,86400)
    jd=2440587.5+day
    code,xyz,_=model.sgp4(jd,fraction/86400)
    if code:raise ValueError("Orbital elements cannot produce a valid position")
    a=gstime(jd+fraction/86400)
    x,y,z=xyz
    return x*cos(a)+y*sin(a), -x*sin(a)+y*cos(a), z


def location(model, stamp):
    x,y,z=earth_fixed(model,stamp)
    radius=hypot(x,y)
    lat=atan2(z,radius)
    for _ in range(4):
        n=6378.137/sqrt(1-0.00669438*sin(lat)**2)
        lat=atan2(z+0.00669438*n*sin(lat),radius)
    return degrees(lat),degrees(atan2(y,x))


@lru_cache(maxsize=128)
def pass_window(elements,key,start):
    model=satellite(elements)
    _,lat,lon=region(key)
    lat,lon=radians(lat),radians(lon)
    ux,uy,uz=cos(lat)*cos(lon),cos(lat)*sin(lon),sin(lat)
    n=6378.137/sqrt(1-.00669438*uz**2)
    ox,oy,oz=n*ux,n*uy,n*(1-.00669438)*uz
    first=None
    peak=0
    for stamp in range(start,start+36*3600,60):
        x,y,z=earth_fixed(model,stamp)
        x,y,z=x-ox,y-oy,z-oz
        up=x*ux+y*uy+z*uz
        elevation=degrees(atan2(up,sqrt(max(0,x*x+y*y+z*z-up*up))))
        if elevation>=10:
            first=stamp if first is None else first
            peak=max(elevation,peak)
        elif first is not None:
            return {"start":first,"end":stamp,"peak":round(peak)}
    return None


def predict(rows,key,stamp):
    result=[]
    for element in rows:
        epoch=utc(element["EPOCH"])
        if abs(stamp-epoch)>14*86400:continue
        raw=json.dumps(element,sort_keys=True)
        model=satellite(raw)
        lat,lon=location(model,stamp)
        trail=[list(reversed(location(model,t))) for t in range(stamp-1800,stamp+3601,120)]
        result.append(dict(id="orbit-"+str(element["NORAD_CAT_ID"]), object=str(element["NORAD_CAT_ID"]),
                           source="orbit",title=element["OBJECT_NAME"],lat=lat,lon=lon,time=stamp,epoch=epoch,
                           detail="SGP4 predicted ground position · geometric passes above 10° elevation",
                           trail=trail,window=pass_window(raw,key,stamp//300*300)))
    return result

@lru_cache(maxsize=1)
def directory():
    from pathlib import Path
    records=json.loads(Path(__file__).with_name("orbit-directory.json").read_text())["rows"]
    return {str(r["NORAD_CAT_ID"]):r for r in records}

def selected_prediction(service,key,number,refresh=False):
    from contextlib import closing
    import time
    from . import providers
    from .service import connect
    known=directory().get(number)
    if not known:raise ValueError("Unknown satellite catalogue number")
    now=int(time.time())
    with closing(connect(service.path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS orbit_choice(number TEXT PRIMARY KEY,requested INTEGER,body TEXT)")
        cached=db.execute("SELECT requested,body FROM orbit_choice WHERE number=?",(number,)).fetchone()
        if refresh and (not cached or now-cached[0]>=7200):
            # Claim the fetch before opening the connection so repeated taps share the cooldown.
            with db:
                reserved=db.execute("""INSERT INTO orbit_choice VALUES(?,?,NULL) ON CONFLICT(number) DO UPDATE SET requested=excluded.requested
                    WHERE requested<=?""",(number,now,now-7200)).rowcount
            if reserved:
                try:
                    batch=providers.feed("https://celestrak.org/NORAD/elements/gp.php?CATNR="+number+"&FORMAT=JSON")
                    found=next((r for r in batch if str(r.get("NORAD_CAT_ID"))==number),None)
                    if not found:raise ValueError("No updated elements available")
                except (OSError,KeyError,TypeError) as err:raise ValueError("CelesTrak is unavailable. The bundled elements remain available.") from err
                with db:db.execute("UPDATE orbit_choice SET body=? WHERE number=?",(json.dumps(found),number))
                known=found
        elif cached and cached[1]:known=json.loads(cached[1])
    rows=predict([known],key,now)
    if not rows:raise ValueError("Orbital elements are too old for a current prediction. Refresh this satellite while connected.")
    return rows[0]
