from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from unittest import TestCase
from unittest.mock import patch
import dashboard
import discovery
from archive import connect


class RateLimitTest(TestCase):
    def test_archived_offline_edition_is_pinned_to_matching_commons_title(self):
        item={"url":"https://upload.wikimedia.org/wikipedia/commons/a/a7/Wizard_of_Oz_%281925%29.webm?utm_source=commons", "title":"Wizard of Oz (1925).webm"}
        name,url,ext,size,digest=discovery.commons_video(item)
        self.assertEqual(name,"The Wizard of Oz (1925)")
        self.assertEqual(ext,".mp4")
        self.assertTrue(url.startswith("https://archive.org/download/the-wizard-of-oz-1925/"))
        self.assertEqual(size,399884974)
        self.assertEqual(len(digest),40)

    def test_backoff_survives_worker_poll_and_clears_after_success(self):
        with TemporaryDirectory() as folder, dashboard.create_server(0,Path(folder)/"archive.sqlite3") as server:
            worker=server.downloads
            worker.stopping.set()
            worker.wakeup.set()
            worker.worker.join()
            with closing(connect(server.database)) as db, db:
                key=db.execute("SELECT id FROM discovery_item WHERE filename IS NULL LIMIT 1").fetchone()[0]
                job={"id":"discover-"+key,"title":"Test film"}
                worker.enqueue(db,[job])
                db.commit()
                with patch("discovery.download",side_effect=HTTPError("https://example.org",429,"Rate limited",{"Retry-After":"180"},None)) as download:
                    self.assertTrue(worker.run_one())
                    self.assertFalse(worker.run_one())
                    download.assert_called_once()
                row=worker.progress(db)[0]
                self.assertEqual(row["state"],"Queued")
                self.assertGreaterEqual(db.execute("SELECT due-strftime('%s','now') FROM download_backoff").fetchone()[0],179)
                db.execute("UPDATE download_backoff SET due=0")
                db.commit()
                with patch("discovery.download"):
                    self.assertTrue(worker.run_one())
                self.assertFalse(worker.progress(db))
                self.assertFalse(db.execute("SELECT * FROM download_backoff").fetchall())
