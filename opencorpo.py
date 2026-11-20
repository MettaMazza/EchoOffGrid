"""Public entity registers, investment disclosures and institutional accounts."""
import json
from html import escape
from pathlib import Path
from tempfile import NamedTemporaryFile
import re
from urllib.parse import urlencode, urljoin, urlsplit

import govports
import opengov

REGISTERS=json.loads(Path(__file__).with_name("corporate-registers.json").read_text())
GROUPS={
    "royal":("Royal households and estates",[
        ("UK Royal Household","https://www.royal.uk/media-centre/financial-reports"),
        ("The Crown Estate","https://www.thecrownestate.co.uk/"),
        ("Duchy of Cornwall","https://duchyofcornwall.org/"),
        ("Dutch Royal House","https://www.royal-house.nl/"),
        ("Royal House of Spain","https://www.casareal.es/")]),
    "ownership":("Owners, directors and family foundations",[
        ("SEC EDGAR · beneficial ownership and insider transactions","https://www.sec.gov/edgar/search/"),
        ("Companies House · people with significant control","https://find-and-update.company-information.service.gov.uk/"),
        ("ProPublica · foundation officers and tax filings","https://projects.propublica.org/nonprofits/"),
        ("Charity Commission · trustees and accounts","https://register-of-charities.charitycommission.gov.uk/")]),
    "capital":("Capital, foundations and public disclosures",[
        ("SEC EDGAR · filings and major shareholders","https://www.sec.gov/edgar/search/"),
        ("Norges Bank Investment Management","https://www.nbim.no/en/investments/"),
        ("IRS · tax-exempt organisations","https://apps.irs.gov/app/eos/"),
        ("UK Charity Commission","https://register-of-charities.charitycommission.gov.uk/"),
        ("Companies House · companies and officers","https://find-and-update.company-information.service.gov.uk/"),
        ("Berkshire Hathaway shareholder reports","https://www.berkshirehathaway.com/reports.html"),
        ("Gates Foundation financial statements","https://www.gatesfoundation.org/about/financials")])}
PORTALS={k:dict(name=v["name"],exact_hosts=True,sites=[u for _,_,urls in v["registers"] for u in urls if u.startswith("https://")]) for k,v in REGISTERS.items()}
PORTALS.update({k:dict(name=name,exact_hosts=True,sites=[u for _,u in entries]) for k,(name,entries) in GROUPS.items()})
PROVIDERS={"all":"All connected catalogues","gleif":"GLEIF · companies and funds","foundations":"Nonprofit Explorer · US tax filings","reports":"Institutional and royal reports","local":"On this device"}
REPORTS=[
 ("Sovereign Grant Annual Report 2024–25","UK Royal Household","Royal finances · audited annual accounts","https://www.royal.uk/sites/default/files/documents/2025-06/Sovereign%20Grant%20Annual%20Report%202024-25.pdf"),
 ("Government Pension Fund Global · Annual Report 2024","Norges Bank Investment Management","Capital · investments and financial statements","https://www.nbim.no/contentassets/7dd79cd87d4c4fd8a4d938ef6bcb51db/gpfg_annual_report_2024_uuweb2.pdf"),
 ("Annual Report 2024 · Berkshire Hathaway","Berkshire Hathaway","Corporate · annual shareholder report","https://www.berkshirehathaway.com/2024ar/2024ar.pdf")]


def record(*args):
    item=opengov.record(*args)
    item["rights"]="OpenCorpo · "+item["rights"]
    return item


def seed(db, folder):
    import discovery
    source=Path(__file__).with_name("corporate-starter.json")
    entry=json.loads(source.read_bytes())["data"]
    lei=entry["id"]
    starter=record(entry["attributes"]["entity"]["legalName"]["name"],"GLEIF","Public legal entity registration · "+lei,"https://api.gleif.org/api/v1/lei-records/"+lei,".json")
    discovery.remember(db,"Documents","corpo featured",1,[starter]+[record(*r) for r in REPORTS],False)
    target=folder/"Content"/(starter["id"]+".json")
    if not target.exists():
        target.parent.mkdir(exist_ok=True)
        with NamedTemporaryFile(dir=target.parent,delete=False) as tmp:
            tmp.write(source.read_bytes())
        Path(tmp.name).replace(target)
    db.execute("UPDATE discovery_item SET filename=? WHERE id=?",(target.name,starter["id"]))


