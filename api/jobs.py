from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import jobs as jobs_lib


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            rows = jobs_lib.recent(50)
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            body = json.dumps({"jobs": rows}, default=str).encode()
        except Exception as e:
            body = json.dumps({"error": f"{type(e).__name__}:{e}"}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
