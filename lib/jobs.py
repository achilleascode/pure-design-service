from __future__ import annotations

import json
import os
import uuid
from typing import Any


def _has_db() -> bool:
    return bool(os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"))


def _conn():
    import psycopg2
    url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("POSTGRES_URL not set")
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return psycopg2.connect(url)


def insert(user_prompt: str, session_id: str | None) -> str:
    if not _has_db():
        return str(uuid.uuid4())
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            insert into design_jobs (user_prompt, session_id, status)
            values (%s, %s, 'queued') returning id::text
            """,
            (user_prompt, session_id),
        )
        return cur.fetchone()[0]


def update(job_id: str, **fields: Any) -> None:
    if not fields or not _has_db():
        return
    import psycopg2
    from psycopg2.extras import Json
    img_bytes = fields.pop("image_bytes", None)
    cols = list(fields.keys())
    values: list[Any] = []
    for k in cols:
        v = fields[k]
        if isinstance(v, (dict, list)):
            values.append(Json(v))
        else:
            values.append(v)
    if img_bytes is not None:
        cols.append("image_bytes")
        values.append(psycopg2.Binary(img_bytes))
    set_clause = ", ".join(f"{c} = %s" for c in cols)
    values.append(job_id)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            f"update design_jobs set {set_clause}, updated_at = now() where id = %s",
            values,
        )


def get(job_id: str) -> dict[str, Any] | None:
    if not _has_db():
        return None
    from psycopg2.extras import RealDictCursor
    with _conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            select id::text, created_at, updated_at, user_prompt, session_id,
                   status, pre_filter, attempts, reason_code, total_latency_ms,
                   image_mime, (image_bytes is not null) as has_image
            from design_jobs where id = %s
            """,
            (job_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_image(job_id: str) -> tuple[bytes, str] | None:
    if not _has_db():
        return None
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "select image_bytes, image_mime from design_jobs where id = %s",
            (job_id,),
        )
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return bytes(row[0]), row[1] or "image/png"


def recent(limit: int = 24) -> list[dict[str, Any]]:
    if not _has_db():
        return []
    from psycopg2.extras import RealDictCursor
    with _conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            select id::text, created_at, user_prompt, status, reason_code,
                   total_latency_ms, (image_bytes is not null) as has_image
            from design_jobs
            order by created_at desc
            limit %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
