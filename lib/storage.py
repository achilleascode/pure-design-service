from __future__ import annotations

import os
from lib import jobs


def upload(job_id: str, png_bytes: bytes) -> str:
    """Persist image in SQLite and return a serving URL."""
    try:
        jobs.update(job_id, image_bytes=png_bytes, image_mime="image/png")
    except Exception:
        pass
    base = os.getenv("PUBLIC_BASE_URL", "")
    path = f"/api/image?id={job_id}"
    return f"{base}{path}" if base else path
