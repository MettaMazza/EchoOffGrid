"""Install a login item for a Mac already paired over USB."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
for name in ("profile","kit","archive","adb"):
    parser.add_argument("--"+name,type=Path,required=True)
parser.add_argument("--dictionary",type=Path)
parser.add_argument("--host",required=True)
parser.add_argument("--serial",required=True)
args=parser.parse_args()
base=Path.home()/"Library/Application Support/EchoOffGrid/Android"
base.mkdir(parents=True,exist_ok=True,mode=0o700)
for name in ("auto_sync.py","storage_policy.py","compatibility.py","wifi.py","merge.py","peer.py"):
    shutil.copy2(Path(__file__).with_name(name),base/name)
shutil.copy2(args.profile,base/"pair.json")
(base/"pair.json").chmod(0o600)
config={name:str(value.resolve()) if isinstance(value,Path) else value for name,value in vars(args).items() if name!="profile"}
(base/"connection.json").write_text(json.dumps(config))
label="local.echooffgrid.companion-sync"
agents=Path.home()/"Library/LaunchAgents"
agents.mkdir(exist_ok=True)
plist=agents/(label+".plist")
domain="gui/"+str(os.getuid())
if plist.exists():
    subprocess.run(["launchctl","bootout",domain+"/"+label],capture_output=True)
with plist.open("wb") as stream:
    plistlib.dump({"Label":label,"ProgramArguments":[sys.executable,"-B",str(base/"auto_sync.py"),str(base)],
                   "RunAtLoad":True,"KeepAlive":True,"ThrottleInterval":30,
                   "StandardErrorPath":str(base/"sync.log")},stream)
subprocess.run(["launchctl","bootstrap",domain,str(plist)],check=True)
