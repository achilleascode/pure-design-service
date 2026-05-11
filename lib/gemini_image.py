import base64
import httpx
from lib.models import PromptVariant
from lib.settings import get_settings


class GeminiImageError(Exception):
    pass


class GeminiSafetyBlock(GeminiImageError):
    pass


async def generate(variant: PromptVariant) -> bytes:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiImageError("GEMINI_API_KEY not set")

    prompt_text = (
        variant.image_prompt
        + "\n\nDO NOT INCLUDE: " + variant.negative_prompt
    )

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": variant.aspect_ratio,
                "imageSize": variant.image_size,
            },
            "temperature": variant.temperature,
            "candidateCount": 1,
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
        f"{variant.model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=22.0) as client:
        r = await client.post(
            url,
            headers={"x-goog-api-key": settings.gemini_api_key,
                     "Content-Type": "application/json"},
            json=body,
        )
        if r.status_code != 200:
            raise GeminiImageError(
                f"HTTP {r.status_code}: {r.text[:500]}"
            )
        data = r.json()

    pf = data.get("promptFeedback") or {}
    if pf.get("blockReason"):
        raise GeminiSafetyBlock(f"Prompt blocked: {pf.get('blockReason')}")

    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiImageError("No candidates in response")
    cand = candidates[0]
    if cand.get("finishReason") == "SAFETY":
        raise GeminiSafetyBlock("Output blocked by safety filter")

    parts = (cand.get("content") or {}).get("parts") or []
    for p in parts:
        inline = p.get("inline_data") or p.get("inlineData")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise GeminiImageError("No inline image data in response")
