"""Render the shared, offline History timeline."""
from contextlib import closing
from html import escape
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlencode, quote

ROOT=Path(__file__).with_name("vendor")/"history"
LANDMARKS=[(int(year),date,region,article,title,text) for year,date,region,article,title,text in
           (line.split("|",5) for line in (ROOT/"landmarks.tsv").read_text().splitlines() if line)]
FIRST,LAST=-3300000,2025
ERAS=[(FIRST,-100001,"Early humans"),(-100000,-10001,"Ice Age worlds"),(-10000,-3001,"Fields and villages"),
      (-3000,-701,"Cities and writing"),(-700,499,"Ancient societies"),(500,1399,"Connected worlds"),
      (1400,1749,"Ocean crossings"),(1750,1913,"Revolutions"),(1914,1989,"World wars and independence"),
      (1990,LAST,"Living memory")]
SIZE=18


READINGS={
    "History of Easter Island":("Population collapse or resilience?",
        "Pollen and charcoal record forest loss. Those observations do not directly measure population.",
        "A once influential explanation proposed that deforestation caused a demographic collapse before Europeans arrived. A 2024 analysis of 15 ancient genomes found no strong seventeenth-century bottleneck. The genetic estimate is model-dependent and measures effective population, not a census."),
    "Late Bronze Age collapse":("Several causes, different places",
        "Some settlements show destruction, others abandonment or continuity. Their chronologies differ.",
        "Drought, internal rebellion, warfare and trade disruption have all been proposed. A destruction layer can support violent loss without identifying an attacker. Regional comparisons test whether an explanation travels beyond a single site."),
    "Indus Valley Civilisation":("Writing system or another kind of sign system?",
        "Short recurring sign sequences survive on seals and other objects. No accepted bilingual key has been found.",
        "Many researchers interpret the signs as writing. A minority view treats them as non-linguistic symbols. Proposals identifying a particular language face the further challenge of producing independently testable readings."),
    "Great Zimbabwe":("How an unsupported claim persisted",
        "Excavation, dating and material culture place the city in local African traditions.",
        "European writers once attributed the ruins to outsiders. The claim served colonial politics and failed archaeological tests. Its historical importance is the influence it exerted on people and institutions."),
    "White Sands National Park":("How old are the footprints?",
        "Researchers documented tracks in layered sediment. The disputed inference was the age of the layers.",
        "Critics pointed out that aquatic seeds can yield radiocarbon dates older than the sediment. Terrestrial pollen and luminescence dating later supported the early chronology. This did not settle every question about migration routes.")
}

def comparison(article):
    if article not in READINGS:return ""
    question,observation,interpretation=READINGS[article]
    return (f'<details class=h-note><summary>{escape(question)}</summary>'
            f'<h4>Evidence</h4><p>{escape(observation)}</p><h4>Interpretations</h4><p>{escape(interpretation)}</p></details>')

def date(year):
    return f"{abs(year):,} BCE" if year<0 else f"{year} CE"


def parse_year(value):
    match=re.fullmatch(r"(-?[0-9]{1,7})\s*(BCE?|CE|AD)?",value.strip().upper().replace(",",""))
    if not match:return None
    year=int(match[1])
    return -abs(year) if match[2] in {"BC","BCE"} else year


def route(**params):
    return "/history?"+escape(urlencode(params),quote=True)


