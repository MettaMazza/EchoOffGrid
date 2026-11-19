"""Exercise platform selection through both directions of the paired TLS protocol."""
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import peer
from wifi import Companion
from merge import merge

class PlatformSync(unittest.TestCase):
    @patch("storage_policy.shutil.disk_usage", return_value=SimpleNamespace(free=100 * 10**9))
    def test_native_packages_and_portable_media(self, _disk_usage):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            mac,phone=base/"mac",base/"phone"
            for device in (mac,phone):
                (device/"Content").mkdir(parents=True)
                with sqlite3.connect(device/"archive.sqlite3") as db:
                    db.execute("CREATE TABLE discovery_item(id PRIMARY KEY,kind,title,preview,rights,url,ext,provider,filename)")
                    db.execute("CREATE TABLE discovery_file(id,sequence,title,filename,PRIMARY KEY(id,sequence))")
            def fixture(device,kind,title,extension,entries=()):
                key="personal-"+secrets.token_hex(32)
                name=key+extension
                path=device/"Content"/name
                if entries:
                    with ZipFile(path,"w") as z:
                        for entry in entries:z.writestr(entry,b"fixture")
                else:path.write_bytes(b"fixture")
                (device/"Content"/(key+".cover")).write_bytes(b"art")
                with sqlite3.connect(device/"archive.sqlite3") as db:
                    db.execute("INSERT INTO discovery_item VALUES(?,?,?,?,?,?,?,?,?)",(key,kind,title,"","","",extension,"Personal library",name))
                return name
            bundle=fixture(mac,"Emulators","Mac emulator",".zip",["Emulator.app/Contents/MacOS/Emulator"])
            apk=fixture(phone,"Emulators","Android emulator",".apk",["AndroidManifest.xml","lib/arm64-v8a/app.so"])
            x86=fixture(mac,"Games","x86 app",".apk",["AndroidManifest.xml","lib/x86/app.so"])
            rom=fixture(mac,"Games","ROM",".gba")
            book=fixture(phone,"Books","Book",".txt")
            subprocess.run(["openssl","req","-x509","-newkey","rsa:2048","-nodes","-days","1","-subj","/CN=localhost",
                            "-keyout",str(base/"key.pem"),"-out",str(base/"cert.pem")],check=True,capture_output=True)
            profile={"token":secrets.token_hex(32),"cert":(base/"cert.pem").read_text()}
            with patch.object(peer,"PORT",0):
                server=peer.serve(phone,profile,base)
            try:
                link=Companion("127.0.0.1",server.server_port,profile)
                link.sync(base/"kit",mac/"archive.sqlite3",None)
                merge(phone/"archive.sqlite3",phone/"desktop.sqlite3")
                for device,absent,present in [(phone,[bundle,x86],[rom]),(mac,[apk],[book])]:
                    with sqlite3.connect(device/"archive.sqlite3") as db:
                        saved={r[0] for r in db.execute("SELECT filename FROM discovery_item WHERE filename IS NOT NULL")}
                    for name in absent+present:
                        expected=name in present
                        self.assertEqual((device/"Content"/name).exists(),expected)
                        self.assertEqual((device/"Content"/Path(name).with_suffix(".cover")).exists(),expected)
                        self.assertEqual(name in saved,expected)
            finally:
                server.shutdown();server.server_close()

if __name__=="__main__":unittest.main()
