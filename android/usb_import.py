"""Adopt verified USB-seeded files into directories owned by the Android application."""
import argparse
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import tempfile
from peer import portable

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb",default="adb")
    p.add_argument("--serial",required=True)
    args=p.parse_args()
    adb=[args.adb,"-s",args.serial]
    root="/sdcard/Android/data/dev.echooffgrid.mobile/files/"
    paths=("Kit","library","Content")
    entries=subprocess.run(adb+["exec-out","find",*(root+x for x in paths),"-type","f","-print0"],
                           capture_output=True,check=False).stdout.decode().split("\0")
    job=secrets.token_hex(12)
    manifest=[]
    moves=["set -e"]
    for path in entries:
        if not path.startswith(root):
            continue
        name=path[len(root):]
        if not portable(name) or any(p.endswith(".app") for p in Path(name).parts):
            continue
        slot=job+"-"+str(len(manifest))
        manifest.append([slot,name])
        moves.append("mv "+shlex.quote(path)+" "+shlex.quote(root+"incoming/"+slot))
    if not manifest:
        return
    with tempfile.TemporaryDirectory() as tmp:
        manifest_file=Path(tmp)/"manifest.json"
        manifest_file.write_text(json.dumps(manifest))
        target=root+"incoming/"+job
        subprocess.run(adb+["push",str(manifest_file),target+".pending"],check=True)
        moves.append("mv "+shlex.quote(target+".pending")+" "+shlex.quote(target+".json"))
        subprocess.run(adb+["shell","sh","-s"],input="\n".join(moves)+"\n",text=True,check=True)
        print("Submitted",len(manifest),"verified files to the Android library.")

if __name__=="__main__":
    main()
