"""Exercise a fresh workstation with fixture downloads and no external services."""
from contextlib import closing
from io import BytesIO, StringIO
import json
import sqlite3
import news
from pathlib import Path
import tempfile
import zlib
import references
from threading import Thread
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import urlopen

import archive
import dashboard
import evidence
from kit_library import listing


class WorkstationTest(unittest.TestCase):
    def test_dictionary_browse_and_sense_relationships(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "companion"
            path = launcher.parent / "library/dictionary.sqlite3"
            path.parent.mkdir()
            senses = [{"glosses":["An animal:", gloss], "synonyms":[{"word":"canine"}],
                       "examples":[{"type":"example","text":"The dog barked."}]}
                      for gloss in ["A domesticated animal.", "A member of the canine family."]]
            sample = [w for w in Path(references.__file__).with_name("reading-words.txt").read_text().splitlines() if w.startswith("a")][:50]
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE entries(id INTEGER PRIMARY KEY,word TEXT,normalized TEXT,pos TEXT,payload BLOB)")
                for word in ["dog","canine"] + sample + ["a1", "a phrase", "AAAAI", "AAAAM", "aaawesomes"]:
                    payload = zlib.compress(json.dumps({"lang_code":"en", "senses":senses}).encode())
                    db.execute("INSERT INTO entries(word,normalized,pos,payload) VALUES(?,?,?,?)",(word,word.casefold(),"noun",payload))
            home = references.dictionary(launcher,"")
            self.assertIn("Word of the day",home)
            self.assertIn(">"+sample[47]+"</a>",home)
            self.assertNotIn(">"+sample[48]+"</a>",home)
            self.assertNotIn(">a1</a>",home)
            self.assertNotIn(">AAAAI</a>",home)
            self.assertIn(">AAAAI</a>",references.dictionary(launcher,"","a","1",True))
            self.assertIn(">a phrase</a>",references.dictionary(launcher,"","a","1",True))
            self.assertIn(">"+sample[48]+"</a>",references.dictionary(launcher,"","a","2"))
            result = references.dictionary(launcher,"dog")
            self.assertEqual(result.count("<h4>An animal</h4>"),1)
            self.assertNotIn("<ol>",result)
            self.assertIn("The dog barked.",result)
            self.assertIn('href="/dictionary?q=canine"',result)

    def test_news_background_refresh_and_offline_restart(self):
        rss = b"<rss><channel><item><title>Local update</title><link>https://www.bbc.co.uk/news/articles/example</link><description>Brief</description></item></channel></rss>"
        def retrieve(url, limit):
            return rss if url.endswith(".xml") else b"<article><p>A complete local report.</p></article>"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "news.db"
            cache = news.News(path)
            with patch.object(news, "fetch", side_effect=retrieve):
                cache.choose("Scotland")
                cache.start()
                try:
                    for _ in range(100):
                        with closing(sqlite3.connect(path)) as db:
                            if db.execute("SELECT count(*) FROM news_story WHERE body != ''").fetchone()[0] == 2:
                                break
                        time.sleep(.02)
                    else:
                        self.fail("World and regional articles were not saved in the background")
                finally:
                    cache.close()
            cache = news.News(path)
            with closing(sqlite3.connect(path)) as db, patch.object(news, "fetch", side_effect=OSError("offline")):
                with db:
                    db.execute("UPDATE news_check SET attempt=0")
                cache.refresh(db,"Scotland")
                key = db.execute("SELECT id FROM news_story WHERE edition='Scotland'").fetchone()[0]
            self.assertIn("A complete local report.",cache.story(key))
            self.assertIn("Refresh unavailable",cache.render(""))
            self.assertIn("Scotland",cache.render("",home=True))

    def test_setup_offline_search_and_original_export(self):
        body = b'{"features":[{"properties":{"title":"Example earthquake"}}]}'
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "archive.sqlite3"
            with patch.object(archive, "urlopen", return_value=BytesIO(body)) as download:
                with dashboard.create_server(0, db) as server:
                    serving = Thread(target=server.serve_forever)
                    serving.start()
                    base = f"http://127.0.0.1:{server.server_port}"
                    try:
                        def get(path):
                            with urlopen(base + path, timeout=5) as response:
                                return response.read()

                        sources = get("/?region=WORLD&region=GB-SCT")
                        self.assertIn(b"scotmesh", sources)
                        self.assertIn(b"usgs-earthquakes", sources)
                        request = urlencode([
                            ("token", server.token), ("region", "WORLD"),
                            ("region", "GB-SCT"), ("source", "usgs-earthquakes"),
                        ]).encode()
                        with urlopen(base + "/sync", request, timeout=5) as response:
                            self.assertEqual(response.status, 200)
                        deadline = time.monotonic() + 5
                        while b"/read/1" not in get("/archive?q=earthquake"):
                            if time.monotonic() >= deadline:
                                self.fail("Download did not finish")
                            time.sleep(0.05)
                        self.assertIn(b"Example earthquake", get("/read/1"))
                        self.assertEqual(get("/snapshot/1"), body)
                        self.assertIn(b'value="usgs-earthquakes" checked', get("/sources"))
                        cards = get("/home-status")
                        self.assertIn(b"Saved sources", cards)
                        self.assertNotIn(b'class="tile result-card discovery-card"', cards)
                        self.assertIn(b'class="tile result-card discovery-card"', get("/"))
                        download.assert_called_once()
                    finally:
                        server.shutdown()
                        serving.join()

    def test_download_thread_stops_when_library_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with dashboard.create_server(0, Path(tmp) / "library.sqlite3") as server:
                worker = server.downloads.worker
                self.assertTrue(worker.is_alive())
            self.assertFalse(worker.is_alive())

    def test_migrate_interrupted_catalogue_jobs_without_requeuing_other_failures(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(dashboard.Downloads, "run", return_value=None):
            path = Path(tmp) / "library.sqlite3"
            with dashboard.create_server(0, path):
                pass
            with closing(archive.connect(path)) as db, db:
                db.executemany("INSERT INTO pending_download(source,title,state) VALUES(?,?,?)", [
                    ("discover-abc","Audiobook","Interrupted: 'discover-abc'"),
                    ("discover-def","Film","Interrupted: Insufficient available storage"),
                    ("usgs-earthquakes","Earthquakes","Queued")])
            with dashboard.create_server(0, path) as server, closing(archive.connect(path)) as db:
                self.assertEqual(dict(db.execute("SELECT source,state FROM content_download")),
                                 {"discover-abc":"Queued", "discover-def":"Interrupted: Insufficient available storage"})
                self.assertEqual(db.execute("SELECT source FROM pending_download").fetchone()[0], "usgs-earthquakes")
                self.assertEqual(len(server.downloads.progress(db)), 3)

    def test_recent_cards_render_feed_records(self):
        from discovery import preview
        readings = [{"time_tag":"2026-11-10T09:00:00","Kp":4},
                    {"time_tag":"2026-11-11T12:00:00","Kp":2,"station_count":8}]
        self.assertEqual(preview("noaa-kp",json.dumps(readings)), "Planetary Kp index 2 · 2026-11-11 12:00 UTC · 8 reporting stations")
        self.assertEqual(preview("nasa-eonet",json.dumps({"title":"EONET Events","events":[{"title":"Tropical Cyclone Akvan"}]})), "Tropical Cyclone Akvan")

    def test_clips_are_previews_not_extra_films(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "04-Entertainment/Video"
            thumbs = video / ".thumbnails"
            thumbs.mkdir(parents=True)
            (video / "Film.webm").touch()
            (thumbs / "Film.webm.preview.mp4").touch()
            shelf = listing(root.resolve(), "watch", on_load=True)
            self.assertEqual(shelf.count("class=item"), 1)
            self.assertIn('data-clip="/preview/watch/Film.webm"', shelf)

    def test_chat_bridge_preserves_companion_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            companion = root / "echolite"
            companion.write_text("#!/bin/sh\nprintf 'begin%s%s%s%send' \"$3\" \"$3\" \"$3\" \"$3\"\n")
            companion.chmod(0o700)
            with dashboard.create_server(0, root / "db", echolite=companion) as server:
                serving = Thread(target=server.serve_forever)
                serving.start()
                try:
                    prompt = "x" * 7000
                    fields = urlencode({"prompt": prompt, "token": server.token}).encode()
                    with urlopen(f"http://127.0.0.1:{server.server_port}/echolite", fields, timeout=5) as response:
                        self.assertIn(("begin" + prompt * 4 + "end").encode(), response.read())
                finally:
                    server.shutdown()
                    serving.join()

    def test_live_kit_logs_handle_appends_and_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "01-Comms/Reception Logs"
            folder.mkdir(parents=True)
            log = folder / "local.jsonl"
            first = {"time": "2026-11-19T13:11:00Z", "event": "local decode"}
            second = {"time": "2026-11-19T13:12:00Z", "event": "local decode"}
            log.write_text(json.dumps(first) + "\n")
            monitor = evidence.KitReceptionLogs(root)
            with closing(archive.connect(root / "test.sqlite3")) as db:
                with patch.object(evidence, "monotonic", return_value=10):
                    monitor.refresh(db)
                with log.open("a") as stream:
                    stream.write(json.dumps(second) + "\n")
                with patch.object(evidence, "monotonic", return_value=16):
                    monitor.refresh(db)
                evidence.KitReceptionLogs(root).refresh(db)
                self.assertEqual([row["event_at"] for row in evidence.timeline(db)],
                                 ["2026-11-19T13:12:00+00:00", "2026-11-19T13:11:00+00:00"])

    def test_distinct_event_types_and_idempotent_import(self):
        rows = [
            {"time": "2026-11-19T11:41:51+00:00", "source": "ScotMesh", "event": "online status"},
            {"time": "2026-11-19T11:41:35+00:00", "event": "receiver status", "listening": True},
            {"time": "2026-11-19T11:47:20+00:00", "source": "ScotMesh",
             "source_time_utc": "2026-11-19T10:57:37+00:00", "event": "packet-feed timestamp"},
        ]
        data = "\n".join(map(json.dumps, rows))
        with tempfile.TemporaryDirectory() as folder, closing(archive.connect(Path(folder) / "archive.sqlite3")) as db:
            self.assertEqual(evidence.import_records(db, "receiver.jsonl", StringIO(data)), (3, 0))
            self.assertEqual(evidence.import_records(db, "receiver.jsonl", StringIO(data)), (0, 0))
            self.assertEqual(
                [row["category"] for row in evidence.timeline(db)],
                ["public_online_status", "receiver_status", "public_packet_feed"],
            )
            selected = evidence.timeline(db, source="ScotMesh", end="2026-11-19T11:00:00+00:00")
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]["event_at"], "2026-11-19T10:57:37+00:00")


if __name__ == "__main__":
    unittest.main()
