"""Editorial sources selected per edition. Hostnames also identify saved articles offline."""
from urllib.parse import urlsplit

WORLD = [
    ("The Guardian","https://www.theguardian.com/world/rss","theguardian.com"),
    ("Al Jazeera","https://www.aljazeera.com/xml/rss/all.xml","aljazeera.com"),
    ("France 24","https://www.france24.com/en/rss","france24.com"),
    ("Deutsche Welle","https://rss.dw.com/rdf/rss-en-all","dw.com"),
    ("NPR","https://feeds.npr.org/1004/rss.xml","npr.org"),
    ("CBC","https://www.cbc.ca/cmlink/rss-world","cbc.ca"),
    ("RNZ","https://www.rnz.co.nz/rss/world.xml","rnz.co.nz"),
    ("CNA","https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311","channelnewsasia.com"),
    ("Africanews","https://www.africanews.com/feed/rss","africanews.com"),
    ("The Hindu","https://www.thehindu.com/news/international/feeder/default.rss","thehindu.com"),
    ("South China Morning Post","https://www.scmp.com/rss/91/feed","scmp.com"),
]
SCOTLAND = [("The National","https://www.thenational.scot/news/rss/","thenational.scot"),
            ("The Guardian","https://www.theguardian.com/uk/scotland/rss","theguardian.com")]
NORTH = ("The Press and Journal","https://www.pressandjournal.co.uk/category/news/aberdeen-aberdeenshire/feed/","pressandjournal.co.uk")
REGION_TAGS = {"United Kingdom":"uk-news","England":"uk/uk","Wales":"uk/wales","Northern Ireland":"uk/northernireland",
               "London":"uk/london","Manchester":"uk/manchester","Africa":"world/africa","Asia":"world/asia-pacific",
               "Australia":"australia-news","Europe":"world/europe","Middle East":"world/middleeast",
               "US and Canada":"us-news","Latin America and the Caribbean":"world/americas"}

def feeds(edition,bbc_path):
    sources=[("BBC News","https://feeds.bbci.co.uk/news/"+bbc_path+"/rss.xml","bbc.co.uk")]
    if edition=="World":return sources+WORLD
    if edition.startswith("Aberdeen"):return sources+[NORTH]
    if edition=="Scotland":return sources+SCOTLAND
    if bbc_path.startswith("scotland/"):
        # A national feed would mislabel these stories as city reporting.
        return sources+[("The Scotsman","https://www.scotsman.com/rss", "scotsman.com")]
    if edition in REGION_TAGS:
        sources.append(("The Guardian","https://www.theguardian.com/"+REGION_TAGS[edition]+"/rss","theguardian.com"))
    return sources

def matches(link,domain):
    host=(urlsplit(link).hostname or "").lower()
    return host==domain or host.endswith("."+domain) or (domain=="bbc.co.uk" and host in {"bbc.com","www.bbc.com"})

def publisher(link):
    for name,_,domain in WORLD+SCOTLAND+[NORTH,("The Scotsman","","scotsman.com"),("BBC News","","bbc.co.uk")]:
        if matches(link,domain):return name
    return urlsplit(link).hostname or "Publisher"
