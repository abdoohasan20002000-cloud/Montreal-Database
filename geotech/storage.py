"""Where contributors' files and their metadata cards live.

Supabase (Postgres table + Storage bucket) when SUPABASE_URL is set in secrets,
otherwise a local folder. Streamlit Community Cloud wipes local folders on every
restart, so the local backend is for trying the app only.
"""
import json
import os
import re
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

LOCAL_DIR = config.ROOT / "local_uploads"
# Used where there is no fcntl (Windows). Kept on sys so a live update that reloads this module reuses it.
_IN_MEMORY_LOCK = sys.__dict__.setdefault("_geotech_catalogue_lock", threading.Lock())


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id():
    return uuid.uuid4().hex[:12]


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]


class LocalStore:
    kind = "local folder (temporary)"
    temporary = True  # tested by the pages instead of the class, which a live update can replace

    def __init__(self, root: Path = LOCAL_DIR):
        self.root = root
        (root / "files").mkdir(parents=True, exist_ok=True)
        self.cat = root / "catalogue.json"

    @contextmanager
    def _turn(self):
        """Held while the catalogue is read and rewritten. It is a lock on a file, so changes take turns even across
        store objects (a live update builds a new one while visitors still hold the old) and processes."""
        if fcntl is None:  # Windows: one process, so a lock in memory does
            with _IN_MEMORY_LOCK:
                yield
            return
        with open(self.root / "catalogue.lock", "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _all(self):
        return json.loads(self.cat.read_text(encoding="utf-8")) if self.cat.exists() else []

    def _save(self, rows):
        # Written whole to a file of its own, then swapped in, so a reader never sees half a catalogue.
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix="catalogue.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.cat)

    def list(self, status=None):
        rows = self._all()
        return [r for r in rows if status is None or r["status"] == status]

    def add(self, record, data: bytes):
        path = f"{record['id']}/{safe_name(record['file_name'])}"
        p = self.root / "files" / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        record["storage_path"] = path
        with self._turn():
            self._save(self._all() + [record])

    def get_bytes(self, record) -> bytes:
        return (self.root / "files" / record["storage_path"]).read_bytes()

    def update(self, upload_id, **fields):
        with self._turn():
            rows = self._all()
            for r in rows:
                if r["id"] == upload_id:
                    r.update(fields)
            self._save(rows)


class SupabaseStore:
    kind = "Supabase"
    temporary = False

    def __init__(self, url, key, bucket="uploads"):
        from supabase import create_client
        self.client = create_client(url, key)
        self.bucket = bucket

    def list(self, status=None):
        q = self.client.table("uploads").select("*")
        if status:
            q = q.eq("status", status)
        rows = q.order("uploaded_at", desc=True).execute().data
        for r in rows:
            if isinstance(r.get("check_report"), str):
                r["check_report"] = json.loads(r["check_report"])
        return rows

    def add(self, record, data: bytes):
        path = f"{record['id']}/{safe_name(record['file_name'])}"
        self.client.storage.from_(self.bucket).upload(path, data, {"content-type": record.get("mime") or "application/octet-stream"})
        record["storage_path"] = path
        self.client.table("uploads").insert(record).execute()

    def get_bytes(self, record) -> bytes:
        return self.client.storage.from_(self.bucket).download(record["storage_path"])

    def update(self, upload_id, **fields):
        self.client.table("uploads").update(fields).eq("id", upload_id).execute()


def get_store(secrets):
    url = secrets.get("SUPABASE_URL") if secrets else None
    if url:
        return SupabaseStore(url, secrets["SUPABASE_SERVICE_KEY"], secrets.get("SUPABASE_BUCKET", "uploads"))
    return LocalStore()
