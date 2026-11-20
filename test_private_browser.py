from pathlib import Path
import tempfile
import unittest
from private_browser import address,Reader,Session,link_address,screen

class PrivateBrowserTest(unittest.TestCase):
    def test_reader_keeps_content_links_and_images_with_optional_head_end(self):
        reader=Reader("https://example.org/",lambda _: "/private-image/local")
        reader.feed('<head><title>A</title><style>xxx</style><body><h1>Example</h1><a href="/two">Two</a><img src="/photo.jpg" onerror="bad()"><script>leak()</script>')
        page="".join(reader.parts)
        self.assertIn("<h1>Example</h1>",page)
        self.assertIn('value="https://example.org/two"',page)
        self.assertIn('src="/private-image/local"',page)
        for unsafe in ("bad()", "leak()", "<script", "xxx"):
            self.assertNotIn(unsafe,page)

    def test_fail_closed_and_public_https_only(self):
        with tempfile.TemporaryDirectory() as root:
            session=Session(Path(root))
            with self.assertRaises(ValueError):session.fetch("example.org")
            for url in ["file:///etc/passwd","http://example.org","https://localhost","https://127.0.0.1","https://user:pass@example.org"]:
                with self.subTest(url=url),self.assertRaises(ValueError):address(url)

    def test_public_link_preserves_destination_and_upgrades_http(self):
        self.assertEqual(link_address("http://example.org/book?q=one#chapter"),
                         "https://example.org/book?q=one#chapter")
        for target in ("file:///etc/passwd", "http://127.0.0.1/private", "https://user@example.org/"):
            with self.assertRaises(ValueError):
                link_address(target)

    def test_reader_result_does_not_relaunch_and_keeps_protected_links(self):
        with tempfile.TemporaryDirectory() as root:
            session=Session(Path(root))
            page=screen(session,"token","https://example.org/","<p>Example</p>")
            self.assertIn('data-destination=""',page)
            self.assertIn('<article><p>Example</p></article>',page)
            self.assertIn('id="private-links"',page)
