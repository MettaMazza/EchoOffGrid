"""Pair one Mac to one EchoOffGrid installation using an already trusted USB connection."""
import argparse
from pathlib import Path
import json
import os
import secrets
import subprocess
import tempfile

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb",default="adb")
    parser.add_argument("--serial",required=True)
    parser.add_argument("--profile",type=Path,required=True)
    args=parser.parse_args()
    if args.profile.exists():
        parser.error("Choose a new pairing profile")
    adb=[args.adb,"-s",args.serial]
    token=secrets.token_urlsafe(48)
    remote="/sdcard/Android/data/dev.echooffgrid.mobile/files/pairing"
    with tempfile.TemporaryDirectory() as temp:
        base=Path(temp)
        subprocess.run(["openssl","req","-x509","-newkey","rsa:3072","-nodes","-days","365",
                        "-subj","/CN=EchoOffGrid Companion","-keyout",str(base/"key.pem"),"-out",str(base/"cert.pem")],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        bundle=base/"pairing.json"
        bundle.write_text(json.dumps({"token":token,"cert":(base/"cert.pem").read_text(),"key":(base/"key.pem").read_text()}))
        root=remote.rsplit("/",1)[0]
        subprocess.run(adb+["push",str(bundle),root+"/pairing.pending"],check=True)
        subprocess.run(adb+["shell","mv",root+"/pairing.pending",root+"/pairing.json"],check=True)
        args.profile.parent.mkdir(parents=True,exist_ok=True)
        with os.fdopen(os.open(args.profile,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),"w") as profile:
            json.dump({"token":token,"cert":(base/"cert.pem").read_text()},profile)

if __name__=="__main__":
    main()
