"""Illustrated archive installation and interrupted transfer regression tests."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from references import Wiki
from wiki_editions import Editions


class Response(BytesIO):
    status = 206

    def __init__(self, data, content_range):
        super().__init__(data)
        self.headers = {"Content-Range": content_range}


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.wiki = Wiki(None, None, self.folder)
        self.manager = Editions(self.folder, self.wiki)
        self.name = "wikipedia_en_all_maxi_test.zim"
        self.part = self.folder / (self.name + ".part")

    def test_default_and_starter_search_choose_wikipedia_with_other_archives(self):
        other = self.folder / "appropedia_en_mini_2026.zim"
        starter = self.folder / "wikipedia_en-simple_all_mini_2026.zim"
        self.wiki.archives = [other, starter]
        self.assertIn("content=" + starter.stem, self.wiki.page("", "Aberdeen"))
        self.manager.select("starter")
        self.assertEqual(self.wiki.preferred, starter.stem)
        self.assertIn("content=" + other.stem, self.wiki.page(other.stem, "Aberdeen"))

    def test_resume_verify_register_and_prefer(self):
        self.part.write_bytes(b"abcd")
        with patch("wiki_editions.urlopen", return_value=Response(b"ef", "bytes 4-5/6")) as fetch:
            self.manager.transfer(self.name, 6, sha256(b"abcdef").hexdigest(), self.part)
        self.assertEqual(fetch.call_args.args[0].get_header("Range"), "bytes=4-5")
        self.wiki.refresh()
        self.assertIn(self.folder / self.name, self.wiki.archives)
        self.assertIn(self.name[:-4] + '/"', self.wiki.page("", ""))

    def test_corrupt_archive_never_opened(self):
        self.part.write_bytes(b"ab")
        with self.assertRaisesRegex(OSError, "Checksum"):
            self.manager.transfer(self.name, 2, sha256(b"xx").hexdigest(), self.part)
        self.assertFalse(self.part.exists())
        self.assertFalse((self.folder / self.name).exists())

    def test_wrong_range_preserves_partial(self):
        self.part.write_bytes(b"a")
        with patch("wiki_editions.urlopen", return_value=Response(b"b", "bytes 0-0/2")):
            with self.assertRaisesRegex(ValueError,"range"):
                self.manager.transfer(self.name, 2, "", self.part)
        self.assertEqual(self.part.read_bytes(), b"a")

    def test_insufficient_space_keeps_existing_choice(self):
        self.manager.select("starter")
        with patch("wiki_editions.disk_usage") as usage:
            usage.return_value.free = 10
            self.manager.select("full")
            self.assertIn('insufficient space', self.manager.panel("token"))
        self.assertIsNone(self.manager.active)
        self.assertEqual(self.manager.choice.read_text(), "starter")
