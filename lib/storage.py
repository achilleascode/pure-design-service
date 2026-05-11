from __future__ import annotations

import base64
import os


def upload(job_id: str, png_bytes: bytes) -> str:
    """Persist image and return a serving URL.

    Strategy:
      - If POSTGRES_URL is set, store BYTEA in design_jobs and return /api/image?id=...
      - Otherwise return a data URL so the mock UI still displays the image.
    """
    if os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"):
        from lib import jobs
        try:
            jobs.update(job_id, image_bytes=png_bytes, image_mime="image/png")
            base = os.getenv("PUBLIC_BASE_URL", "")
            path = f"/api/image?id={job_id}"
            return f"{base}{path}" if base else path
        except Exception:
            pass
    b64 = base64.b64encode(png_bytes).decode()
    return f"data:image/png;base64,{b64}"
