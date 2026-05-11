from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lib import jobs, pipeline, pre_filter
from lib.settings import get_settings


app = FastAPI(title="Pure Design Generator", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

ROOT = Path(__file__).parent
PUBLIC_DIR = ROOT / "public"


class GenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


@app.on_event("startup")
def _startup():
    try:
        jobs.init_db()
    except Exception as e:
        print(f"[startup] DB init warning: {e}")


@app.get("/", include_in_schema=False)
def root_index():
    idx = PUBLIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"service": "pure-design-generator", "ui": "missing /public/index.html"}


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "service": "pure-design-generator",
        "fast_mode": s.fast_mode,
        "model": s.image_model,
        "has_gemini_key": bool(s.gemini_api_key),
    }


@app.post("/api/generate")
async def generate(body: GenerateBody, request: Request):
    t0 = time.time()
    pre = await pre_filter.run(body.prompt)
    try:
        job_id = jobs.insert(body.prompt, body.session_id)
    except Exception as e:
        raise HTTPException(500, f"db_insert_error:{type(e).__name__}:{e}")

    if not pre.allow:
        try:
            jobs.update(
                job_id,
                status="rejected",
                pre_filter=pre.model_dump(),
                reason_code=pre.category,
                total_latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception:
            pass
        return {
            "job_id": job_id,
            "status": "rejected",
            "reason": pre.reason,
            "category": pre.category,
        }

    try:
        jobs.update(job_id, pre_filter=pre.model_dump(), status="processing")
    except Exception:
        pass

    result = await pipeline.run(job_id, body.prompt, t0)
    result["job_id"] = job_id
    if result.get("status") != "done":
        return JSONResponse(status_code=502, content=result)
    return result


@app.get("/api/image")
def image(id: str):
    try:
        res = jobs.get_image(id)
    except Exception as e:
        raise HTTPException(500, f"db_error:{type(e).__name__}")
    if not res:
        raise HTTPException(404, "not_found")
    body, mime = res
    return Response(content=body, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/jobs")
def jobs_list(limit: int = 50):
    try:
        rows = jobs.recent(min(max(limit, 1), 200))
    except Exception as e:
        raise HTTPException(500, f"db_error:{type(e).__name__}")
    return {"jobs": rows}


@app.get("/api/job/{job_id}")
def job_detail(job_id: str):
    try:
        row = jobs.get(job_id)
    except Exception as e:
        raise HTTPException(500, f"db_error:{type(e).__name__}")
    if not row:
        raise HTTPException(404, "not_found")
    return row


# Static assets (HTML/CSS/JS) under /public/* — mounted last so /api/* matches first.
if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
