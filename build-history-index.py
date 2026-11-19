"""Build the offline event index from year articles on a local Kiwix server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError
from time import sleep


class Events(HTMLParser):
    def __init__(self):
        super().__init__()
        self.heading = None
        self.active = False
        self.capture = None
        self.parts = []
        self.hidden = []
        self.rows = []
        self.source_title = None

    def handle_starttag(self, tag, attrs):
        if tag=="link" and dict(attrs).get("rel")=="canonical":
            self.source_title=urlsplit(dict(attrs).get("href","")).path.split("/")[-1]
        if tag in ("sup","table","style","script","figure","nav"):
            self.hidden.append(tag)
        if self.hidden:return
        if tag=="h2":
            self.heading = []
            self.active = False
        if self.active and tag in ("li","p"):
            if self.capture=="li" and tag=="p":return
            self.capture=tag
            self.parts=[]
        if tag=="br" and self.capture:self.parts.append(" ")

    def handle_data(self,value):
        if self.hidden:return
        if self.heading is not None:self.heading.append(value)
        if self.capture:self.parts.append(value)

    def handle_endtag(self,tag):
        if self.hidden:
            if tag==self.hidden[-1]:self.hidden.pop()
            return
        if tag=="h2" and self.heading is not None:
            heading="".join(self.heading).strip().lower()
            self.active=heading in {"events","global events","europe","africa","asia","oceania","the americas","americas","events and trends","politics and society","art and culture","by place","by topic","world events","early history","classical antiquity","middle paleolithic","upper paleolithic","holocene","common era"}
            self.heading=None
        if tag==self.capture:
            line=" ".join("".join(self.parts).split())
            if len(line)>=26 and len(line)<=6000 and not line.endswith(":"):
                self.rows.append(line)
            self.capture=None

def early_rows(data,topic):
    reader=Events()
    reader.feed(data)
    for text in dict.fromkeys(reader.rows):
        start=re.match(r"(?i)^(?:c(?:a)?\.\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(kya|BC(?:E)?|years ago)\b",text)
        if not start:continue
        magnitude=float(start[1].replace(",",""))
        unit=start[2].lower()
        year=-int(magnitude) if unit.startswith("bc") else round(1950-magnitude*(1000 if unit=="kya" else 1))
        if -3300000<=year<=2025 and year!=0:yield year,topic,text

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("origin",help="Local Kiwix /zim/content/BOOK URL")
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    if urlsplit(args.origin).hostname!="127.0.0.1":parser.error("Use a local archive")
    def year_rows(year):
        page=(str(-year)+"_BC" if year<0 else "AD_"+str(year) if year<1000 else str(year))
        for attempt in range(3):
            try:
                with urlopen(args.origin+"/"+quote(page),timeout=30) as r:data=r.read().decode("utf-8")
                break
            except HTTPError as e:
                if e.code==404:return []
                if attempt==2:raise
            except OSError:
                if attempt==2:raise
            sleep(.5)
        reader=Events()
        reader.feed(data)
        if reader.source_title not in {page,str(year) if year>0 else page,"AD_"+str(year)}:
            return []
        return [(year,reader.source_title,line) for line in dict.fromkeys(reader.rows)
                if not line.startswith(("Below, the events","For events in","This section "))]

    tmp=args.output.with_suffix(".building")
    if tmp.exists():raise SystemExit("Build file already exists")
    with sqlite3.connect(tmp) as db,ThreadPoolExecutor(max_workers=6) as pool:
        db.execute("CREATE TABLE event(year INTEGER, article TEXT, text TEXT)")
        for i,rows in enumerate(pool.map(year_rows,[*range(-700,0),*range(1,2026)])):
            db.executemany("INSERT INTO event VALUES(?,?,?)",rows)
            if i%300==0:print(i,flush=True)
        for topic in ("Timeline_of_prehistory","Timeline_of_ancient_history"):
            with urlopen(args.origin+"/"+topic,timeout=30) as response:
                db.executemany("INSERT INTO event VALUES(?,?,?)",early_rows(response.read().decode("utf-8"),topic))
        db.execute("CREATE INDEX event_year ON event(year)")
        count=db.execute("SELECT count(*) FROM event").fetchone()[0]
        if count<10000:raise ValueError("Incomplete year index")
    tmp.replace(args.output)
    print(count,"events")

if __name__=="__main__":main()
