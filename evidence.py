"""Import local receiver logs and public packet reports into an offline timeline."""
import argparse
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from io import StringIO
from threading import Lock
from time import monotonic
from urllib.request import ProxyHandler, build_opener

from archive import connect


DEFAULT_DATABASE = Path.home() / "Library/Application Support/EchoOffGrid/archive.sqlite3"
MAX_LOG_BYTES = 16 * 1024 * 1024
EVENT_TYPES = {
    "packet-feed timestamp": "public_packet_feed",
    "feed checked": "public_feed_check",
    "feed unavailable": "public_feed_unavailable",
    "online status": "public_online_status",
    "local decode": "local_decode",
    "decoder reported packet": "local_decode",
    "receiver status": "receiver_status",
    "listening": "receiver_status",
    "receiver inactive": "receiver_status",
    "receiver unavailable": "receiver_status",
    "SDRangel report snapshot": "decoder_snapshot",
    "watch started": "recorder_status",
    "watch ended": "recorder_status",
}


def create_table(database):
    database.executescript("""
        CREATE TABLE IF NOT EXISTS evidence (
            fingerprint TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            event_at TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            filename TEXT NOT NULL,
            record TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS evidence_event_at ON evidence(event_at DESC);
    """)


def normalized_time(value):
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return timestamp.astimezone(timezone.utc).isoformat()


def records(stream, suffix):
    if suffix == ".csv":
        yield from csv.DictReader(stream)
    elif suffix == ".jsonl":
        for line in stream:
            try:
                yield json.loads(line)
            except ValueError:
                yield None
    else:
        raise ValueError("Expected CSV or JSONL")


def import_log(database, path):
    if path.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("Log exceeds 16 MiB")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return import_records(database, path.name, stream)


class KitReceptionLogs:
    """Import changed recorder files when the dashboard is viewed."""
    def __init__(self, kit):
        self.kit = kit.resolve() if kit else None
        self.lock = Lock()
        self.next_check = 0
        self.seen = {}

    def refresh(self, database):
        if not self.kit or monotonic() < self.next_check or not self.lock.acquire(blocking=False):
            return
        try:
            self.next_check = monotonic() + 5
            folder = (self.kit / "01-Comms/Reception Logs").resolve()
            if not folder.is_relative_to(self.kit) or not folder.is_dir():
                return
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() not in {".csv", ".jsonl"} or path.is_symlink() or not path.is_file():
                    continue
                try:
                    info = path.stat()
                    signature = info.st_ino, info.st_mtime_ns, info.st_size
                    if signature != self.seen.get(path) and info.st_size <= MAX_LOG_BYTES:
                        import_log(database, path)
                        self.seen[path] = signature
                except (OSError, ValueError, csv.Error):
                    continue
        except OSError:
            return
        finally:
            self.lock.release()


def import_records(database, filename, stream):
    create_table(database)
    added = skipped = 0
    with database:
        for row in records(stream, Path(filename).suffix.lower()):
            if not isinstance(row, dict) or not isinstance(row.get("event"), str) or row["event"] not in EVENT_TYPES:
                skipped += 1
                continue
            category = EVENT_TYPES[row["event"]]
            source = row.get("source") or "HackRF"
            if source not in ("HackRF", "ScotMesh"):
                skipped += 1
                continue
            try:
                observed_at = normalized_time(row.get("checked_at_utc") or row["time"])
                event_at = normalized_time(row.get("source_time_utc") or observed_at)
            except (KeyError, ValueError, AttributeError):
                skipped += 1
                continue
            raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
            fingerprint = hashlib.sha256(raw.encode()).hexdigest()
            result = database.execute("INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?,?,?)",
                                      (fingerprint, source, category, event_at, observed_at,
                                       filename, raw))
            added += result.rowcount
    return added, skipped


