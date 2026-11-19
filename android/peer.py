"""Paired Android library transfer. The dashboard remains loopback-only."""
import hashlib
import hmac
import os
import secrets
import re
import shutil
import sqlite3
import ssl
import tempfile
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from threading import Thread, Lock
from urllib.parse import unquote, urlsplit
import json

PORT = 38779
TYPES = {".txt", ".pdf", ".zim", ".pmtiles", ".js", ".css", ".json", ".pbf", ".png", ".jpg", ".html", ".wasm", ".mp3", ".ogg", ".wav", ".m4a", ".mp4", ".m4v", ".webm", ".ogv", ".epub", ".zip"}


def portable(name):
    parts = PurePosixPath(name).parts
    if not parts or name.startswith("/") or ".." in parts or "\x00" in name:
        return False
    if len(parts)==2 and parts[0]=="Publisher artwork" and re.fullmatch("[a-f0-9]{64}",parts[1]):return True
    if len(parts)==2 and parts[0]=="Content" and re.fullmatch(r"personal-[a-f0-9]{64}\.[a-z0-9]{1,12}",parts[1]):
        return True
    if len(parts)==2 and parts[0]=="Content" and re.fullmatch(r"[a-f0-9]{64}(?:-[0-9]+)?(?:\.tar\.(?:gz|bz2|xz)|\.[a-z0-9]{1,12})",parts[1]):
        return True
    if name in {"desktop.sqlite3", "library/dictionary.sqlite3"}:
        return True
    return (len(parts) == 2 and parts[0] == "Content" or len(parts) >= 3 and parts[0] == "Kit"
            and parts[1] in {"02-Reference","03-Maps","04-Entertainment"}) and PurePosixPath(name).suffix.lower() in TYPES


def serve(root, pair, credentials):
    root=root.resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization",""), "Bearer " + pair["token"])

        def respond(self, data):
            self.send_response(200)
            self.send_header("Content-Length",str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_file(self, file):
            with file.open("rb") as stream:
                self.send_response(200)
                self.send_header("Content-Length",str(os.fstat(stream.fileno()).st_size))
                self.end_headers()
                shutil.copyfileobj(stream,self.wfile,1024*1024)

        def asset(self):
            name = unquote(urlsplit(self.path).path.removeprefix("/file/"))
            target = (root/name).resolve()
            return target if self.path.startswith("/file/") and portable(name) and target.is_relative_to(root) else None

        def do_GET(self):
            if not self.authorized():
                return self.send_error(403)
            if self.path == "/status":
                return self.respond(b"EchoOffGrid")
            if self.path == "/revision":
                from merge import revision
                return self.respond(revision(root/"archive.sqlite3").encode())
            if self.path == "/inventory":
                inventory={}
                for base,dirs,names in os.walk(root):
                    for name in names:
                        asset=Path(base)/name
                        rel=asset.relative_to(root).as_posix()
                        if portable(rel):
                            stat=asset.stat()
                            inventory[rel]=[stat.st_size,stat.st_mtime_ns]
                return self.respond(json.dumps(inventory).encode())
            if self.path.startswith("/checksum/"):
                name=unquote(self.path[len("/checksum/"):])
                if not portable(name):
                    return self.send_error(400)
                asset=(root/name).resolve()
                if not asset.is_relative_to(root) or not asset.is_file():
                    return self.send_error(404)
                h=hashlib.sha256()
                with asset.open("rb") as stream:
                    for block in iter(lambda: stream.read(2**20),b""):
                        h.update(block)
                return self.respond(h.hexdigest().encode())
            if self.path in ("/content","/content?target=macos"):
                folder=root/"Content"
                from compatibility import ContentPolicy
                policy=ContentPolicy(folder,root/"archive.sqlite3")
                return self.respond(json.dumps([p.name for p in folder.glob("*") if portable("Content/"+p.name) and policy.allows(p.name,"macos")]).encode())
            if self.path == "/snapshot":
                with tempfile.TemporaryDirectory(dir=root) as temp:
                    path=Path(temp)/"copy.sqlite3"
                    with closing(sqlite3.connect(root/"archive.sqlite3")) as source, closing(sqlite3.connect(path)) as dest:
                        source.backup(dest)
                    return self.send_file(path)
            asset=self.asset()
            if asset and asset.is_file():
                return self.send_file(asset)
            self.send_error(404)

        def do_HEAD(self):
            if not self.authorized():
                return self.send_error(403)
            asset=self.asset()
            if not asset or not asset.is_file():
                return self.send_error(404)
            stat=asset.stat()
            with lock:
                record=known.get(str(asset))
            self.send_response(200)
            self.send_header("Content-Length",str(stat.st_size))
            if record and record[:2]==[stat.st_size,stat.st_mtime_ns]:
                self.send_header("ETag",record[2])
            self.end_headers()

        def do_PUT(self):
            if not self.authorized():
                return self.send_error(403)
            asset=self.asset()
            if not asset:
                return self.send_error(400)
            digest=self.headers.get("X-SHA256","")
            try:
                length=int(self.headers["Content-Length"])
            except (ValueError,TypeError):
                return self.send_error(411)
            if len(digest)!=64 or length<0 or length>shutil.disk_usage(root).free-16*1024**2:
                return self.send_error(507)
            asset.parent.mkdir(parents=True,exist_ok=True)
            tmp=asset.with_name(asset.name+"."+secrets.token_hex(8)+".partial")
            try:
                hashed=hashlib.sha256()
                with tmp.open("xb") as out:
                    remaining=length
                    while remaining:
                        block=self.rfile.read(min(1024**2,remaining))
                        if not block:
                            return self.send_error(400)
                        out.write(block)
                        hashed.update(block)
                        remaining-=len(block)
                if hashed.hexdigest()!=digest:
                    return self.send_error(422)
                os.replace(tmp,asset)
                stat=asset.stat()
                with lock:
                    known[str(asset)]=[stat.st_size,stat.st_mtime_ns,digest]
                return self.respond(b"Saved")
            finally:
                tmp.unlink(missing_ok=True)

    lock=Lock()
    known={}
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version=ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(credentials/"cert.pem",credentials/"key.pem")
    class Listener(ThreadingHTTPServer):
        def finish_request(self, sock, address):
            sock.settimeout(20)
            try:
                with tls.wrap_socket(sock,server_side=True) as secure:
                    secure.settimeout(300)
                    self.RequestHandlerClass(secure,address,self)
            except (OSError,TimeoutError):
                return
    listener=Listener(("",PORT),Handler)
    Thread(target=listener.serve_forever,daemon=True).start()
    return listener
