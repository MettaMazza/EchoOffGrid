"""Public visual sources, bundled dated examples and a searchable camera directory."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode
import json
import re
from . import providers as p
from .visual_catalogue import item

ROOT=Path(__file__).resolve().parent
SAT='Satellite image'
PUBLISHERS={
    'Transport for London':'https://tfl.gov.uk/info-for/open-data-users/our-open-data',
    'Caltrans':'https://cwwp2.dot.ca.gov/tools/cctv.html',
    'Fintraffic / Digitraffic':'https://www.digitraffic.fi/en/road-traffic/',
    'USGS Hawaiian Volcano Observatory':'https://www.usgs.gov/observatories/hvo/webcams',
    'NOAA / NESDIS / STAR':'https://www.star.nesdis.noaa.gov/GOES/',
    'NASA GIBS':'https://worldview.earthdata.nasa.gov/',
    'Maui Real Estate':'https://www.mauirealestate.net/live/',
    'Seacroft Marine Consultants':'https://www.seacroftmarine.com/webcams/',
    'Traffic Scotland':'https://www.traffic.gov.scot/traffic-cameras',
    'Australian Antarctic Program':'https://www.antarctica.gov.au/antarctic-operations/webcams/',
}
SENSORS={'terra':'MODIS_Terra_CorrectedReflectance_TrueColor','aqua':'MODIS_Aqua_CorrectedReflectance_TrueColor','noaa20':'VIIRS_NOAA20_CorrectedReflectance_TrueColor'}

def satellite_image(sensor,region,day):
    # GIBS composites are indexed by UTC acquisition day.
    stamp=datetime.strptime(day,'%Y-%m-%d').date()
    if stamp>datetime.now(timezone.utc).date():raise ValueError('Choose today or an earlier date')
    from math import radians,log,tan,pi
    w,s,e,n=p.extent(region)
    northing=lambda lat:6378137*log(tan(pi/4+radians(lat)/2))
    bounds=[6378137*radians(w),northing(s),6378137*radians(e),northing(n)]
    query=urlencode(dict(SERVICE='WMS',REQUEST='GetMap',VERSION='1.1.1',LAYERS=SENSORS[sensor],STYLES='',SRS='EPSG:3857',BBOX=','.join(map(str,bounds)),WIDTH=768,HEIGHT=512,FORMAT='image/png',TRANSPARENT='TRUE',TIME=day))
    return p.GIBS.replace('epsg4326','epsg3857')+'?'+query

@lru_cache(maxsize=1)
def directory():
    data=json.loads((ROOT/'visual-directory.json').read_text())
    return data['checked'],data['rows']

def featured_items(region,day):
    name,_,_=p.region(region)
    featured=[item('terra','Terra · MODIS',name,'NASA GIBS',SAT,satellite_image('terra',region,day)),
              item('crater','Kīlauea summit crater','Hawaiʻi, US','USGS Hawaiian Volcano Observatory','Camera still','https://volcanoes.usgs.gov/cams/KWcam/images/M.jpg',lat=19.406,lon=-155.283),
              item('east','GOES-East · GeoColor','Americas and Atlantic','NOAA / NESDIS / STAR',SAT,'https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD/GEOCOLOR/678x678.jpg'),
              item('maui','Charley Young Beach','Kihei, Hawaiʻi','Maui Real Estate','Live video',video='/openintel/camera'),
              item('west','GOES-West · GeoColor','Pacific Ocean','NOAA / NESDIS / STAR',SAT,'https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/GEOCOLOR/678x678.jpg'),
              item('aqua','Aqua · MODIS',name,'NASA GIBS',SAT,satellite_image('aqua',region,day)),
              item('noaa20','NOAA-20 · VIIRS',name,'NASA GIBS',SAT,satellite_image('noaa20',region,day)),
              item('scotland','Traffic Scotland camera network','Scotland, UK','Traffic Scotland','Publisher viewer',video=PUBLISHERS['Traffic Scotland'])]
    for direction,subject in [('north','Aberdeen Beach and bay'),('east','Harbour entrance'),('south','Main navigation channel'),('west','Harbour turning basin')]:
        website=f'https://www.seacroftmarine.com/webcams/{direction}-webcam/'
        entry=item('aberdeen-'+direction,subject,'Aberdeen, Scotland','Seacroft Marine Consultants','Publisher viewer',video=website)
        if region=='aberdeen' and direction=='north':featured.insert(1,entry)
        else:featured.append(entry)
    for place in ('mawson','casey','davis'):
        featured.append(item('antarctic-'+place,place.title()+' research station','Antarctica','Australian Antarctic Program','Camera still','https://www.antarctica.gov.au/antarctic-operations/webcams/'+place+'/'))
    return featured

def list_items(region,day,kind,query,provider,page):
    groups={'video':{'Camera clip','Live video'},'still':{'Camera still'},'viewers':{'Publisher viewer'},'space':{SAT}}
    groups['cameras']=groups['video'] | groups['still'] | groups['viewers']
    if kind!='all' and kind not in groups:raise ValueError('Unknown collection')
    checked,cameras=directory()
    featured=featured_items(region,day)
    representatives=[next((r for r in cameras if r['publisher']==name),None) for name in ('Transport for London','Caltrans','Fintraffic / Digitraffic')]
    featured[3:3]=[r for r in representatives if r]
    primary={r['id'] for r in featured}
    pool=featured+[r for r in cameras if r['id'] not in primary]
    words=query.casefold().split()
    filtered=[r for r in pool if (kind=='all' or r['kind'] in groups[kind]) and (not provider or r['publisher']==provider)
              and all(w in (' '.join((r['title'],r['area'],r['publisher'],r['kind']))).casefold() for w in words)]
    size=8
    page=min(max(0,page),max(0,(len(filtered)-1)//size))
    rows=[]
    for r in filtered[page*size:(page+1)*size]:
        row=dict(r,url=PUBLISHERS[r['publisher']])
        if r['id'] in ('crater','east','west','terra'):
            row['poster']='/openintel/poster/'+r['id']
            example=json.loads((ROOT/'previews/sources.json').read_text())[r['id']]
            row['example']='Example · '+example['region']+' · '+(example['composite_day'] or example['retrieved'][:10])
        rows.append(row)
    return dict(rows=rows,count=len(filtered),page=page,pages=(len(filtered)+size-1)//size,checked=checked,
                publishers=sorted({r['publisher'] for r in pool if kind=='all' or r['kind'] in groups[kind]}))

def response(params):
    def first(k,default=''):return params.get(k,[default])[0]
    yesterday=(datetime.now(timezone.utc)-timedelta(days=1)).date().isoformat()
    return list_items(first('region','aberdeen'),first('day',yesterday),first('kind','all'),first('q')[:140],first('publisher'),int(first('page','0')))

@lru_cache(maxsize=1)
def camera_index():
    return {r['id']:r for r in directory()[1]}

def resolve(key,region,day):
    camera=camera_index().get(key)
    if camera:return camera
    for row in featured_items(region,day):
        if row['id']==key:return row
    raise ValueError('Unknown visual source')

def collect(service,key,region,day):
    from email.utils import parsedate_to_datetime
    from hashlib import sha256
    from urllib.request import Request,urlopen
    import time
    data=resolve(key,region,day)
    remote=data['image']
    if key.startswith("antarctic-"):
        place=key.split("-")[1]
        markup=p.fetch(remote,1024**2).decode()
        match=re.search(r'https://images\.antarctica\.gov\.au/webcams/'+place+r'/[0-9/]+/[A-Z0-9]+s\.jpg',markup)
        if not match:raise ValueError("The station has not published an image")
        remote=match[0]
    if not remote:raise ValueError('Use the publisher player for this camera')
    # All URLs originate in the shipped publisher catalogue or fixed NASA query builder.
    with urlopen(Request(remote,headers={'User-Agent':'EchoOffGrid/OpenIntel'}),timeout=12) as reply:
        body=reply.read(5*1024*1024+1)
        modified=reply.headers.get('Last-Modified')
    if len(body)>5*1024*1024 or not (body.startswith(b'\xff\xd8\xff') or body.startswith(b'\x89PNG\r\n\x1a\n')):
        raise ValueError('Publisher did not supply a supported image')
    now=int(time.time())
    file_time=int(parsedate_to_datetime(modified).timestamp()) if modified else None
    image_digest=sha256(body).hexdigest()
    stamp=now
    meta={'received':now,'modified':file_time,'digest':image_digest,'url':remote}
    if key in SENSORS:
        if not p.available_image(body):raise ValueError('No imagery for this date and region')
        stamp=p.utc(day+'T00:00:00Z')
    if key in SENSORS or data['publisher'] in ('NOAA / NESDIS / STAR','USGS Hawaiian Volcano Observatory','Fintraffic / Digitraffic'):
        _,lat,lon=p.region(region)
        if data['lat'] is not None:lat,lon=data['lat'],data['lon']
        row=p.observation('imagery' if key in SENSORS else 'earth-frame' if key in ('east','west') else 'visual',key,data['title'],lat,lon,stamp,
            data['publisher']+' · '+data['kind'],retrieval_url=remote,payload_sha256=image_digest,
            time_basis='Composite day' if key in SENSORS else 'Retrieved',publisher=data['publisher'])
        if key in SENSORS:row['bounds']=p.extent(region)
        if key in ('east','west'):row['no_map_point']=True
        row['id']=sha256((row['id']+image_digest).encode()).hexdigest()
        service.store(region,row,body)
        from .service import connect
        from contextlib import closing
        with closing(connect(service.path)) as db,db:service.trim(db)
        meta.update(id=row['id'],image='/openintel/image/'+row['id'])
        if key in SENSORS:meta['bounds']=row['bounds']
    else:
        with service.lock:
            # Camera providers with unspecified archival terms remain preview-only.
            service.preview_frames[image_digest]=body
            while sum(map(len,service.preview_frames.values()))>12*1024*1024:
                del service.preview_frames[next(iter(service.preview_frames))]
        meta['image']='/openintel/frame/'+image_digest
    return meta