def import_scotmesh(database, node_name):
    snapshot = database.execute("""
        SELECT s.id, s.body, min(f.checked_at) AS saved_at
        FROM snapshot s JOIN fetch f ON f.snapshot_id=s.id
        WHERE s.source='scotmesh'
        GROUP BY s.id ORDER BY s.id DESC LIMIT 1
    """).fetchone()
    if snapshot is None:
        raise ValueError("Download the ScotMesh public network snapshot from Sources first.")
    devices = json.loads(snapshot["body"])["devices"]
    if isinstance(devices, dict):
        devices = devices.values()
    matches = [device for device in devices
               if str(device.get("name", "")).casefold() == node_name.casefold()]
    if not matches:
        raise ValueError("That node name was not found in the latest saved ScotMesh snapshot.")

    records_to_import = []
    for device in matches:
        for field, event in (("mqtt_packets_ts", "packet-feed timestamp"),
                             ("mqtt_status_ts", "online status")):
            timestamp = device.get(field)
            if not isinstance(timestamp, (float, int)) or timestamp <= 0:
                continue
            records_to_import.append({
                "source": "ScotMesh",
                "event": event,
                "time": snapshot["saved_at"],
                "source_time_utc": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
                "detail": device["name"],
                "node_id": device.get("device_id"),
                "status": device.get("mqtt_status_value") if field == "mqtt_status_ts" else None,
                "snapshot_id": snapshot["id"],
                "timestamp_field": field,
            })
    stream = StringIO("\n".join(json.dumps(row) for row in records_to_import))
    added, _ = import_records(database, f"ScotMesh snapshot {snapshot['id']}.jsonl", stream)
    return added, len(records_to_import)


def capture_receiver(database):
    """Save reports observed now, without assigning reception times to cached packets."""
    base = "http://127.0.0.1:18891/sdrangel/"
    opener = build_opener(ProxyHandler({}))

    def read(path):
        with opener.open(base + path, timeout=3) as response:
            data = response.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                raise ValueError("SDRangel response exceeds 1 MiB")
            return json.loads(data)

    observations = []
    for index, device in enumerate(read("devicesets").get("deviceSets", [])):
        receiver = device["samplingDevice"]
        if receiver["hwType"] != "HackRF" or receiver["state"] != "running":
            continue
        for channel in device.get("channels", []):
            if channel["id"] != "MeshcoreDemod":
                continue
            channel_index = channel["index"]
            report = read(f"deviceset/{index}/channel/{channel_index}/report")["MeshcoreDemodReport"]
            observations.append({
                "source": "HackRF",
                "event": "SDRangel report snapshot",
                "time": datetime.now(timezone.utc).isoformat(),
                "device_set": index,
                "decoder_channel": channel_index,
                "frequency_hz": receiver["centerFrequency"] + channel["deltaFrequency"],
                "packet_length_reported": report.get("packetLength"),
                "crc_status": report.get("payloadCRCStatus"),
                "snr_db": report.get("snrPowerDB"),
                "channel_power_db": report.get("channelPowerDB"),
                "detail": "Decoder report at time of check. A cached packet may be older.",
            })
    stream = StringIO("\n".join(json.dumps(row) for row in observations))
    return import_records(database, "SDRangel localhost.jsonl", stream)[0]


def timeline(database, include_checks=False, limit=250, *, source="", start="", end=""):
    create_table(database)
    return database.execute("""
        SELECT * FROM evidence
        WHERE (? OR category != 'public_feed_check')
          AND (? = '' OR source = ?)
          AND (? = '' OR event_at >= ?)
          AND (? = '' OR event_at < ?)
        ORDER BY event_at DESC, observed_at DESC, fingerprint
        LIMIT ?
    """, (include_checks, source, source, start, start, end, end, limit)).fetchall()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    with closing(connect(args.db)) as database:
        for path in args.logs:
            added, skipped = import_log(database, path)
            print(f"{path.name}: {added} new records, {skipped} unreadable or unsupported")


if __name__ == "__main__":
    main()
