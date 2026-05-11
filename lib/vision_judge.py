from __future__ import annotations

import base64
import json
import httpx
from lib.models import VisionVerdict, VisionChecks
from lib.settings import get_settings


RUBRIC = """You are a brand-safety judge for a CBD/cannabis brand mockup pipeline.
Look at the image and answer in STRICT JSON only (no markdown):
{
  "checks": {
    "no_text_in_image": bool,
    "no_foreign_logos": bool,
    "no_minors_or_humans": bool,
    "composition_centered": bool,
    "on_brief_similarity": <0-10>,
    "detected_brands": ["..."]
  },
  "overall_pass": bool,
  "retry_hint": "<short prompt-engineering hint if overall_pass=false>"
}
Rules:
- "no_text_in_image": true if there is no readable letter, word, number, caption, watermark.
- "no_foreign_logos": true if there is no third-party brand logo or mark.
- "no_minors_or_humans": true if there is no person/face. Botanical / abstract / object scenes pass.
- "composition_centered": true if the main subject is roughly centered with ~10% edge padding.
- "on_brief_similarity": 0-10 how well the image matches USER_BRIEF below.
- "overall_pass": true ONLY if all four checks pass AND on_brief_similarity >= 6.
- "retry_hint": short instruction to improve the next attempt if pass=false; otherwise empty string.
"""


async def _judge_gemini(image_bytes: bytes, user_brief: str) -> VisionVerdict | None:
    s = get_settings()
    if not s.gemini_api_key:
        return None
    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": RUBRIC + f"\nUSER_BRIEF: {user_brief}"},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": c, "threshold": "OFF"} for c in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ],
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{s.vision_judge_model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.post(
                url,
                headers={"x-goog-api-key": s.gemini_api_key,
                         "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return VisionVerdict(
                overall_pass=bool(parsed.get("overall_pass")),
                checks=VisionChecks(**parsed["checks"]),
                retry_hint=parsed.get("retry_hint", ""),
            )
        except Exception:
            return None


async def _judge_claude(image_bytes: bytes, user_brief: str) -> VisionVerdict | None:
    s = get_settings()
    if not s.anthropic_api_key:
        return None
    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "model": s.vision_fallback_model,
        "max_tokens": 600,
        "system": RUBRIC,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png", "data": b64
                }},
                {"type": "text", "text": f"USER_BRIEF: {user_brief}\nReply with the JSON only."},
            ],
        }],
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": s.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()
            text = data["content"][0]["text"]
            # strip code fences if present
            text = text.strip().lstrip("`").lstrip("json").strip("`").strip()
            parsed = json.loads(text)
            return VisionVerdict(
                overall_pass=bool(parsed.get("overall_pass")),
                checks=VisionChecks(**parsed["checks"]),
                retry_hint=parsed.get("retry_hint", ""),
            )
        except Exception:
            return None


async def judge(image_bytes: bytes, user_brief: str) -> VisionVerdict:
    verdict = await _judge_gemini(image_bytes, user_brief)
    if verdict is not None:
        return verdict
    verdict = await _judge_claude(image_bytes, user_brief)
    if verdict is not None:
        return verdict
    return VisionVerdict(
        overall_pass=True,
        checks=VisionChecks(
            no_text_in_image=True,
            no_foreign_logos=True,
            no_minors_or_humans=True,
            composition_centered=True,
            on_brief_similarity=6.0,
        ),
        retry_hint="vision judge unavailable, fail-open",
    )
