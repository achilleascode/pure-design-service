import json
import random
import httpx
from lib.models import PromptVariant
from lib.settings import get_settings


BRAND_GUIDE = (
    "Brand: Pure Cannabis (CH/EU, CBD <1% THC). "
    "Visual style: cinematic, photo-realistic, vivid colour, high detail. "
    "Output must be 2:3 portrait (taller than wide). "
    "Central composition with ~10% padding from edges. "
    "Lower-right area should remain visually calm — keep main subject in upper 2/3 and centre. "
    "Vocabulary: replace 'weed/joint/smoke/high' with 'hemp/CBD/botanical/wellness'."
)

DEFAULT_NEGATIVE = (
    "text, letters, words, numbers, captions, labels, logos, brand marks, watermarks, "
    "frames, borders, packaging mockup, pouch, doypack, studio backdrop, red floor, "
    "studio curtain, cannabis leaves at lower-right corner, hands, fingers, faces, "
    "people, persons, children, low quality, blurry, distorted"
)

# escalation strategies per retry attempt
ESCALATION = [
    {"temperature": 0.7, "extra_negative": ""},
    {"temperature": 0.85, "extra_negative": ", duplicate subject, off-centre, cropped"},
    {"temperature": 1.0, "extra_negative": ", any text whatsoever, any logo whatsoever, any photographic frame edges"},
]


async def build(user_prompt: str, attempt: int = 0, retry_hint: str = "") -> PromptVariant:
    settings = get_settings()
    esc = ESCALATION[min(attempt, len(ESCALATION) - 1)]
    seed = random.randint(1, 2**31 - 1)

    if not settings.gemini_api_key:
        return PromptVariant(
            image_prompt=f"{user_prompt}. {BRAND_GUIDE}",
            negative_prompt=DEFAULT_NEGATIVE + esc["extra_negative"],
            seed=seed,
            temperature=esc["temperature"],
            model=settings.image_model if attempt < 2 else settings.image_model_pro,
        )

    system = (
        "Du bist Prompt-Engineer fuer einen Bild-Generator. "
        "Konvertiere den User-Wunsch in ein praezises englisches Image-Prompt, "
        "das die Brand-Guideline einhaelt. " + BRAND_GUIDE + " "
        "Antworte STRICT als JSON mit den Feldern image_prompt und negative_prompt. "
        "Kein Markdown, kein Kommentar."
    )
    user_msg = f"USER_WUNSCH: {user_prompt}\n"
    if retry_hint:
        user_msg += f"VORHERIGES_FEEDBACK: {retry_hint}\n"
    user_msg += f"ATTEMPT: {attempt}"

    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {
            "temperature": 0.4,
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
        f"{settings.text_model}:generateContent"
    )
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.post(
                url,
                headers={"x-goog-api-key": settings.gemini_api_key,
                         "Content-Type": "application/json"},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            image_prompt = parsed.get("image_prompt", user_prompt)
            neg = parsed.get("negative_prompt", DEFAULT_NEGATIVE)
            full_negative = neg + esc["extra_negative"]
        except Exception:
            image_prompt = f"{user_prompt}. {BRAND_GUIDE}"
            full_negative = DEFAULT_NEGATIVE + esc["extra_negative"]

    model = settings.image_model if attempt < 2 else settings.image_model_pro
    return PromptVariant(
        image_prompt=image_prompt,
        negative_prompt=full_negative,
        seed=seed,
        temperature=esc["temperature"],
        model=model,
    )
