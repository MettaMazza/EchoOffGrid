"""Build the portable visual directory from publisher-issued public camera catalogues."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import json
import re

from . import providers as p


def public_url(value, hosts):
    u=urlsplit(value or '')
    return value if u.scheme=='https' and u.hostname in hosts and not u.username and not u.password else ''


def item(key,title,area,publisher,kind,image='',video='',lat=None,lon=None):
    return dict(id=key,title=title,area=area,publisher=publisher,kind=kind,image=image,video=video,lat=lat,lon=lon)


def london():
    for site in p.feed('https://api.tfl.gov.uk/Place/Type/JamCam'):
        meta={v['key']:v['value'] for v in site['additionalProperties']}
        if meta.get('available')!='true':continue
        hosts={'s3-eu-west-1.amazonaws.com','jamcams.tfl.gov.uk'}
        image=public_url(meta.get('imageUrl'),hosts)
        video=public_url(meta.get('videoUrl'),hosts)
        if image:yield item(site['id'],site['commonName'],'London, UK','Transport for London','Camera clip' if video else 'Camera still',image,video,site['lat'],site['lon'])


def california(district):
    for row in p.feed(f'https://cwwp2.dot.ca.gov/data/d{district}/cctv/cctvStatusD{district:02}.json')['data']:
        c=row['cctv'];loc=c['location'];media=c['imageData']
        if str(c.get('inService')).lower()!='true':continue
        image=public_url(media['static'].get('currentImageURL'),{'cwwp2.dot.ca.gov'})
        video=public_url(media.get('streamingVideoURL'),{'wzmedia.dot.ca.gov'})
        if image:
            yield item(f"ca-{district}-{c['index']}",loc['locationName'],loc['nearbyPlace']+', California','Caltrans','Live video' if video else 'Camera still',image,video,float(loc['latitude']),float(loc['longitude']))


def finland():
    sites=p.feed(p.CAM_API)['features']
    status=p.feed(p.CAM_API+'/data')['stations']
    presets={s['id']:s.get('presets',[]) for s in status}
    for site in sites:
        x,y=site['geometry']['coordinates'][:2]
        for preset in presets.get(site['id'],[]):
            code=preset['id']
            if re.fullmatch(r'C\d+',code) and preset.get('measuredTime'):
                yield item('fi-'+code,site['properties']['name'].replace('_',' ')+' · '+code,'Finland','Fintraffic / Digitraffic','Camera still','https://weathercam.digitraffic.fi/'+code+'.jpg',lat=y,lon=x)


def main():
    tasks=[('London',london),('Finland',finland)]+[(f'Caltrans {i}',lambda d=i:california(d)) for i in range(1,13)]
    def load(task):
        name,fn=task
        try:
            result=list(fn());print(name,len(result),flush=True);return result
        except Exception as err:print(name,type(err).__name__,str(err),flush=True);return []
    with ThreadPoolExecutor(3) as pool: rows=[r for batch in pool.map(load,tasks) for r in batch]
    if not all(any(r['publisher']==name for r in rows) for name in ('Transport for London','Fintraffic / Digitraffic','Caltrans')):
        raise SystemExit('A required source is unavailable; kept the existing directory')
    path=Path(__file__).with_name('visual-directory.json')
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'checked':datetime.now(timezone.utc).date().isoformat(),'rows':rows},ensure_ascii=False,separators=(',',':')))
    tmp.replace(path)

if __name__=='__main__':main()
