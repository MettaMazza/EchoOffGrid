"""Synchronize a paired phone over authenticated USB forwarding or the local network."""
import json
import hashlib
import re
from pathlib import Path
import subprocess
import sys
import time
from http.client import HTTPException
import sqlite3
from contextlib import contextmanager
from wifi import Companion, PORT

@contextmanager
def endpoint(config):
    adb=[config["adb"],"-s",config["serial"]]
    port=None
    try:
        try:
            result=subprocess.run(adb+["get-state"],capture_output=True,text=True,timeout=4)
            if result.stdout.strip()=="device":
                forward=subprocess.run(adb+["forward","tcp:0","tcp:"+str(PORT)],check=True,capture_output=True,text=True,timeout=5)
                port=int(forward.stdout.strip())
        except (OSError,subprocess.SubprocessError,ValueError):
            pass
        if port:
            yield "127.0.0.1",port
        else:
            yield config["host"],PORT
    finally:
        if port:
            subprocess.run(adb+["forward","--remove","tcp:"+str(port)],capture_output=True,timeout=5)

def discover(token):
    name="EchoOffGrid-"+hashlib.sha256(token.encode()).hexdigest()[:12]
    try:
        output=subprocess.run(["/usr/bin/dns-sd","-L",name,"_echooffgrid._tcp","local."],
                              capture_output=True,timeout=2).stdout
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or b""
    match=re.search(rb"can be reached at ([a-zA-Z0-9.-]+\.local\.):([0-9]+)",output)
    return match.group(1).decode() if match and int(match.group(2))==PORT else None


def run(folder):
    config=json.loads((folder/"connection.json").read_text())
    profile=json.loads((folder/"pair.json").read_text())
    status=folder/"status.json"
    def report(state):
        temp=status.with_suffix(".tmp")
        temp.write_text(json.dumps({"state":state,"checked":int(time.time())}))
        temp.replace(status)
    while True:
        try:
            with endpoint(config) as (host,port):
                if host!="127.0.0.1":
                    host=discover(profile["token"]) or host
                peer=Companion(host,port,profile,folder/"inventory.json")
                report("Checking paired phone")
                peer.sync(Path(config["kit"]),Path(config["archive"]),Path(config["dictionary"]) if config.get("dictionary") else None)
                report("Up to date")
            time.sleep(120)
        except (OSError,HTTPException,sqlite3.Error,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            report("Waiting for phone" if isinstance(exc,OSError) else "Sync needs attention")
            print(type(exc).__name__,str(exc)[:200],file=sys.stderr,flush=True)
            time.sleep(20)

if __name__=="__main__":
    run(Path(sys.argv[1]))
