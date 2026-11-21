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

    def test_corrected_observation_retains_both_versions(self):
        first = providers.observation("buoys", "station", "Wave height", 57, -2, int(time.time()), "2.1 m")
        corrected = dict(first, detail="1.2 m")
        for row in (first, corrected, corrected):
            self.service.store("aberdeen", row)
        with closing(connect(self.service.path)) as db:
            versions = [json.loads(r[0]) for r in db.execute("SELECT body FROM obs ORDER BY rowid")]
        self.assertEqual([r["detail"] for r in versions], ["2.1 m", "1.2 m"])
        self.assertEqual(versions[1]["revises"], first["id"])

    def test_region_coverage_uses_observation_time_and_saved_records(self):
        from datetime import datetime, timezone
        stamp = int(datetime(2020, 1, 2, 10, tzinfo=timezone.utc).timestamp())
        for minutes in (0, 30, 120):
            report = providers.observation("buoys", "station", "Wave height", 57, -2,
                                           stamp + minutes * 60, "2.1 m")
            self.service.store("aberdeen", report)
            if minutes != 120:
                self.service.save("aberdeen", report["id"], stamp)
            if minutes == 30:
                with closing(connect(self.service.path)) as db, db:
                    db.execute("DELETE FROM obs WHERE id=?", (report["id"],))
            self.service.store("world", report)
        window = ("2020-01-02T10:00", "2020-01-02T12:00")
        rows = self.service.coverage("aberdeen", *window)["sources"]
        self.assertEqual([(r["source"], r["count"], r["last"]) for r in rows if r["count"]],
                         [("buoys", 2, stamp + 1800)])
        self.assertFalse(any(r["count"] for r in self.service.coverage("finland", *window)["sources"]))
        with self.assertRaises(ValueError):
            self.service.coverage("aberdeen", *reversed(window))

    def test_browser_capture_preserves_rendered_material_and_citations(self):
        import base64
        from intel import cases
        from zipfile import ZipFile
        owner=cases.create(self.service,"Port records")
        photo=(Path(cases.__file__).parent/"previews/terra.jpg").read_bytes()
        page=dict(url="https://example.org/harbour",title="Harbour archive",captured="2026-01-02T15:00:00Z",
                  html="<html><p>Harbour works</p></html>",text="Harbour works",viewport=base64.b64encode(photo).decode())
        for _ in range(2):
            self.assertEqual(cases.capture_page(self.service,owner,page)["count"],3)
        with self.assertRaises(ValueError):
            cases.capture_page(self.service,owner,dict(page,url="file:///private"))
        with self.assertRaises(ValueError):
            cases.capture_page(self.service,owner,dict(page,viewport="invalid!"))
        with cases.export(self.service,owner) as stream,ZipFile(stream) as export:
            rows=json.loads(export.read("manifest.json"))["exhibits"]
            self.assertEqual(len(rows),3)
            expected={"Browser viewport":photo,"Rendered HTML":page["html"].encode(),"Rendered page text":page["text"].encode()}
            for row in rows:
                self.assertEqual(export.read(row["file"]),expected[row["material"]])
                self.assertEqual(row["url"],page["url"])
                self.assertEqual(row["date_utc"],"2026-01-02T15:00:00+00:00")

    def test_landmark_clues_and_original_case_capture(self):
        from intel import cases, places
        element = dict(type="way", id=1, version=4, timestamp="2020-06-01T00:00:00Z",
                       center=dict(lat=57.14,lon=-2.08), tags=dict(name="North Pier",man_made="pier"))
        payload = json.dumps(dict(elements=[element]),indent=2).encode()
        with patch.object(providers,"fetch",return_value=payload):
            places.acquire(self.service,"aberdeen")
        rows = places.search(self.service,"aberdeen","pier north")
        self.assertEqual(rows["count"],1)
        self.assertTrue(rows["rows"][0]["centre"])
        self.assertFalse(places.search(self.service,"finland","pier")["rows"])
        owner = cases.create(self.service,"Harbour")
        cases.attach_landmark(self.service,owner,"aberdeen","way/1",rows["digest"])
        with patch.object(providers,"fetch",return_value=b'{"remark":"timed out","elements":[]}'):
            with self.assertRaises(ValueError):
                places.acquire(self.service,"aberdeen")
        self.assertEqual(places.search(self.service,"aberdeen","")["digest"],rows["digest"])
        with closing(connect(self.service.path)) as db,db:
            db.execute("DELETE FROM landmark_pack")
        with self.assertRaises(ValueError):
            cases.attach_landmark(self.service,owner,"aberdeen","way/1",rows["digest"])
        exhibit = cases.listing(self.service,owner)["items"][0]
        self.assertEqual(cases.exhibit_original(self.service,owner,exhibit["ref"]),payload)
        self.assertEqual(exhibit["basis"],"Map edit")
        self.assertEqual(exhibit["feature_version"],4)

    def test_track_pages_include_archived_reports_and_boundary_gap(self):
        stamp = 1600000000
        for index in range(52):
            row = providers.observation("ships", "123", "Vessel 123", 60, 24,
                                        stamp + index * 60 + (1800 if index >= 2 else 0),
                                        "Docked")
            self.service.store("finland", row)
            if index <= 1:
                self.service.save("finland", row["id"], row["time"])
            if index == 0:
                with closing(connect(self.service.path)) as db, db:
                    db.execute("DELETE FROM obs WHERE id=?", (row["id"],))
        query = ("finland", "ships", "123", stamp + 86400)
        first = self.service.track_history(*query)
        self.assertTrue(first["more"])
        self.assertEqual(first["rows"][-1]["interval"], 1860)
        older = self.service.track_history(*query, 1)
        self.assertEqual([r["time"] for r in older["rows"]], [stamp + 60, stamp])
        self.assertTrue(all(r["received"] for r in older["rows"]))
        self.assertFalse(older["more"])
        self.assertEqual(len(self.service.track_history(*query[:3], stamp)["rows"]), 1)
        self.assertFalse(self.service.track_history("aberdeen", *query[1:])["rows"])
        with self.assertRaises(ValueError):
            self.service.track_history("finland", "ais", "123", stamp)

    def test_compare_saved_composites_after_cache_expiry(self):
        from intel import visuals
        payload = (Path(visuals.__file__).parent / "previews" / "terra.jpg").read_bytes()
        for day in ("2020-01-02", "2020-01-03"):
            row = providers.image_row("aberdeen", day)
            original = row.pop("image_url")
            self.service.store("aberdeen", row, payload)
            self.service.save("aberdeen", row["id"], row["time"])
            with closing(connect(self.service.path)) as db, db:
                db.execute("DELETE FROM obs")
            found = visuals.local_composite(self.service, "terra", "aberdeen", day)
            self.assertEqual((found["day"], found["url"], found["bounds"]),
                             (day, original, row["bounds"]))
            self.assertEqual(self.service.media(found["id"]), payload)
            self.assertIsNone(visuals.local_composite(self.service, "aqua", "aberdeen", day))
            self.assertIsNone(visuals.local_composite(self.service, "terra", "finland", day))
        self.assertIsNone(visuals.local_composite(self.service, "terra", "aberdeen", "2020-01-04"))

    def test_cross_source_case_originals_survive_source_loss(self):
        from intel import cases
        from archive import connect as archive_connect
        from news import News
        from discovery import init
        from hashlib import sha256
        from zipfile import ZipFile
        from datetime import datetime, timezone
        import os

        now=int(time.time())
        day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
        place="Aberdeen"
        bodies={"archive":b"exact archive bytes\r\n","news":b"<html>Aberdeen news</html>","documents":b"%PDF-1.7 actual bytes"}
        News(self.archive)
        with closing(archive_connect(self.archive)) as db,db:
            init(db)
            blob=bodies["archive"]
            db.execute("INSERT INTO snapshot VALUES(1,'station','https://example.org/a','Aberdeen notice','CC0',?,?)",(sha256(blob).hexdigest(),blob))
            db.execute("INSERT INTO search(rowid,title,body) VALUES(1,'Aberdeen notice','Aberdeen')")
            db.execute("INSERT INTO fetch(source,checked_at,snapshot_id) VALUES('station',?,1)",(day+"T23:59:59Z",))
            db.execute("INSERT INTO news_story VALUES(1,'Scotland','https://example.org/b','Aberdeen report','summary',?,'text')",(now,))
            db.execute("INSERT INTO news_original VALUES(1,'https://example.org/b',?,?)",(now,bodies["news"]))
            db.execute("INSERT INTO discovery_item VALUES('doc','Documents','Aberdeen public notice','harbour','public','https://example.org/c','.pdf','Harbour office','doc.pdf')")
        file=self.archive.parent/"Content"/"doc.pdf"
        file.parent.mkdir(exist_ok=True);file.write_bytes(bodies["documents"]);os.utime(file,(now,now))
        raw=json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[-2,57.15]},"properties":{"title":"Local report","time":day+"T00:00:00Z"}}]},indent=2)
        self.service.local("aberdeen",raw);bodies["observation"]=raw.encode()
        records=cases.search(self.service,place,day,day)["rows"]
        self.assertEqual({r["collection"] for r in records},set(bodies))
        self.assertFalse(cases.search(self.service,place,"2000-02-01","2000-02-02")["rows"])
        owner=cases.create(self.service,"Harbour study")
        for row in records:
            for _ in range(2):cases.attach(self.service,owner,row["collection"],row["key"],row["version"])
        with self.assertRaises(ValueError):cases.attach(self.service,owner,"news","1","old-version")
        doc = next(e for e in cases.listing(self.service,owner)["items"] if e["collection"]=="documents")
        from android.merge import revision
        before = revision(self.archive)
        relationship = ("Harbour office","issued a notice to","Port authority","Uncertain",doc["ref"],"Page 1, addressee")
        edge = cases.add_relationship(self.service,owner,*relationship)
        self.assertNotEqual(before,revision(self.archive))
        with self.assertRaises(ValueError):
            cases.add_relationship(self.service,cases.create(self.service,"Separate case"),*relationship)
        file.unlink()
        self.assertEqual(cases.exhibit_original(self.service,owner,doc["ref"]),bodies["documents"])
        with self.assertRaises(ValueError):
            cases.exhibit_original(self.service,0,doc["ref"])
        with closing(connect(self.archive)) as db,db:db.execute("DELETE FROM news_original")
        with cases.export(self.service,owner) as stream,ZipFile(stream) as exported:
            manifest=json.loads(exported.read("manifest.json"));citations=exported.read("citations.txt").decode()
            self.assertEqual(len(manifest["exhibits"]),4)
            self.assertEqual(manifest["relationships"][0]["uuid"],edge)
            self.assertIn(f"Exhibit [{doc['exhibit']}] · Page 1, addressee",citations)
            for r in manifest["exhibits"]:
                self.assertEqual(exported.read(r["file"]),bodies[r["collection"]])
                self.assertIn(sha256(bodies[r["collection"]]).hexdigest(),citations)

    def test_cases_merge_on_identity_and_retain_exhibits(self):
        from android.merge import merge, revision
        from intel import cases
        from zipfile import ZipFile
        with tempfile.TemporaryDirectory() as directory:
            other_path=Path(directory)/"archive.sqlite3"
            other=Intel(other_path)
            self.addCleanup(other.close)
            cases.create(other,"Same title")
            origin=cases.create(self.service,"Same title")
            row=providers.observation("buoys","a","A wave",57,-2,time.time(),"2 m")
            self.service.store("aberdeen",row)
            record=cases.search(self.service,"A wave")["rows"][0]
            before=revision(self.archive)
            cases.attach(self.service,origin,"observation",record["key"],record["version"])
            self.assertNotEqual(before,revision(self.archive))
            exhibit=cases.listing(self.service,origin)["items"][0]
            prior=revision(self.archive)
            finding=cases.add_finding(self.service,origin,"One buoy report was received.","Wave extent is unknown.",{exhibit["ref"]:"supports"})
            self.assertNotEqual(prior,revision(self.archive))
            with self.assertRaises(ValueError):
                cases.add_finding(self.service,origin,"Invalid reference","",{"unknown":"supports"})
            relationship=cases.add_relationship(self.service,origin,"Station A","reported to","Observatory","Supported",exhibit["ref"],"Source report header")
            for _ in range(2):merge(other_path,self.archive)
            owners=cases.listing(other)["cases"]
            self.assertEqual(len(owners),2)
            attached=[c for c in owners if cases.listing(other,c["id"])["items"]]
            self.assertEqual(len(attached),1)
            with cases.export(other,attached[0]["id"]) as stream,ZipFile(stream) as bundle:
                manifest=json.loads(bundle.read("manifest.json"))
                self.assertEqual([r["uuid"] for r in manifest["relationships"]],[relationship])
                self.assertEqual(manifest["relationships"][0]["exhibit_ref"],manifest["exhibits"][0]["ref"])
                self.assertEqual([f["uuid"] for f in manifest["findings"]],[finding])
                self.assertEqual(manifest["findings"][0]["links"],{manifest["exhibits"][0]["ref"]:"supports"})
                self.assertIn("retrieved_utc",manifest["exhibits"][0])
                self.assertIn("Exhibit [1] supports this finding",bundle.read("citations.txt").decode())
                self.assertIn("A wave",bundle.read("citations.txt").decode())

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
