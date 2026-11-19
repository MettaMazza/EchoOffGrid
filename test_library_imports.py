"""Exercise the packaged offline shelves and the ordinary category import routes."""
from contextlib import closing
from io import BytesIO
from pathlib import Path
import json
import plistlib
import tempfile
from threading import Thread
import unittest
from urllib.request import Request, urlopen
from zipfile import ZipFile

from archive import connect
from dashboard import create_server
from personal_library import SHELVES


class LibraryTest(unittest.TestCase):
    def test_fresh_shelves_and_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "archive.sqlite3"
            with create_server(0, path) as server:
                thread = Thread(target=server.serve_forever)
                thread.start()
                origin = f"http://127.0.0.1:{server.server_port}"
                def read(route):
                    with urlopen(origin + route, timeout=5) as res:
                        return res.read()
                def upload(shelf, filename, entries):
                    blob = BytesIO()
                    with ZipFile(blob, "w") as z:
                        for name, data in entries.items():
                            z.writestr(name, data)
                    request = Request(origin + "/library/" + shelf + "/import", blob.getvalue(),
                                      {"X-Library-Token": server.token, "X-Filename": filename})
                    with urlopen(request, timeout=8) as res:
                        self.assertEqual(res.status, 201)
                        return res.read().decode()
                try:
                    self.assertIn(b'word-sense',read("/dictionary?q=dog"))
                    self.assertIn(b"/news/field-notes/",read("/news"))
                    self.assertIn(b"Lunar Reconnaissance Orbiter",read("/news/field-notes/15728898"))
                    self.assertTrue(read("/atlas/World.pmtiles").startswith(b"PMTiles"))
                    for shelf in SHELVES:
                        with self.subTest(shelf=shelf):
                            page = read("/library/" + shelf)
                            self.assertIn(b'class="category-grid ', page)
                            self.assertNotIn(b'<section class="carousel"', page)
                            self.assertEqual(page.count(b"<input name=files type=file"), 1)
                    with closing(connect(path)) as db:
                        rows=db.execute("SELECT * FROM discovery_item WHERE filename IS NOT NULL").fetchall()
                    self.assertEqual(sum(r["kind"]=="Pictures" for r in rows), 5)
                    for row in rows:
                        self.assertTrue(read("/content-file/" + row["id"]))
                        self.assertIn(row["id"].encode(), read("/content/" + row["id"]))
                    photos=Path(__file__).parent/"vendor/picture-samples"
                    image=(photos/json.loads((photos/"credits.json").read_text())[0]["file"]).read_bytes()
                    key=upload("books","untitled.epub",{
                        "META-INF/container.xml":'<container><rootfile full-path="book.opf"/></container>',
                        "book.opf":'<package><metadata><title>The real title</title></metadata><manifest><item id="a" href="abc.jpg" properties="cover-image"/></manifest></package>',
                        "abc.jpg":image})
                    self.assertEqual(read("/personal-cover/"+key),image)
                    self.assertIn(b"The real title",read("/library/books"))
                    key=upload("games","Original.app.zip",{
                        "Original.app/Contents/Info.plist":plistlib.dumps({"CFBundleDisplayName":"Embedded game title"}),
                        "Original.app/Contents/Resources/icon.jpg":image})
                    self.assertIn(b"Embedded game title",read("/library/games"))
                    self.assertEqual(read("/personal-cover/"+key),image)
                finally:
                    server.shutdown()
                    thread.join()
