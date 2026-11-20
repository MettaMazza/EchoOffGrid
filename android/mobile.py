from http.cookies import SimpleCookie, CookieError
"""Android host for the same dashboard used on macOS."""
from pathlib import Path
import os
import secrets
import sys
from threading import Thread

def start(root, native, token):
    os.environ["HOME"] = root
    import dashboard
    staging = Path(root)
    root = staging / "Workstation"
    root.mkdir(exist_ok=True)
    incoming_dir = staging / "incoming"
    incoming_dir.mkdir(exist_ok=True)
    kit = root / "Kit"
    kit.mkdir(exist_ok=True)
    os.environ["SSL_CERT_FILE"] = str(Path(__file__).with_name("cacert.pem"))
    server = dashboard.create_server(0, root / "archive.sqlite3", kit=kit)
    class MobileDashboard(dashboard.Dashboard):
        def do_GET(self):
            if self.path == "/mobile-transfer-count" and self.local_request():
                from contextlib import closing
                with closing(dashboard.connect(server.database)) as db:
                    count=sum(db.execute(f"SELECT count(*) FROM {table} WHERE state IN ('Queued','Downloading')").fetchone()[0]
                              for table in ("content_download","pending_download"))
                body=str(count+int(bool(server.editions.active))).encode()
                self.send_response(200)
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/archive/backup" and self.local_request() and self.headers.get("X-Echo-Export") == "1":
                self.backup_archive()
                return
            super().do_GET()

        def local_request(self):
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
            except CookieError:
                return False
            auth = cookies.get("workstation")
            return super().local_request() and auth is not None and secrets.compare_digest(
                auth.value.encode(), token.encode())
    server.private_browser.binary = Path(native) / "libtor.so"
    server.private_browser.state = Path(__file__).resolve().parents[4] / "Tor"
    from browser_proxy import BrowserProxy
    server.phone_proxy = BrowserProxy(str(server.private_browser.state.parent/"vpn"/"s"))
    server.android = True
    server.RequestHandlerClass = MobileDashboard
    server.companion_status = root / "sync-status.json"
    server.dictionary_path = root / "library/dictionary.sqlite3"
    os.environ["ICU_DATA"] = str(Path(__file__).parent/"icu")
    server.wiki.diagnostic_log = staging/"wiki-startup.log"
    server.wiki.tool = Path(native) / "libkiwix-serve.so"
    from voice import renderer
    dashboard.narrator.render = renderer(native, Path(__file__).parent)
    import json
    import logging
    import time
    from storage_policy import fits
    from merge import merge
    from peer import serve
    from peer import portable
    def adopt():
        for manifest in incoming_dir.glob("*.json"):
            for slot, name in json.loads(manifest.read_text()):
                if Path(slot).name != slot or not portable(name):
                    raise ValueError("Invalid USB manifest entry")
                target = root / name
                source = incoming_dir / slot
                if source.is_file():
                    target.parent.mkdir(parents=True,exist_ok=True)
                    source.replace(target)
                elif not target.is_file():
                    raise IOError("USB import interrupted")
            manifest.unlink()
    def usb_worker():
        while True:
            try:
                adopt()
            except Exception:
                logging.exception("USB library import")
            time.sleep(2)
    Thread(target=usb_worker,daemon=True).start()
    snapshot = root / "desktop.sqlite3"
    seed = staging / "desktop.sqlite3"
    if not snapshot.exists() and seed.is_file():
        import shutil
        shutil.copyfile(seed,snapshot)
    def monitor():
        previous = None
        while True:
            try:
                if snapshot.exists():
                    stamp = snapshot.stat().st_mtime_ns
                    if stamp != previous and fits(root, snapshot.stat().st_size*2):
                        merge(server.database, snapshot)
                        previous = stamp
                        status=root/"sync-status.pending"
                        status.write_text(json.dumps({"state":"Desktop archive synced","checked":int(time.time())}))
                        status.replace(server.companion_status)
                server.wiki.refresh()
            except Exception:
                logging.exception("Companion sync")
            time.sleep(5)
    def pairing():
        while True:
            try:
                credentials=Path(__file__).resolve().parents[4]/"paired-device"
                credentials.mkdir(mode=0o700,exist_ok=True)
                incoming=staging/"pairing.json"
                if incoming.is_file():
                    bundle=json.loads(incoming.read_text())
                    for key,name in (("cert","cert.pem"),("key","key.pem"),("token","token")):
                        (credentials/name).write_text(bundle[key])
                    incoming.unlink()
                if (credentials/"token").is_file():
                    serve(root, {"token":(credentials/"token").read_text()}, credentials)
                    print("Paired library listener is ready", flush=True)
                    return
            except Exception:
                logging.exception("Pairing listener")
            time.sleep(5)
    print("Companion storage", {str(p.relative_to(root)):p.exists() for p in
          [server.dictionary_path, kit/"03-Maps/Atlas/UK.pmtiles",root/"pairing.json"]}, flush=True)
    Thread(target=pairing,daemon=True).start()
    Thread(target=monitor, daemon=True).start()
    server.news.start()
    Thread(target=server.serve_forever, daemon=True).start()
    return server.server_port
