from hashlib import sha256
from pathlib import Path
import os
import sqlite3
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from android import storage_policy as storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_projected_reserve_and_local_override(self):
        with patch.object(storage.shutil, "disk_usage") as usage:
            usage.return_value.free = storage.RESERVE + 300
            self.assertTrue(storage.fits(self.root, 300))
            self.assertFalse(storage.fits(self.root, 301))
            usage.return_value.free = storage.RESERVE - 1
            self.assertFalse(storage.fits(self.root, 0))
            marker = self.root/storage.ALLOWANCE
            marker.write_text(str(time.time()+600))
            self.assertTrue(storage.fits(self.root, 301))
            self.assertFalse(storage.fits(self.root, usage.return_value.free))
            marker.write_text(str(time.time()-1))
            self.assertFalse(storage.fits(self.root, 0))

    def test_cleanup_protects_saved_files_and_artwork(self):
        root = self.root
        with sqlite3.connect(root/"archive.sqlite3") as db:
            db.execute("CREATE TABLE discovery_item(url,filename)")
            db.execute("INSERT INTO discovery_item VALUES ('saved','book.epub')")
        art = root/"Publisher artwork"
        art.mkdir()
        saved = art/sha256(b"saved").hexdigest()
        old = art/sha256(b"old").hexdigest()
        recent = art/sha256(b"recent").hexdigest()
        content = root/"Content"
        content.mkdir()
        book = content/"book.epub"
        for file in (saved, old, recent, book):
            file.write_bytes(b"test")
        os.utime(old, (0,0))
        os.utime(saved, (0,0))
        self.assertEqual(storage.clean(root), 4)
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        storage.clean(root, clear=True)
        self.assertFalse(recent.exists())
        self.assertTrue(saved.exists())
        self.assertTrue(book.exists())
