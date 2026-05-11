from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import pre_filter, jobs, pipeline


def _send(handler, code: int, payload: dict):
    body = json.dumps(payload).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


async def _run(prompt: str, session_id: str | None) -> tuple[int, dict]:
    t0 = time.time()
    pre = await pre_filter.run(prompt)
    job_id = jobs.insert(prompt, session_id)

    if not pre.allow:
        jobs.update(
            job_id,
            status="rejected",
            pre_filter=pre.model_dump(),
            reason_code=pre.category,
            total_latency_ms=int((time.time() - t0) * 1000),
        )
        return 200, {
            "job_id": job_id,
            "status": "rejected",
            "reason": pre.reason,
            "category": pre.category,
        }

    jobs.update(job_id, pre_filter=pre.model_dump(), status="processing")
    result = await pipeline.run(job_id, prompt, t0)
    result["job_id"] = job_id
    code = 200 if result["status"] == "done" else 502
    return code, result


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw or b"{}")
        except Exception as e:
            return _send(self, 400, {"error": f"bad_json:{type(e).__name__}"})

        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            return _send(self, 400, {"error": "prompt_required"})
        if len(prompt) > 2000:
            return _send(self, 400, {"error": "prompt_too_long"})

        session_id = data.get("session_id")

        try:
            code, payload = asyncio.run(_run(prompt, session_id))
        except Exception as e:
            return _send(self, 500, {"error": f"server:{type(e).__name__}:{e}"})

        return _send(self, code, payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        return _send(self, 200, {"ok": True, "service": "pure-design-generator", "method": "POST /api/generate"})