def directory(code,query):
    options=''.join(f'<option value="{escape(k)}" {"selected" if k==code else ""}>{escape(v["name"])}</option>' for k,v in sorted(PORTALS.items(),key=lambda x:x[1]["name"]))
    form=f'<section class="gov-directory"><h3>Registers and disclosures</h3><form class="gov-search"><label>Jurisdiction or collection<select name="country"><option value="">Choose a directory</option>{options}</select></label><button>Browse directory</button></form>'
    if code not in PORTALS:
        return form+f'<p>{len(REGISTERS)} jurisdictions · GLEIF Registration Authorities List v1.9</p><nav class=pills><a href="?country=ownership">Owners and directors</a><a href="?country=capital">Capital and foundations</a><a href="?country=royal">Royal households and estates</a></nav></section>'
    links=GROUPS[code][1] if code in GROUPS else [(name+" · "+ref,u) for name,ref,urls in REGISTERS[code]["registers"] for u in (urls or [""])]
    def entry(name,url):
        if not url:return f'<span>{escape(name)} · Website unlisted</span>'
        dest=govports.route(code,url,"/opencorpo") if govports.allowed(PORTALS[code],url) else url
        return f'<a href="{escape(dest,quote=True)}">{escape(name)}</a>'
    links=''.join(entry(n,u) for n,u in links if query.casefold() in n.casefold())
    return form+f'<h3>{escape(PORTALS[code]["name"])}</h3><form class=gov-search><input type=hidden name=country value="{escape(code)}"><label>Filter registers<input name=siteq value="{escape(query)}"></label><button>Filter</button></form><nav class=gov-portal-links>{links}</nav><form class=gov-search action="/opencorpo/portal"><input type=hidden name=country value="{escape(code)}"><label>Publication URL<input type=url name=url required></label><button>Preview and save</button></form></section>'


def lookup(source,query,page):
    size=opengov.LIMIT
    if source=="gleif":
        params={"page[size]":size,"page[number]":page}
        if query:params["filter[fulltext]"]=query
        data=opengov.get_json("https://api.gleif.org/api/v1/lei-records?"+urlencode(params))
        rows=[]
        for r in data["data"]:
            lei=r["id"]
            if not re.fullmatch("[0-9A-Z]{20}",lei):continue
            entity=r["attributes"]["entity"]
            rows.append(record(entity["legalName"]["name"],"GLEIF"," · ".join(filter(None,[entity.get("jurisdiction"),entity.get("category"),entity.get("status"),lei])),"https://api.gleif.org/api/v1/lei-records/"+lei,".json"))
        return rows,bool(data["links"].get("next"))
    if source=="foundations":
        if not query:return [],False
        data=opengov.get_json("https://projects.propublica.org/nonprofits/api/v2/search.json?"+urlencode({"q":query,"page":page-1}))
        rows=[]
        for org in data["organizations"]:
            ein=str(org["ein"]).zfill(9)
            if re.fullmatch(r"[0-9]{9}",ein):
                rows.append(record(org["name"],"ProPublica Nonprofit Explorer"," · ".join(filter(None,[org.get("state"),"IRS filing summary",ein])),"https://projects.propublica.org/nonprofits/api/v2/organizations/"+ein+".json",".json"))
        return rows,page<data.get("num_pages",0)
    if source!="reports":raise ValueError("Unknown records catalogue")
    rows=[record(*r) for r in REPORTS]
    # Read the publisher's index so newly published accounts can also be found.
    home=GROUPS["royal"][1][0][1]
    try:
        with govports.fetch(PORTALS["royal"],home) as response:index=govports.parse_html(response)
        for href,label in index.links.items():
            dest=urljoin(home,href)
            if ("financial reports" in label.lower() and re.search(r'20\d\d',label) and govports.allowed(PORTALS["royal"],dest)):
                rows.append(record(label.strip(),"Royal households and estates · www.royal.uk","UK Royal Household · financial reports",dest,".txt"))
    except (OSError,ValueError):
        if query and not any(query.casefold() in ' '.join(r).casefold() for r in REPORTS):raise
    words=query.casefold().split()
    rows=[r for r in rows if all(w in (r["title"]+" "+r["preview"]+" "+r["provider"]).casefold() for w in words)]
    return rows[(page-1)*size:page*size],len(rows)>page*size


def json_reader(raw):
    data=json.loads(raw)
    if "organization" in data:
        org=data["organization"]
        fields=[("Name",org.get("name")),("EIN",org.get("ein")),("State",org.get("state")),("Tax filings",len(data.get("filings_with_data") or []))]
        for f in (data.get("filings_with_data") or [])[:20]:
            fields.append((str(f.get("tax_prd_yr","Filing"))+" reported revenue (USD)",f.get("totrevenue")))
    else:
        r=data["data"];a=r["attributes"];e=a["entity"]
        fields=[("Legal name",e["legalName"]["name"]),("LEI",r["id"]),("Jurisdiction",e.get("jurisdiction")),("Entity status",e.get("status")),("Registration status",a["registration"].get("status")),("Last updated",a["registration"].get("lastUpdateDate"))]
    return '<dl>'+''.join(f'<dt>{escape(k)}</dt><dd>{escape(str(v))}</dd>' for k,v in fields if v is not None)+'</dl>'
