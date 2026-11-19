"""HTTPS reading over an app-owned Tor SOCKS socket. Remote markup is never executed."""
from browser_proxy import BrowserProxy
import http.client
import ipaddress
import os
from pathlib import Path
import socket
import secrets
import ssl
import subprocess
import tempfile
from threading import Lock, Thread
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

ROOT = Path(__file__).parent / "vendor/private-browser"
COUNTRIES = {"":"Automatic", "gb":"United Kingdom", "us":"United States", "de":"Germany", "fr":"France",
             "nl":"Netherlands", "se":"Sweden", "ch":"Switzerland", "ca":"Canada", "fi":"Finland",
             "at":"Austria", "ro":"Romania", "pl":"Poland", "es":"Spain", "au":"Australia", "jp":"Japan"}
LIMIT = 3 * 1024 * 1024


def address(value):
    value = value.strip()
    if len(value) > 4096 or any(ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Enter a public HTTPS address.")
    parsed = urlsplit(value if "://" in value else "https://" + value)
    host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
    if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None or
            parsed.port not in {443, None} or "." not in host or host.endswith((".local",".localhost",".internal"))):
        raise ValueError("Enter a public HTTPS address.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and not ip.is_global:
        raise ValueError("Choose a public website.")
    return urlunsplit(("https", host, quote(parsed.path or "/", safe="/%:@-._~!$&'()*+,;="),
                       quote(parsed.query, safe="/%?:@-._~!$&'()*+,;="), ""))


class Reader(HTMLParser):
    blocks = {"h1","h2","h3","h4","p","li","blockquote","strong","em","ul","ol","br","pre","code"}
    hidden = {"head","script","style","svg","noscript","template","iframe","canvas","object","video","audio","form"}
    def __init__(self, base, image_url=None):
        super().__init__(convert_charrefs=True)
        self.base, self.parts, self.links, self.skipped = base, [], [], []
        self.in_link = False
        self.image_url = image_url

    def handle_starttag(self, tag, attrs):
        if self.skipped == ["head"] and (tag=="body" or tag in self.blocks or tag in {"main","div","article","header"}):
            self.skipped.clear()
        if tag in self.hidden:
            self.skipped.append(tag)
        if self.skipped:
            return
        if tag in self.blocks:
            self.parts.append("<"+tag+">")
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                try:
                    target = address(urljoin(self.base, href))
                except (ValueError,UnicodeError):
                    return
                self.links.append(target)
                self.parts.append(f'<button form="private-links" name="url" value="{escape(target,quote=True)}">')
                self.in_link = True
        elif tag=="img":
            attributes=dict(attrs)
            alt=attributes.get("alt") or ""
            src=attributes.get("src")
            resolved=urljoin(self.base,src) if src else ""
            if self.image_url and resolved.startswith("https://") and urlsplit(resolved).hostname==urlsplit(self.base).hostname:
                local=self.image_url(resolved)
                if local:self.parts.append(f'<img loading=lazy alt="{escape(alt,quote=True)}" src="{local}">')
            elif alt:self.parts.append(escape(alt)+" ")

    def handle_endtag(self, tag):
        if self.skipped:
            if tag == self.skipped[-1]: self.skipped.pop()
            return
        if tag in self.blocks and tag!="br":
            self.parts.append("</"+tag+">")
        if tag=="a" and self.in_link:
            self.parts.append("</button>")
            self.in_link=False

    def handle_data(self,data):
        if not self.skipped:self.parts.append(escape(data))


def receive(stream, length):
    result=bytearray()
    while len(result)<length:
        part=stream.recv(length-len(result))
        if not part:raise OSError("Tor closed the connection")
        result.extend(part)
    return bytes(result)


class Session:
    def __init__(self, state, binary=None):
        self.state=Path(state)
        self.binary=Path(binary) if binary else ROOT/"macos/tor"
        self.lock=Lock()
        self.process=None
        self.proxy=None
        self.location=""
        self.progress=0
        self.images={}
        self.history=[]
        self.position=-1
        self.temp=None

    def close(self):
        with self.lock:self._stop()

    def _stop(self):
        if self.proxy:
            self.proxy.stop();self.proxy=None
        if self.process:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process=None
        self.history.clear()
        self.position=-1
        self.images.clear()
        if self.temp:self.temp.cleanup()
        self.temp=None
        self.progress=0

    def start(self, country):
        if country not in COUNTRIES:raise ValueError("Choose a listed exit country.")
        with self.lock:
            if self.process and self.process.poll() is None and self.location==country:return
            self._stop()
            self.location=country
            self.state.mkdir(mode=0o700,parents=True,exist_ok=True)
            self.temp=tempfile.TemporaryDirectory(prefix="pb-",dir=self.state if os.environ.get("ANDROID_ROOT") else "/tmp")
            self.socket_path=str(Path(self.temp.name)/"s")
            config=Path(self.temp.name)/"torrc"
            config.touch(mode=0o600)
            args=[str(self.binary),"-f",str(config),"--DataDirectory",str(self.state),"--SocksPort","unix:"+self.socket_path,
                  "--GeoIPFile",str(ROOT/"data/geoip"),"--GeoIPv6File",str(ROOT/"data/geoip6"),
                  "--ClientRejectInternalAddresses","1","--SafeLogging","1","--Log","notice stdout",
                  "--__OwningControllerProcess",str(os.getpid())]
            if country:args+=["--ExitNodes","{"+country+"}","--StrictNodes","1"]
            self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            self.proxy=BrowserProxy(self.socket_path)
            Thread(target=self._watch,args=(self.process,),daemon=True).start()

    def _watch(self, process):
        import re
        with process.stdout as logs:
            for line in logs:
                match=re.search(r"Bootstrapped (\d+)%",line)
                if match and process is self.process:self.progress=int(match[1])

    def status(self):
        with self.lock:
            if not self.process:return "Disconnected",False
            if self.process.poll() is not None:return "Connection failed. Reconnect to try again.",False
            if self.progress<100:return f"Connecting to Tor · {self.progress}%",False
            return "Tor connected · "+COUNTRIES[self.location],True

    def navigate(self, action, url):
        with self.lock:
            process=self.process
            position=self.position
            if action in {"back","forward"}:
                position+= -1 if action=="back" else 1
                if not 0<=position<len(self.history):raise ValueError("No page in that direction.")
                url=self.history[position]
        final,article=self.fetch(url)
        with self.lock:
            if process is not self.process:raise ValueError("The browsing session ended.")
            if action in {"back","forward"}:self.position=position
            else:
                self.history=(self.history[:self.position+1]+[final])[-40:]
                self.position=len(self.history)-1
        return final,article

    def remember_image(self, path, url):
        with self.lock:
            if not self.temp or path!=self.socket_path or len(self.images)>=1500:return None
            key=secrets.token_hex(16)
            self.images[key]=url
            return "/private-image/"+key

    def image(self,key):
        with self.lock:url=self.images.get(key)
        if not url:raise ValueError("Image expired")
        return self.fetch(url, image=True)

    def fetch(self, value, image=False):
        url=address(value)
        with self.lock:
            if not self.process or self.process.poll() is not None or self.progress!=100:
                raise ValueError("Connect to Tor before opening a website.")
            path=self.socket_path
        for _ in range(5):
            target=urlsplit(url)
            host=target.hostname.encode("ascii")
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as proxy:
                proxy.settimeout(30)
                proxy.connect(path)
                proxy.sendall(b"\x05\x01\x00")
                if receive(proxy,2)!=b"\x05\x00":raise OSError("SOCKS negotiation failed")
                proxy.sendall(b"\x05\x01\x00\x03"+bytes([len(host)])+host+b"\x01\xbb")
                version,reply,_,kind=receive(proxy,4)
                if version!=5 or reply!=0:raise OSError("The exit could not reach that website")
                size={1:4,4:16}.get(kind)
                if kind==3:size=receive(proxy,1)[0]
                if size is None:raise OSError("Invalid SOCKS reply")
                receive(proxy,size+2)
                with ssl.create_default_context().wrap_socket(proxy,server_hostname=target.hostname) as tls:
                    request=urlunsplit(("","",target.path,target.query,""))
                    accept="image/png,image/jpeg,image/gif,image/webp" if image else "text/html,text/plain"
                    tls.sendall(f"GET {request} HTTP/1.1\r\nHost: {target.hostname}\r\nUser-Agent: Mozilla/5.0\r\nAccept: {accept}\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n".encode("ascii"))
                    with http.client.HTTPResponse(tls) as response:
                        response.begin()
                        if response.status in (301,302,303,307,308) and response.getheader("Location"):
                            url=address(urljoin(url,response.getheader("Location")));continue
                        if response.status>=400:raise ValueError(f"The website returned HTTP {response.status}.")
                        mime=response.headers.get_content_type()
                        if image:
                            if mime not in {"image/jpeg","image/png","image/webp","image/gif"}:raise ValueError("Unsupported image type")
                            blob=response.read(LIMIT+1)
                            if len(blob)>LIMIT:raise ValueError("Image too large")
                            return mime,blob
                        if mime not in {"text/plain","text/html","application/xhtml+xml"}:
                            raise ValueError("This page requires a format the private reader cannot display.")
                        data=response.read(LIMIT+1)
                        if len(data)>LIMIT:raise ValueError("Page exceeds the private reader’s 3 MB limit.")
                        try:text=data.decode(response.headers.get_content_charset() or "utf-8","replace")
                        except LookupError:text=data.decode("utf-8","replace")
                        if mime=="text/plain":return url,"<pre>"+escape(text)+"</pre>"
                        reader=Reader(url,lambda src:self.remember_image(path,src));reader.feed(text);reader.close()
                        return url,"".join(reader.parts)
        raise ValueError("The website redirected too many times.")

def screen(session, token, url="", article="", message=""):
    status, ready = session.status()
    launch = f"/private-open?port={session.proxy.server_port}" if ready and session.proxy else "/private-open"
    hidden = f'<input type=hidden name=token value="{escape(token,quote=True)}">'
    options = "".join(f'<option value="{code}"{" selected" if code==session.location else ""}>{name}</option>'
                      for code,name in COUNTRIES.items())
    connecting = session.process is not None and session.process.poll() is None and not ready
    return (f'<section><form method=post action="/private-browser" class="private-browser-controls">{hidden}'
            f'<label>Exit location<select name=country>{options}</select></label><button name=action value=connect>Connect</button>'
            f'<button name=action value=disconnect>Disconnect</button></form>'
            f'<p id=private-status data-connecting="{int(connecting)}" role=status>{escape(status)}</p>'
            '<small>Only this browser uses Tor. Choosing a country narrows the pool of exits. Signing in can identify you to a site.</small></section>'
            f'<p><a class="native-browser-launch" id=native-browser-launch href="{launch}" aria-disabled="{str(not ready).lower()}">Open private browser →</a></p>')
