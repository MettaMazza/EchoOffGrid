import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import dashboard
import discovery


class SeriesRecovery(unittest.TestCase):
    def test_recover_episode_order_and_remove_only_selected_title(self):
        key = "a" * 64
        other = "b" * 64
        episodes = {"Show S01E10.mp4": b"existing episode ten",
                    "Show S01E02.mkv": b"two", "Show S01E01.mp4": b"one"}
        manifest = {"metadata": {"licenseurl": "public"},
                    "files": [{"name": name, "size": str(len(data)), "sha1": hashlib.sha1(data).hexdigest()}
                              for name, data in episodes.items()]}
        manifest["files"].append({"name": "Show S01E10.webm", "original": "Show S01E10.mp4", "size": "10"})
        with tempfile.TemporaryDirectory() as folder, closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            discovery.init(db)
            for table in ("download_backoff","content_download"):
                db.execute(f"CREATE TABLE {table}(source TEXT)")
            root = Path(folder)
            legacy = root / (key + ".mp4")
            legacy.write_bytes(episodes["Show S01E10.mp4"])
            inode = legacy.stat().st_ino
            db.execute("INSERT INTO discovery_item VALUES(?,?,?,?,?,?,?,?,?)",
                       (key,"Films","A series","","public","https://archive.org/metadata/example","","Internet Archive",legacy.name))
            db.execute("INSERT INTO discovery_file VALUES(?,?,?,?)",(key,0,"Show S01E10.mp4",legacy.name))
            item = db.execute("SELECT * FROM discovery_item").fetchone()
            fetched = []
            def save(path, url, *args):
                from urllib.parse import unquote
                title = unquote(url.rsplit("/",1)[1])
                fetched.append(title)
                path.write_bytes(episodes[title])
            with patch.object(discovery,"metadata",return_value=manifest), patch.object(discovery,"transfer",side_effect=save):
                while discovery.download(db,root,item) is False:
                    pass
            self.assertEqual(fetched, ["Show S01E01.mp4","Show S01E02.mkv"])
            self.assertEqual(legacy.stat().st_ino,inode)
            self.assertEqual([r[0] for r in db.execute("SELECT title FROM discovery_file ORDER BY sequence")],
                             ["Show S01E01.mp4","Show S01E02.mkv","Show S01E10.mp4"])
            (root/(key+".mp4.part")).write_bytes(b"partial")
            unrelated = root/(other+".mp4")
            unrelated.write_bytes(b"keep")
            dashboard.Downloads.remove_local(db,root,key)
            self.assertFalse(list(root.glob(key+"*")))
            self.assertEqual(unrelated.read_bytes(), b"keep")
            self.assertIsNone(db.execute("SELECT filename FROM discovery_item WHERE id=?",(key,)).fetchone()[0])

    def test_resumes_from_verified_range(self):
        class Reply(BytesIO):
            status = 206
            headers = {"Content-Range": "bytes 3-5/6"}
        def open_range(req,timeout):
            self.assertEqual(req.get_header("Range"), "bytes=3-")
            return Reply(b"def")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"episode.mp4"
            target.with_suffix(".mp4.part").write_bytes(b"abc")
            with patch.object(discovery,"urlopen",open_range):
                discovery.transfer(target,"https://example.org/episode",6,hashlib.sha1(b"abcdef").hexdigest(),None,lambda *_:None)
            self.assertEqual(target.read_bytes(),b"abcdef")
