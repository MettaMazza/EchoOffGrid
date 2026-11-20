"""Official records catalogue. Search pages and acquired documents persist separately."""
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
from itertools import zip_longest
import http.client
import json
import shutil

import discovery
import govports

ACT = "https://www.govinfo.gov/content/pkg/STATUTE-55/pdf/STATUTE-55-Pg31.pdf"
FEATURED = [
    ("Lend-Lease Act", "US Government Publishing Office", "War history · 1941 · 55 Stat. 31. The enacted law from the Statutes at Large.", ACT),
    ("Project Blue Book records transfer", "US National Archives", "UFO records · Air Force documentation of the transfer of its investigation files.", "https://prologue.blogs.archives.gov/wp-content/uploads/sites/9/2018/03/report.pdf"),
    ("Unidentified Anomalous Phenomena Independent Study", "NASA", "UFO and UAP research · September 2023 · Final report.", "https://www.nasa.gov/wp-content/uploads/2023/09/uap-independent-study-team-final-report-0.pdf"),
    ("Jeffrey Epstein case files · Part 01", "FBI Vault", "FOIA release · The first 44-page PDF in the FBI’s published case-file series.", "https://vault.fbi.gov/jeffrey-epstein/Jeffrey%20Epstein%20Part%2001/at_download/file"),
    ("Jeffrey Epstein in federal custody", "US Department of Justice, Office of the Inspector General", "Oversight · June 2023 · Investigation of custody, care and supervision. Report 23-085.", "https://oig.justice.gov/sites/default/files/reports/23-085.pdf"),
    ("Epstein Files Transparency Act", "US Government Publishing Office", "Disclosure · 2025 · Public Law 119–38 sets out the release requirements.", "https://www.govinfo.gov/content/pkg/PLAW-119publ38/pdf/PLAW-119publ38.pdf"),
    ("U-2 and OXCART programs, 1954–1974", "US National Archives", "Declassified CIA history of Cold War aerial reconnaissance.", "https://www.archives.gov/files/declassification/iscap/pdf/2014-004-doc01.pdf"),
]
PROVIDERS = {"all":"All connected catalogues","world":"World Bank Documents & Reports · worldwide","local":"On this device", "uk":"GOV.UK statements", "us":"US Federal Register"}
UK = "https://www.gov.uk"
LIMIT = 16


def record(title, agency, description, url, ext=".pdf"):
    return dict(id=sha256(url.encode()).hexdigest(), kind="Documents", title=title,
                preview=description or "", rights=agency+" · Official publication · "+url,
                url=url, ext=ext, provider=agency)


def seed(db, folder):
    records = [record(*entry) for entry in FEATURED]
    discovery.remember(db,"Documents","featured",1,records,False)
    item = records[0]
    target = folder/"Content"/(item["id"]+".pdf")
    if not target.is_file():
        target.parent.mkdir(exist_ok=True)
        tmp = target.with_suffix(".seed")
        shutil.copyfile(Path(__file__).with_name("lend-lease-1941.pdf"), tmp)
        tmp.replace(target)
    db.execute("UPDATE discovery_item SET filename=? WHERE id=?", (target.name,item["id"]))


def get_json(url):
    with urlopen(Request(url, headers={"User-Agent":"EchoOffGrid/1.0","Accept":"application/json"}),timeout=12) as response:
        data = response.read(8*1024*1024+1)
    if len(data)>8*1024*1024:
        raise ValueError("Publication exceeds the text reader limit")
    return json.loads(data)


