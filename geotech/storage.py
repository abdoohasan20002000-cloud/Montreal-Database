"""Where contributors' files and their metadata cards live.

Supabase (Postgres table + Storage bucket) when SUPABASE_URL is set in secrets,
otherwise a local folder. Streamlit Community Cloud wipes local folders on every
restart, so the local backend is for trying the app only.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config

LOCAL_DIR = config.ROOT / "local_uploads"


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
        self._lock = threading.Lock()  # one store serves every visitor, so catalogue changes take turns

    def _all(self):
        return json.loads(self.cat.read_text(encoding="utf-8")) if self.cat.exists() else []

    def _save(self, rows):
        tmp = self.cat.with_suffix(".tmp")  # written whole, then swapped in, so a reader never sees half a file
        tmp.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
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
        with self._lock:
            self._save(self._all() + [record])

    def get_bytes(self, record) -> bytes:
        return (self.root / "files" / record["storage_path"]).read_bytes()

    def update(self, upload_id, **fields):
        with self._lock:
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
