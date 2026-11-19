"""Sync portable library files and merge saved material between two paired workstations."""
import argparse
from contextlib import closing
import hashlib
from http.client import HTTPSConnection
import json
import os
from pathlib import Path
import shutil
import sqlite3
import ssl
import tempfile
import time
from urllib.parse import quote

from compatibility import ContentPolicy,targets
from merge import merge, revision
from peer import PORT, portable


def checksum(path):
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


class Companion:
    def __init__(self, host, port, pairing, state=None):
        self.host, self.port = host, port
        self.state=state
        self.cache=json.loads(state.read_text()) if state and state.exists() else {}
        self.inventory=None
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.load_verify_locations(cadata=pairing["cert"])
        # The unique certificate was enrolled over USB. The phone's DHCP address can change.
        self.context.check_hostname = False
        self.headers = {"Authorization":"Bearer "+pairing["token"]}

    def request(self, method, path, data=None, headers=None):
        conn=HTTPSConnection(self.host,self.port,timeout=5,context=self.context)
        try:
            conn.connect()
            conn.sock.settimeout(900)
            conn.request(method,path,data,headers={**self.headers,**(headers or {})})
            return conn.getresponse()
        except BaseException:
            conn.close()
            raise

    def send(self, file, name):
        if not portable(name):
            raise ValueError("Unsupported sync destination")
        endpoint="/file/"+quote(name)
        size=file.stat().st_size
        local=[size,file.stat().st_mtime_ns]
        remote=(self.inventory or {}).get(name)
        if remote and self.cache.get(name)==[local,remote]:
            return
        digest=checksum(file)
        if remote and remote[0]==size:
            with self.request("GET","/checksum/"+quote(name)) as checked:
                if checked.status==200 and checked.read().decode()==digest:
                    self.cache[name]=[local,remote]
                    return
        with file.open("rb") as data, self.request("PUT",endpoint,data,{"Content-Length":str(size),"X-SHA256":digest}) as response:
            if response.status!=200:
                raise RuntimeError(f"{name}: HTTP {response.status}")
            response.read()
        print("Saved on phone:",name, flush=True)

    def fetch(self, route, dest):
        with self.request("GET",route) as response:
            if response.status!=200:
                raise RuntimeError(f"{route}: HTTP {response.status}")
            expected=int(response.getheader("Content-Length"))
            with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as stream:
                partial=Path(stream.name)
                try:
                    shutil.copyfileobj(response,stream,2**20)
                    if stream.tell()!=expected:
                        raise IOError("Incomplete sync")
                    stream.close()
                    partial.replace(dest)
                finally:
                    partial.unlink(missing_ok=True)

    def sync(self, kit, archive, dictionary):
        with self.request("GET","/inventory") as response:
            if response.status!=200:
                raise RuntimeError("Could not read paired library inventory")
            self.inventory=json.load(response)
        for group in ("02-Reference","03-Maps","04-Entertainment"):
            for base, dirs, names in os.walk(kit/group):
                dirs[:]=[d for d in dirs if not d.endswith(".app") and not (Path(base)/d).is_symlink()]
                for name in sorted(names):
                    p=Path(base)/name
                    target="Kit/"+p.relative_to(kit).as_posix()
                    if portable(target) and p.is_file() and not p.is_symlink():
                        if p.suffix.lower()==".zip" and "android" not in targets(p,p.stat().st_mtime_ns,p.stat().st_size,"",""):continue
                        self.send(p,target)
        if dictionary:
            self.send(dictionary,"library/dictionary.sqlite3")
        if self.state:
            temp=self.state.with_suffix(".pending")
            temp.write_text(json.dumps(self.cache))
            temp.replace(self.state)
        if not archive:
            return
        artwork=archive.parent/"Publisher artwork"
        artwork.mkdir(exist_ok=True)
        for name in self.inventory:
            if name.startswith("Publisher artwork/") and portable(name) and not (archive.parent/name).exists():
                self.fetch("/file/"+quote(name),archive.parent/name)
        for art in artwork.iterdir():
            name="Publisher artwork/"+art.name
            if art.is_file() and not art.is_symlink() and portable(name):self.send(art,name)
        content=archive.parent/"Content"
        content.mkdir(exist_ok=True)
        with self.request("GET","/content?target=macos") as response:
            if response.status!=200:
                raise RuntimeError("Could not load phone inventory")
            remote=json.load(response)
        for name in remote:
            if Path(name).name!=name or not portable("Content/"+name):
                raise ValueError("Invalid portable filename")
            if not (content/name).exists():
                self.fetch("/file/Content/"+quote(name),content/name)
        policy=ContentPolicy(content,archive)
        for p in content.iterdir():
            if p.is_file() and not p.is_symlink() and portable("Content/"+p.name) and policy.allows(p.name,"android"):
                self.send(p,"Content/"+p.name)
        with self.request("GET","/revision") as response:
            if response.status!=200:
                raise RuntimeError("Could not check the phone archive")
            remote_version=response.read().decode()
        local_version=revision(archive)
        revisions=[local_version,remote_version]
        if self.cache.get("@archive")==revisions:
            return
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=Path(tmp)/"phone.sqlite3"
            self.fetch("/snapshot",snapshot)
            merge(archive,snapshot)
            dest=Path(tmp)/"desktop.sqlite3"
            with closing(sqlite3.connect(archive.resolve().as_uri()+"?mode=ro",uri=True)) as source, closing(sqlite3.connect(dest)) as target:
                source.backup(target)
            self.send(dest,"desktop.sqlite3")
            self.cache["@archive"]=[revision(archive),remote_version]
            if self.state:
                temp=self.state.with_suffix(".pending")
                temp.write_text(json.dumps(self.cache))
                temp.replace(self.state)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host",required=True)
    parser.add_argument("--port",type=int,default=PORT)
    parser.add_argument("--profile",required=True,type=Path)
    parser.add_argument("--kit",required=True,type=Path)
    parser.add_argument("--archive",type=Path)
    parser.add_argument("--dictionary",type=Path)
    parser.add_argument("--watch",action="store_true",help="Repeat sync when the paired device is reachable")
    args=parser.parse_args()
    peer=Companion(args.host,args.port,json.loads(args.profile.read_text()),args.profile.with_suffix(".inventory"))
    while True:
        try:
            peer.sync(args.kit,args.archive,args.dictionary)
        except OSError as exc:
            if not args.watch:
                raise
            print("Waiting for phone:",exc,flush=True)
        if not args.watch:
            break
        time.sleep(120)

if __name__=="__main__":
    main()
