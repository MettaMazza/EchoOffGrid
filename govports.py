"""Browse the UN DESA national portals directory and acquire linked publications."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin, urlencode, urldefrag
from urllib.request import HTTPRedirectHandler, Request, build_opener
import json

COUNTRIES=json.loads(Path(__file__).with_name("government-portals.json").read_text())
EXTRA={"State of Palestine":"https://www.pmo.pna.ps","Holy See":"https://www.vatican.va","Taiwan":"https://www.taiwan.gov.tw","Kosovo":"https://www.rks-gov.net"}
for code,name in (("PSE","State of Palestine"),("VAT","Holy See"),("TWN","Taiwan"),("XKX","Kosovo")):
    COUNTRIES.setdefault(code,{"name":name,"region":"Europe" if code in {"VAT","XKX"} else "Asia","sites":[]})
    if not COUNTRIES[code]["sites"]:
        COUNTRIES[code]["sites"].append(EXTRA[name])


def allowed(country,url):
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.username or parts.password or parts.netloc!=parts.hostname:
        return False
    host=parts.hostname or ""
    for site in country["sites"]:
        root=urlsplit(site).hostname.removeprefix("www.")
        if host==root or host=="www."+root or (not country.get("exact_hosts") and host.endswith("."+root)):
            return True
    return False


def fetch(country,url):
    if not allowed(country,url):
        raise ValueError("Choose a link on this government portal.")
    class OfficialRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not allowed(country,newurl):
                raise ValueError("The publisher moved this page to another website. Open its official site to continue.")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    return build_opener(OfficialRedirect()).open(Request(url,headers={"User-Agent":"EchoOffGrid/1.0"}),timeout=10)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links={}
        self.words=[]
        self.title=[]
        self.in_title=False
        self.link=None
        self.hidden=0

    def handle_starttag(self,tag,attrs):
        if tag in {"script","style","noscript","svg"}: self.hidden+=1
        if self.hidden:return
        if tag=="title":self.in_title=True
        if tag=="a":self.link=dict(attrs).get("href")
        if tag in {"p","li","h1","h2","h3","br","section"}: self.words.append("\n")

    def handle_data(self,data):
        if self.hidden:return
        self.words.append(data)
        if self.in_title:self.title.append(data)
        if self.link:self.links[self.link]=self.links.get(self.link,"")+" "+data.strip()

    def handle_endtag(self,tag):
        if tag in {"script","style","noscript","svg"}: self.hidden=max(0,self.hidden-1)
        if tag=="title":self.in_title=False
        if tag=="a":self.link=None

def parse_html(response):
    data=response.read(4*1024*1024+1)
    if len(data)>4*1024*1024:raise ValueError("Page exceeds reader size.")
    page=Page()
    page.feed(data.decode(response.headers.get_content_charset() or "utf-8","replace"))
    return page


def route(code,url,base="/opengov"):
    return base+"/portal?"+urlencode({"country":code,"url":url})


def directory(code,query):
    country=COUNTRIES.get(code)
    options="".join(f'<option value="{k}" {"selected" if k==code else ""}>{escape(c["name"])}</option>'
                    for k,c in sorted(COUNTRIES.items(),key=lambda kv:kv[1]["name"]))
    form=f'<section class="gov-directory"><h3>National archives and government portals</h3><form class=gov-search><label>Country or territory<select name=country><option value="">Choose a jurisdiction</option>{options}</select></label><button>Browse government</button></form>'
    if not country:
        return form+f'<p>{len(COUNTRIES)} jurisdictions · National portals and public data catalogues</p><nav class=pills><a href="https://digitallibrary.un.org/">UN Digital Library ↗</a><a href="https://www.fao.org/faolex/en/">FAOLEX national legislation ↗</a><a href="https://eur-lex.europa.eu/">EUR-Lex ↗</a><a href="https://www.wipo.int/wipolex/en/">WIPO Lex ↗</a></nav></section>'
    links=[]
    for site in country["sites"]:
        host=urlsplit(site).hostname
        links.append(f'<a href="{escape(route(code,site))}">{escape(host)} →</a>')
    search="https://www.google.com/search?"+urlencode({"q":"("+ " OR ".join("site:"+urlsplit(s).hostname.removeprefix("www.") for s in country["sites"])+") "+query})
    return (form+f'<h3>{escape(country["name"])}</h3><nav class=pills>{" ".join(links)}</nav>'
            f'<form class=gov-search action="/opengov/portal"><input type=hidden name=country value="{code}"><label>Publication URL<input type=url name=url placeholder="https://" required></label><button>Preview and save</button></form>'
            f'<form class=gov-search><input type=hidden name=country value="{code}"><label>Search these official sites<input name=siteq type=search value="{escape(query)}" required></label><button>Find documents</button></form>'+
            (f'<a href="{escape(search)}">View web search results for {escape(query)} ↗</a>' if query else "")+'</section>')

def browse(db,code,url,token,*,directory=None,base="/opengov"):
    import opengov,discovery
    country=(COUNTRIES if directory is None else directory).get(code)
    if not country or not allowed(country,url):raise ValueError("Unknown government portal.")
    body=f'<a href="{base}?country={code}">← {escape(country["name"])}</a> · <a href="{escape(url)}">Open official website ↗</a>'
    try:
        with fetch(country,url) as response:
            mime=response.headers.get_content_type()
            address=response.geturl()
            if mime=="application/pdf":
                ext=".pdf"
                title=urlsplit(address).path.split("/")[-1] or "Government publication"
                links=[]
            elif mime in {"text/html","application/xhtml+xml"}:
                ext=".txt"
                parsed=parse_html(response)
                title=" ".join("".join(parsed.title).split()) or country["name"]
                links=[]
                for href,label in parsed.links.items():
                    dest=urldefrag(urljoin(address,href))[0]
                    if not label.strip() or dest==address:continue
                    if not allowed(country,dest):
                        if urlsplit(dest).scheme=="https":
                            links.append(f'<a href="{escape(dest)}">{escape(label.strip()[:150])} ↗</a>')
                        continue
                    links.append(f'<a href="{escape(route(code,dest,base))}">{escape(label.strip()[:150])}</a>')
            else:raise ValueError("Use the official website to open this file format.")
        item=opengov.record(title,country["name"]+" · "+urlsplit(address).hostname,"National portal · "+country["name"],address,ext)
        if base=="/opencorpo":item["rights"]="OpenCorpo · "+item["rights"]
        with db:
            db.execute("INSERT OR IGNORE INTO discovery_item(id,kind,title,preview,rights,url,ext,provider) VALUES(:id,:kind,:title,:preview,:rights,:url,:ext,:provider)",item)
        saved=db.execute("SELECT filename FROM discovery_item WHERE id=?",(item["id"],)).fetchone()[0]
        control=(f'<a href="/content/{item["id"]}">Read offline →</a>' if saved else
                 f'<form method=post action="/discover/add"><input type=hidden name=token value="{token}"><input type=hidden name=item value="{item["id"]}"><button>Save to Documents</button></form>')
        return body+f'<h3>{escape(title)}</h3>{control}<nav class="gov-portal-links">{" ".join(dict.fromkeys(links))}</nav>'
    except (OSError,ValueError) as error:
        return body+f'<p role=status>Portal reader unavailable. {escape(str(error))}</p>'

def country_for(item):
    catalog=COUNTRIES
    if item["rights"].startswith("OpenCorpo ·"):
        from opencorpo import PORTALS
        catalog=PORTALS
    return next((c for c in catalog.values() if item["provider"]==c["name"]+" · "+str(urlsplit(item["url"]).hostname) and allowed(c,item["url"])),None)
