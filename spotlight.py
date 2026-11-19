"""Home discoveries and offline data readers."""
from html import escape
from pathlib import Path
import json
import random
import re
from urllib.parse import urlsplit

import media_previews
from kit_library import GROUPS, carousel
from news import date_label
from publishers import publisher

LABEL={"Pictures":"Picture","Books":"Book","Films":"Video","Shows":"Show","Games":"Game","Software":"Software","Audiobooks":"Audiobook"}
SYMBOL={"Picture":"▧","Book":"▤","Video":"▶","Show":"▣","Game":"✜","Software":"⌘","Audiobook":"♫","News":"≋","World data":"◉"}
TONE={"Picture":"#d6a8c6","Book":"#e1ba98","Video":"#b9b9ea","Show":"#a6c5e5","Game":"#dcc783","Software":"#b9cccc","Audiobook":"#d3aed2","News":"#b3d8ac","World data":"#94d2c6"}

def normalized(title):
    title=re.split(r"\s[·|]|:|;|\s\(",title.casefold(),maxsplit=1)[0]
    return re.sub(r"[^\w]+"," ",title).strip()

def seed(db):
    data=json.loads(Path(__file__).with_name("discover-starters.json").read_text())
    with db:
        db.executemany("""INSERT OR IGNORE INTO discovery_item(id,kind,title,preview,rights,url,ext,provider)
            VALUES(:id,:kind,:title,:preview,:rights,:url,:ext,:provider)""",(r for group in data.values() for r in group))

def collection_titles(kit):
    found=set()
    if kit:
        for kind,(_,folder,formats) in GROUPS.items():
            base=kit/folder
            if base.is_dir():
                for p in base.rglob("*"):
                    if p.suffix.lower() in formats and not any(s.startswith(".") for s in p.relative_to(base).parts):
                        found.update([normalized(p.stem),normalized(p.parent.name)])
        games=kit/"04-Entertainment/Games"
        if games.is_dir():found.update(normalized(p.stem) for p in list(games.glob("*.app"))+list((games/"Browser Puzzles").glob("*.html")))
    return found

def card(kind,title,brief,by,url):
    key=url.rsplit("/",1)[-1]
    art=media_previews.tag("story-"+key if kind=="News" else key,title) if kind!="World data" else '<div class="world-preview" aria-hidden="true">◉</div>'
    return (f'<a class="tile result-card discovery-card" href="{escape(url,quote=True)}" style="--source-accent:{TONE.get(kind,"#bde5c9")}">'
            f'{art}<span class="discover-type"><span aria-hidden=true>{SYMBOL.get(kind,"▥")}</span>{escape(kind)}</span>'
            f'<strong>{escape(title)}</strong><p>{escape(brief)}</p><small>{escape(by)}</small></a>')

def mix(db,kit_titles):
    owned=kit_titles|{normalized(r[0]) for r in db.execute("""SELECT title FROM discovery_item
        WHERE filename IS NOT NULL OR id IN (SELECT id FROM discovery_cart)
        OR ('discover-'||id) IN (SELECT source FROM content_download WHERE state IN ('Queued','Downloading'))""")}
    cards=[]
    article=db.execute("""SELECT * FROM (SELECT id,title,summary,link FROM news_story ORDER BY published DESC LIMIT 30)
                          ORDER BY RANDOM() LIMIT 1""").fetchone()
    if article:cards.append(card("News",article["title"],article["summary"],publisher(article["link"]),"/news/"+str(article["id"])))
    snapshot=db.execute("SELECT id,body FROM snapshot WHERE source='worldbank-population' ORDER BY id DESC LIMIT 1").fetchone()
    if snapshot:
        try:
            rows=json.loads(snapshot["body"])[1]
            world=next(r for r in rows if r.get("countryiso3code")=="WLD" and isinstance(r.get("value"),int))
            cards.append(card("World data",f'{world["value"]/1e9:.2f} billion people',f'World population in {world["date"]}. Explore the trend and compare economies.',"World Bank","/read/"+str(snapshot["id"])))
        except (ValueError,TypeError,IndexError,StopIteration,KeyError):pass
    for kind,label in LABEL.items():
        for r in db.execute("""SELECT id,title,preview,provider FROM discovery_item WHERE kind=? AND filename IS NULL
            AND id NOT LIKE 'personal-%' ORDER BY RANDOM()""",(kind,)):
            name=normalized(r["title"])
            if not name or name in owned:continue
            owned.add(name)
            cards.append(card(label,r["title"],r["preview"],r["provider"],"/discover/item/"+r["id"]))
            break
    random.shuffle(cards)
    return '<div class=section-head><h2>Discover</h2><a href="/discover">Browse catalogues</a></div>'+carousel("Discover","".join(cards),"collection", 'id="recent-cards"')

