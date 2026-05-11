from __future__ import annotations

import os
from lib import jobs


def upload(job_id: str, png_bytes: bytes) -> str:
    """Store image bytes in the design_jobs row and return a serving URL."""
    jobs.update(job_id, image_bytes=png_bytes, image_mime="image/png")
    base = os.getenv("PUBLIC_BASE_URL", "")
    path = f"/api/image?id={job_id}"
    return f"{base}{path}" if base else path
