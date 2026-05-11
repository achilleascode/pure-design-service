from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Any


def _db_path() -> str:
    return os.getenv("SQLITE_PATH", "/data/pure-design.db")


@contextmanager
def _conn():
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path, timeout=10.0, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=8000")
        yield c
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript("""
        create table if not exists design_jobs (
            id text primary key,
            created_at text default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            updated_at text default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
            user_prompt text not null,
            session_id text,
            status text not null,
            pre_filter text,
            attempts text default '[]',
            reason_code text,
            total_latency_ms integer,
            image_bytes blob,
            image_mime text default 'image/png'
        );
        create index if not exists design_jobs_status_idx on design_jobs(status);
        create index if not exists design_jobs_created_at_idx on design_jobs(created_at desc);
        """)


def insert(user_prompt: str, session_id: str | None) -> str:
    init_db()
    job_id = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            "insert into design_jobs (id, user_prompt, session_id, status) values (?, ?, ?, 'queued')",
            (job_id, user_prompt, session_id),
        )
    return job_id


def update(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    img_bytes = fields.pop("image_bytes", None)
    cols, vals = [], []
    for k, v in fields.items():
        cols.append(k)
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    if img_bytes is not None:
        cols.append("image_bytes")
        vals.append(sqlite3.Binary(img_bytes))
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    vals.append(job_id)
    with _conn() as c:
        c.execute(
            f"update design_jobs set {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') where id = ?",
            vals,
        )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for k in ("pre_filter", "attempts"):
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


def get(job_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute(
            """
            select id, created_at, updated_at, user_prompt, session_id, status,
                   pre_filter, attempts, reason_code, total_latency_ms, image_mime,
                   (image_bytes is not null) as has_image
            from design_jobs where id = ?
            """,
            (job_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None


def get_image(job_id: str) -> tuple[bytes, str] | None:
    with _conn() as c:
        row = c.execute(
            "select image_bytes, image_mime from design_jobs where id = ?",
            (job_id,),
        ).fetchone()
        if not row or row[0] is None:
            return None
        return bytes(row[0]), row[1] or "image/png"


def recent(limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            """
            select id, created_at, user_prompt, status, reason_code, total_latency_ms,
                   (image_bytes is not null) as has_image
            from design_jobs
            order by created_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