def item_page(row,token):
    kind=LABEL.get(row["kind"],row["kind"])
    name=escape(row["title"])
    url=urlsplit(row["url"])
    origin=escape(url.hostname or row["provider"])
    action=(f'<a href="/content/{row["id"]}">Open in Library</a>' if row["filename"] else
            f'<form method=post action="/discover/add"><input type=hidden name=token value="{escape(token)}"><input type=hidden name=item value="{row["id"]}"><button>Download to Library</button></form>')
    art=media_previews.tag(row["id"],row["title"],True)
    if row["kind"] in {"Films","Shows"}:
        art=(f'<video class=publisher-video playsinline controls preload=none poster="/publisher-art/{row["id"]}" '
             f'src="/publisher-video/{row["id"]}"></video><small>Publisher video preview · requires internet</small>')
    return (f'<section class="discovery-detail" style="--source-accent:{TONE.get(kind,"#bde5c9")}"><div class="discover-type">{escape(kind)} · {escape(row["provider"])}</div>'
            f'<h3>{name}</h3>{art}<p>{escape(row["preview"])}</p>{action}</section>'
            f'<div class="source-credit"><strong>{origin}</strong><p>{escape(row["rights"])}</p></div>')

def population(records,snapshot):
    valid=[r for r in records if isinstance(r.get("value"),int) and isinstance(r.get("country"),dict)]
    world=next((r for r in valid if r.get("countryiso3code")=="WLD"),None)
    if not world:return ""
    historic=json.loads(Path(__file__).with_name("world-population.json").read_text())["series"]
    end=int(world["date"]); series=dict((y,n) for y,n in historic if y<end);series[end]=world["value"]
    points=sorted(series.items())
    chart=""
    if len(points)>1:
        start,first=points[0];span=max(series.values())-min(series.values()) or 1
        xy=" ".join(f'{4+492*(year-start)/(end-start):.1f},{114-104*(n-min(series.values()))/span:.1f}' for year,n in points)
        chart=(f'<figure class=pop-chart><figcaption>World population · {start}–{end}</figcaption><svg viewBox="0 0 500 122" role=img aria-label="World population from {first:,} in {start} to {world["value"]:,} in {end}">'
               f'<polyline points="{xy}" fill="none" stroke="currentColor" stroke-width="3"/></svg><div><span>{start} · {first/1e9:.2f} billion</span><span>{end} · {world["value"]/1e9:.2f} billion</span></div></figure>')
    def table_row(r):
        return f'<tr><th scope=row>{escape(r["country"]["value"])}</th><td>{escape(str(r["date"]))}</td><td>{r["value"]:,}</td></tr>'
    table="".join(table_row(r) for r in sorted(valid,key=lambda r:r["country"]["value"].casefold()))
    comparisons=[r for r in valid if r.get("countryiso3code") in {"CHN","IND","USA","IDN","PAK","GBR"}]
    largest=max((r["value"] for r in comparisons),default=1)
    bars="".join(f'<li><div><span>{escape(r["country"]["value"])}</span><b>{r["value"]/1e6:,.1f}m</b></div><meter aria-label="Population" min=0 max="{largest}" value="{r["value"]}"></meter></li>' for r in sorted(comparisons,key=lambda r:-r["value"]))
    return (f'<section class="population-hero"><div><small>World Bank · {end}</small><h3>{world["value"]/1e9:.2f} billion</h3><p>Estimated world population</p><strong>{world["value"]:,} people</strong></div>{chart}</section>'
            f'<div class="section-head"><h3>Selected economies</h3></div><ul class="population-bars">{bars}</ul>'
            f'<details class="data-records"><summary>All {len(valid)} economies and aggregates</summary><label>Find a place <input id=population-filter type=search></label>'
            f'<div class=scroll-table><table id=population-records><thead><tr><th>Economy or aggregate</th><th>Year</th><th>Population</th></tr></thead><tbody>{table}</tbody></table></div></details>'
            f'<p><a href="/snapshot/{snapshot}">Download source data</a></p>')
