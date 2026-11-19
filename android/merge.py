"""Merge portable records from a consistent database snapshot, retaining local preferences."""
from contextlib import closing
from pathlib import Path
import sqlite3


def merge(local, snapshot):
    with closing(sqlite3.connect(Path(local).resolve().as_uri(), uri=True, timeout=60)) as dst:
        dst.execute("ATTACH DATABASE ? AS peer", (snapshot.resolve().as_uri() + "?mode=ro&immutable=1",))
        tables = {r[0] for r in dst.execute("SELECT name FROM peer.sqlite_master WHERE type='table'")}
        local_tables = {r[0] for r in dst.execute("SELECT name FROM main.sqlite_master WHERE type='table'")}
        content=local.parent/"Content"
        dst.create_function("has_file",1,lambda n:int(bool(n and Path(n).name==n and (content/n).is_file())))
        with dst:
            for table in ("evidence", "discovery_page", "gutenberg"):
                if table in tables & local_tables:
                    dst.execute(f"INSERT OR IGNORE INTO main.{table} SELECT * FROM peer.{table}")
            if "discovery_item" in tables & local_tables:
                dst.execute("""INSERT OR IGNORE INTO discovery_item(id,kind,title,preview,rights,url,ext,provider,filename)
                    SELECT id,kind,title,preview,rights,url,ext,provider,CASE WHEN has_file(filename) THEN filename END
                    FROM peer.discovery_item WHERE id NOT LIKE 'personal-%' OR has_file(filename)""")
                if "discovery_file" in tables & local_tables:
                    dst.execute("INSERT OR IGNORE INTO discovery_file SELECT * FROM peer.discovery_file WHERE has_file(filename)")
                dst.execute("""UPDATE discovery_item SET (filename,title,rights,provider,url,ext)=(SELECT p.filename,p.title,p.rights,p.provider,p.url,p.ext FROM peer.discovery_item p
                               WHERE p.id=discovery_item.id) WHERE filename IS NULL AND EXISTS
                               (SELECT 1 FROM peer.discovery_item p WHERE p.id=discovery_item.id AND has_file(p.filename))""")
            if {"snapshot","search","fetch"} <= (tables & local_tables):
                dst.execute("""INSERT OR IGNORE INTO main.snapshot(source,url,title,rights,sha256,body)
                            SELECT source,url,title,rights,sha256,body FROM peer.snapshot""")
                dst.execute("""INSERT INTO main.search(rowid,title,body)
                            SELECT d.id,i.title,i.body FROM peer.search i JOIN peer.snapshot s ON s.id=i.rowid
                            JOIN main.snapshot d ON d.source=s.source AND d.sha256=s.sha256
                            WHERE NOT EXISTS(SELECT 1 FROM main.search WHERE rowid=d.id)""")
                dst.execute("""INSERT INTO main.fetch(source,checked_at,snapshot_id,error)
                            SELECT f.source,f.checked_at,d.id,f.error FROM peer.fetch f
                            LEFT JOIN peer.snapshot s ON s.id=f.snapshot_id
                            LEFT JOIN main.snapshot d ON d.source=s.source AND d.sha256=s.sha256
                            WHERE NOT EXISTS(SELECT 1 FROM main.fetch old WHERE old.source=f.source
                            AND old.checked_at=f.checked_at AND old.snapshot_id IS d.id AND old.error IS f.error)""")
            if "news_story" in tables & local_tables:
                dst.execute("""INSERT INTO main.news_story(edition,link,title,summary,published,body)
                            SELECT edition,link,title,summary,published,body FROM peer.news_story WHERE true
                            ON CONFLICT(edition,link) DO UPDATE SET body=excluded.body
                            WHERE news_story.body='' AND excluded.body<>''""")
            if "news_check" in tables & local_tables:
                dst.execute("""INSERT INTO main.news_check(edition,attempt,success,error)
                            SELECT edition,attempt,success,error FROM peer.news_check WHERE true
                            ON CONFLICT(edition) DO UPDATE SET attempt=excluded.attempt,success=excluded.success,error=excluded.error
                            WHERE coalesce(excluded.success,0)>coalesce(news_check.success,0)""")
            # Seed settings on the first import. Each device subsequently owns its own choices.
            for table in ("selection","news_setting","refresh_preference"):
                if table in tables & local_tables:
                    dst.execute(f"INSERT OR IGNORE INTO main.{table} SELECT * FROM peer.{table}")


def revision(path):
    """Identify changes to the synced records without hashing large offline documents."""
    import hashlib
    digest = hashlib.sha256()
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True)) as db:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table,columns in (("snapshot","source,sha256"),("fetch","source,checked_at,error"),
                              ("evidence","fingerprint"),("discovery_item","id,filename"),
                              ("discovery_file","id,sequence,filename"),("news_story","edition,link,title,summary,published,body"),
                              ("selection","regions,sources"),("news_setting","place")):
            if table in tables:
                for row in db.execute(f"SELECT {columns} FROM {table} ORDER BY 1,2" if "," in columns else f"SELECT {columns} FROM {table} ORDER BY 1"):
                    digest.update(repr(row).encode())
    return digest.hexdigest()