def bounds(center,width):
    width=max(1,min(LAST-FIRST+1,width))
    low=min(max(FIRST,center-width//2),LAST-width+1)
    if low==0 and width==1:low=1
    return low,low+width-1


def page(params):
    def value(key,default=""):return params.get(key,[default])[0][:180]
    def number(key,default):
        raw=value(key)
        return int(raw) if re.fullmatch(r"-?\d{1,8}",raw) else default
    q=value("q").strip()
    low=max(FIRST,min(LAST,number("from",FIRST)))
    high=max(low,min(LAST,number("to",LAST)))
    warning=""
    if value("jump"):
        y=parse_year(value("jump"))
        if y is None or y==0 or not FIRST<=y<=LAST:warning="Enter a year from 3,300,000 BCE to 2025 CE. The calendar has no year zero."
        else:low=high=y
    if q:low,high=FIRST,LAST
    full=low==FIRST and high==LAST
    width=high-low+1
    center=(low+high)//2
    mode=value("view","landmarks" if full and not q else "all")
    if q or mode not in {"all","landmarks"}:mode="all"
    pg=max(1,min(99999,number("page",1)))
    with closing(sqlite3.connect(ROOT.joinpath("events.db").resolve().as_uri()+"?mode=ro",uri=True)) as db:
        db.row_factory=sqlite3.Row
        db.execute("CREATE TEMP TABLE guide(year,date,region,article,title,text)")
        db.executemany("INSERT INTO guide VALUES(?,?,?,?,?,?)",LANDMARKS)
        db.execute("""CREATE TEMP VIEW history AS SELECT *,1 AS guided FROM guide
                    UNION ALL SELECT year,'','',article,'',text,0 FROM event""")
        where="year BETWEEN ? AND ?"
        args=[low,high]
        if mode=="landmarks":where+=" AND guided=1"
        if q:
            for term in q.split()[:12]:
                where+=" AND instr(lower(text||' '||title||' '||region||' '||article),lower(?))>0"
                args.append(term)
        count=db.execute("SELECT count(*) FROM history WHERE "+where,args).fetchone()[0]
        pages=max(1,(count+SIZE-1)//SIZE)
        pg=min(pg,pages)
        rows=db.execute("SELECT * FROM history WHERE "+where+" ORDER BY year,guided DESC LIMIT ? OFFSET ?",[*args,SIZE,(pg-1)*SIZE]).fetchall()
        segments=ERAS if full else [(low+i*width//min(width,10),low+(i+1)*width//min(width,10)-1,"") for i in range(min(width,10))]
        rail=[]
        for start,end,label in segments if width>1 else []:
            if start==end==0:continue
            n=db.execute("SELECT count(*) FROM event WHERE year BETWEEN ? AND ?",(start,end)).fetchone()[0]+sum(start<=r[0]<=end for r in LANDMARKS)
            caption=date(start or 1) if start==end else date(start or 1)+" – "+date(end or -1)
            rail.append(f'<a class=h-period href="{route(**{"from":start,"to":end})}"><small>{escape(label or "Period")}</small><b>{caption}</b><span>{n:,} entries</span></a>')
    def window_link(label,edges):
        return f'<a href="{route(**{"from":edges[0],"to":edges[1]})}">{label}</a>'
    controls=[window_link("All eras",(FIRST,LAST))]
    if not full:
        if low>FIRST:controls.append(window_link("← Earlier",bounds(center-width,width)))
        if high<LAST:controls.append(window_link("Later →",bounds(center+width,width)))
        controls.append(window_link("Zoom out",bounds(center,max(width+2,width*5))))
    if width>1:controls.append(window_link("Zoom in",bounds(center,max(1,width//5))))
    cards=[]
    for row in rows:
        yr=row["year"]
        topic=row["article"]
        source=route(read=topic)
        tight=bounds(yr,1 if abs(yr)<3000 else max(101,abs(yr)//10))
        when=row["date"] or (("Approx. " if topic.startswith("Timeline_") else "")+date(yr))
        heading=f'<h3>{escape(row["title"])}</h3>' if row["title"] else ""
        caption=row["region"] or ("Wikipedia chronology" if topic.startswith("Timeline_") else "Wikipedia year entry")
        cards.append(f'<article class=h-entry><small>{escape(when)} · {escape(caption)}</small>{heading}<p>{escape(row["text"])}</p>{comparison(topic) if row["guided"] else ""}<nav><a href="{source}">Read Wikipedia</a> <a href="{route(**{"from":tight[0],"to":tight[1]})}">Nearby events</a></nav></article>')
    def listing(view,number):
        return route(**{"from":low,"to":high,"view":view,"q":q,"page":number})
    pager=" ".join(f'<a href="{listing(mode,num)}">{label}</a>' for num,label in ((pg-1,"← Previous"),(pg+1,"Next →")) if 1<=num<=pages)
    intro='''<details class=h-note><summary>How to read the evidence</summary><p>Fossils, objects, oral histories and written records preserve different things. A fossil can be dated while its place in a family tree remains disputed. An atrocity can be extensively documented while individual names and exact totals are still being recovered.</p><p>Early dates are approximate. A year on the timeline can mark the beginning of a process lasting generations. The guided entries discuss competing interpretations and, where relevant, why a once-popular or fringe claim lost support. For early chronology ranges, the timeline uses the first stated date. Ages given in thousands of years ago are plotted approximately relative to 1950. A missing entry means a gap in this collection. Wikipedia’s year pages favour some regions, languages and types of record.</p></details>'''
    era_title="Human history" if full else date(low or 1)+(f" – {date(high)}" if high!=low else "")
    show_entries=not warning and (width==1 or bool(q) or pg>1 or (not full and count<=1))
    rail_html=(f'<p>{"Scroll through the eras and select one to zoom in." if full else "Select an interval to explore its entries."}</p>'
               f'<nav class=h-rail aria-label="Scrollable timeline" tabindex=0>{"".join(rail)}</nav>') if rail else ""
    return (f'<section class="h-atlas" data-show-entries="{int(show_entries)}"><small>Offline historical atlas</small><h3>{era_title}</h3>'
            f'<form class=h-search><label>Search all history<input name=q type=search value="{escape(q)}" placeholder="Place, event, person or idea"></label><button>Search</button></form>'
            f'<form class=h-search><label>Jump to a year<input name=jump placeholder="e.g. 250 BCE" required></label><button>Jump</button></form>'
            f'<p role=status>{escape(warning)}</p><nav class=pills>{" ".join(controls)}</nav>'
            f'{rail_html}</section>{intro}'
            f'<div class=section-head id=history-entries tabindex="-1"><h3>{"Search results" if q else "Guided history" if mode=="landmarks" else ("Entries for "+date(low) if width==1 else "Historical entries")}</h3>'
            +(f'<a href="{listing("all" if mode=="landmarks" else "landmarks",1)}">{"Show all entries" if mode=="landmarks" else "Show guided history"}</a>' if not q else '<a href="/history">Clear search</a>')+'</div>'
            +(f'<nav class=pills><a href="/history">All eras</a></nav>' if not full else '')
            +f'<small>{count:,} entries · Page {pg:,} of {pages:,}</small><section class=h-results>'+("".join(cards) or '<p>No indexed entries here. Try a different period or search the <a href="/wikipedia">offline encyclopedia</a>.</p>')+f'</section><nav class=pills>{pager}</nav>'
            +'<p><small>Chronology and year entries excerpted from English Wikipedia, June 2026 archive, through the last complete year, 2025. Wikipedia contributors · CC BY-SA 4.0. Each entry links to its source article.</small></p>')


def article(wiki,title):
    title=title[:240].replace("_"," ")
    if not title:return page({})
    archive=next((p for p in wiki.archives if p.name.startswith("wikipedia_en_all_")),None)
    search="/wikipedia?"+escape(urlencode({"q":title}))
    if archive is None:return wiki.page("",title)
    src="/zim/content/"+quote(archive.stem,safe="")+"/"+quote(title.replace(" ","_"),safe="")
    return (f'<h3>{escape(title)}</h3><p><a href="{search}">Search this title across the offline encyclopedia</a></p>'
            f'<div class="wiki-surface"><iframe title="Offline Wikipedia article" sandbox="allow-same-origin" class="kit-document wiki-frame" src="{escape(src)}"></iframe></div>')