def lookup(source, query, page):
    if source=="world":
        args={"format":"json","rows":LIMIT,"os":(page-1)*LIMIT,"fl":"display_title,pdfurl,docdt,repnb"}
        if query:args["qterm"]=query
        data=get_json("https://search.worldbank.org/api/v3/wds?"+urlencode(args))
        entries=[]
        for key,r in data.get("documents",{}).items():
            if key=="facets" or not isinstance(r,dict):continue
            url=(r.get("pdfurl") or "").replace("http://","https://",1)
            if urlsplit(url).hostname not in {"documents.worldbank.org","documents1.worldbank.org","documents.worldbank.org.edgesuite.net"}:continue
            entries.append(record(r["display_title"],"World Bank Documents & Reports",str(r.get("docdt",""))[:10]+" · "+str(r.get("repnb") or key),url))
        return entries,page*LIMIT<int(data["total"])
    if source=="uk":
        filters = [("filter_format",v) for v in ("speech","news_story","government_response","press_release","oral_statement","written_statement")]
        data=get_json(UK+"/api/search.json?"+urlencode(filters+[("q",query),("start",(page-1)*LIMIT),("count",LIMIT)]))
        entries=[record(r["title"],"GOV.UK",r.get("description",""),UK+r["link"],".txt")
                 for r in data["results"] if r.get("link","").startswith("/") and not r["link"].startswith("//")]
        return entries,page*LIMIT<data["total"]
    data=get_json("https://www.federalregister.gov/api/v1/documents.json?"+urlencode({"conditions[term]":query,"page":page,"per_page":LIMIT}))
    entries=[]
    for r in data["results"]:
        url=r.get("pdf_url") or ""
        if urlsplit(url).scheme=="https" and urlsplit(url).hostname in {"www.govinfo.gov","govinfo.gov","public-inspection.federalregister.gov"}:
            agency=", ".join(a["name"] for a in r.get("agencies",[]) if a.get("name")) or "Federal Register"
            entries.append(record(r["title"],agency,r.get("publication_date","")+" · "+(r.get("abstract") or r.get("type",""))[:280],url))
    return entries,page<data["total_pages"]


class StatementText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in {"p","h2","h3","li","br","blockquote"}:
            self.parts.append("\n\n")
    def handle_data(self,data):
        self.parts.append(data)


def save_statement(item,target,progress):
    country=govports.country_for(item)
    if country:
        with govports.fetch(country,item["url"]) as response:
            if response.headers.get_content_type() not in {"text/html","application/xhtml+xml"}:
                raise ValueError("The publisher changed the document format.")
            page=govports.parse_html(response)
        text="\n".join(" ".join(s.split()) for s in "".join(page.words).splitlines() if s.strip())
        if not text:raise ValueError("The official website requires a browser to display its text.")
        return write_text(item,target,progress,text)
    location=urlsplit(item["url"])
    if location.scheme!="https" or location.netloc!="www.gov.uk":
        raise ValueError("Unknown statement publisher")
    details=get_json(UK+"/api/content"+location.path)["details"]
    body=details.get("body") or details.get("delivered_on_detail")
    if not isinstance(body,str) or not body.strip():
        raise ValueError("The publisher has no downloadable statement text for this record")
    parser=StatementText()
    parser.feed(body)
    text="\n\n".join(" ".join(s.split()) for s in "".join(parser.parts).split("\n\n") if s.strip())
    if not text:
        raise ValueError("The statement text is empty")
    write_text(item,target,progress,text)


def write_text(item,target,progress,text):
    payload=(item["title"]+"\n"+item["url"]+"\n\n"+text).encode()
    partial=target.with_suffix(".txt.part")
    try:
        partial.write_bytes(payload)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    progress(len(payload),len(payload))


