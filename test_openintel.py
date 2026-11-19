import json
from pathlib import Path
import tempfile
import time
import unittest
from contextlib import closing
from unittest.mock import patch

from intel import providers
from intel.service import Intel, connect


class OpenIntelTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.archive = Path(folder.name) / "library.sqlite3"
        self.service = Intel(self.archive)
        self.addCleanup(self.service.close)

    def test_replay_save_and_reopen_without_network(self):
        now = int(time.time())
        rows = [providers.observation("air", "test", "Test aircraft", 57, x, now-dt, "test")
                for x, dt in [(-2, 120), (-1.9, 60)]]
        for row in rows:
            self.service.store("aberdeen", row)
        self.assertEqual(self.service.view("aberdeen", now-100)["rows"][0]["id"], rows[0]["id"])
        self.assertEqual(len(self.service.view("aberdeen")["rows"][0]["trail"]), 2)
        self.service.save("aberdeen", rows[0]["id"], now)
        self.assertIn("item=", self.service.home())
        with closing(connect(self.service.path)) as db, db:
            db.execute("UPDATE obs SET received=1")
            self.service.trim(db)
        second = Intel(self.archive)
        self.addCleanup(second.close)
        with patch("intel.providers.fetch", side_effect=AssertionError):
            self.assertFalse(second.view("aberdeen")["rows"])
            self.assertEqual(second.view("aberdeen", saved=True)["rows"][0]["id"], rows[0]["id"])
            self.assertTrue(second.view("finland", sample=True)["rows"])

    def test_invalid_receiver_file_is_atomic(self):
        feature = dict(geometry=dict(type="Point", coordinates=[-2,57]),
                       properties=dict(title="Test", time="2024-06-15T11:00:00Z"))
        with self.assertRaises(ValueError):
            self.service.local("aberdeen", json.dumps(dict(features=[feature,None])))
        self.assertFalse(self.service.view("aberdeen")["rows"])
        self.assertEqual(self.service.local("aberdeen",json.dumps(dict(features=[feature]))),1)

    def test_saved_picture_survives_companion_merge(self):
        from android.merge import merge, revision
        peer_dir = self.archive.parent / "peer"
        peer_dir.mkdir()
        peer = Intel(peer_dir / "archive.sqlite3")
        self.addCleanup(peer.close)
        before = revision(peer.archive)
        row = providers.observation("cams","demo","Demo camera",60,24,int(time.time()),"Snapshot")
        self.service.store("finland",row,b"offline picture")
        self.service.save("finland",row["id"],row["time"])
        merge(peer.archive,self.archive)
        merge(peer.archive,self.archive)
        self.assertNotEqual(before, revision(peer.archive))
        self.assertEqual(len(peer.view("finland",saved=True)["rows"]),1)
        self.assertEqual(peer.media(row["id"]),b"offline picture")
        self.assertFalse(peer.view("finland")["rows"])

    def test_rate_limit_and_cooldown(self):
        from urllib.error import HTTPError
        err = HTTPError("https://example.org", 429, "", {"Retry-After":"4200"}, None)
        with patch("intel.providers.aircraft", side_effect=err) as provider:
            self.service.refresh("aberdeen",["air"])
            self.service.pool.shutdown(wait=True)
            self.service.refresh("aberdeen",["air"])
            self.assertEqual(provider.call_count,1)
        status=self.service.status("aberdeen")["air"]
        self.assertIn("429",status["note"])
        self.assertGreaterEqual(status["next"]-status["attempt"],4200)

    def test_ais_subscription_parses_and_closes(self):
        from unittest.mock import MagicMock
        stream=MagicMock()
        stream.recv.side_effect=[json.dumps({
            "MetaData":{"MMSI":123,"ShipName":"Demo","time_utc":"2024-06-15 10:02:03.111 +0000 UTC","latitude":57,"longitude":-2},
            "Message":{"PositionReport":{"Sog":4,"Cog":120}}}),TimeoutError()]
        with patch("websockets.sync.client.connect",return_value=stream):
            rows=list(providers.ais_live("aberdeen","test-key"))
        self.assertEqual([r["title"] for r in rows],["Demo"])
        self.assertIn("BoundingBoxes",json.loads(stream.send.call_args.args[0]))
        stream.close.assert_called_once()

    def test_restricted_live_vessel_cannot_be_saved(self):
        now = int(time.time())
        row = providers.observation("ais","test","Test",57,-2,now,"")
        self.service.live_ais["aberdeen"] = (now,[row])
        self.assertEqual(self.service.view("aberdeen")["rows"][0]["id"],row["id"])
        with self.assertRaises(ValueError):
            self.service.save("aberdeen",row["id"],now)
        self.assertFalse(self.service.view("aberdeen",now-1)["rows"])
