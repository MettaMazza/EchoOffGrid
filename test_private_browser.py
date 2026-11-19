from pathlib import Path
import tempfile
import unittest
from private_browser import address,Reader,Session

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