def screen(db,params,token,corpo=None):
    providers=corpo.PROVIDERS if corpo else PROVIDERS
    base="/opencorpo" if corpo else "/opengov"
    local_scope="rights LIKE 'OpenCorpo ·%'" if corpo else "rights NOT LIKE 'OpenCorpo ·%'"
    fetch_records=corpo.lookup if corpo else lookup
    query=params.get("q",[""])[0].strip()[:160]
    source=params.get("source",["all"])[0]
    if source not in providers:
        source="local"
    number=params.get("page",["1"])[0]
    page=int(number) if number.isascii() and number.isdigit() and 0<len(number)<=4 else 1
    page=max(1,page)
    options="".join(f'<option value="{k}" {"selected" if k==source else ""}>{v}</option>' for k,v in providers.items())
    form=f'<form class="gov-search"><label>Catalogue <select name=source>{options}</select></label><label>Keywords <input type=search name=q value="{escape(query)}" placeholder="Agency, title or topic"></label><button>Search records</button></form>'
    country=params.get("country",[""])[0]
    directory=(corpo.directory if corpo else govports.directory)(country,params.get("siteq",[""])[0][:200])
    if country in (corpo.PORTALS if corpo else govports.COUNTRIES) and "source" not in params:return directory
    notice=""
    if source=="local":
        pattern="%"+query+"%"
        rows=list(db.execute(f"""SELECT * FROM discovery_item WHERE {local_scope} AND kind='Documents' AND (title LIKE ? OR preview LIKE ? OR provider LIKE ?) ORDER BY title,id LIMIT ? OFFSET ?""",(pattern,pattern,pattern,LIMIT+1,(page-1)*LIMIT)))
        more=len(rows)>LIMIT
        rows=rows[:LIMIT]
    else:
        sources=tuple(k for k in providers if k not in ("all","local")) if source=="all" else (source,)
        groups=[]
        unavailable=[]
        more=False
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            searches={name:pool.submit(fetch_records,name,query,page) for name in sources}
            for name,search in searches.items():
                cache=("corpo " if corpo else "")+name+" "+query
                try:
                    entries,has_next=search.result()
                    discovery.remember(db,"Documents",cache,page,entries,has_next)
                except (OSError,ValueError,KeyError,http.client.HTTPException):
                    unavailable.append(providers[name])
                cached=db.execute("SELECT items,more FROM discovery_page WHERE kind='Documents' AND query=? AND page=?",(cache,page)).fetchone()
                if cached:
                    groups.append(json.loads(cached["items"]))
                    more=more or bool(cached["more"])
        ids=dict.fromkeys(key for group in zip_longest(*groups) for key in group if key)
        rows=[db.execute("SELECT * FROM discovery_item WHERE id=?",(key,)).fetchone() for key in ids]
        if unavailable:notice="Unavailable during this search: "+", ".join(unavailable)+". Previously fetched results are included when available."
        if not rows and unavailable and page==1:
            rows=db.execute(f"SELECT * FROM discovery_item WHERE {local_scope} AND kind='Documents' AND (title LIKE ? OR preview LIKE ?) ORDER BY filename IS NULL,title LIMIT ?",("%"+query+"%","%"+query+"%",LIMIT)).fetchall()
    cards=[]
    for r in filter(None,rows):
        action=(f'<a href="/content/{r["id"]}">Read offline →</a>' if r["filename"] else
                f'<form method=post action="/discover/add"><input type=hidden name=token value="{token}"><input type=hidden name=item value="{r["id"]}"><button>Save to Documents</button></form>')
        cards.append(f'<article class="gov-card"><small>{escape(r["provider"])} · {escape(r["ext"].lstrip(".").upper())}</small><h3>{escape(r["title"])}</h3><p>{escape(r["preview"])}</p>{action}</article>')
    pagination=" ".join(f'<a href="{base}?{escape(urlencode(dict(source=source,q=query,page=n)))}">{label}</a>'
                        for n,label in ((page-1,"Previous"),(page+1,"Next")) if (n<page and n>0) or (n>page and more))
    introduction="Explore company registrations, funds, foundation filings and royal accounts." if corpo else "Explore government statements, declassified records and original publications."
    return (directory+f'<div class=section-head><p>{introduction}</p><a href="/library/documents">Your Documents →</a></div>'+form+
            f'<p role=status>{escape(notice)}</p><div class="gov-grid">'+("".join(cards) or "<p>No matching records.</p>")+f'</div><nav class=pills>{pagination}</nav>')
