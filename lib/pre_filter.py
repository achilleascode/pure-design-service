from __future__ import annotations

import json
import re
import httpx
from lib.models import PreFilterResult
from lib.settings import get_settings


HARD_BLOCK = {
    "child", "children", "kid", "kids", "minor", "minors", "teen", "teenager",
    "baby", "infant", "underage", "youth",
    "weapon", "gun", "rifle", "pistol", "knife", "blade", "blood", "gore",
    "naked", "nude", "porn", "sex", "sexual", "explicit",
    "cocaine", "heroin", "meth", "fentanyl", "crack",
    "nike", "adidas", "puma", "cookies cannabis", "stiiizy", "raw rolling",
    "marlboro", "philip morris",
}

CANNABIS_OK = {
    "bud", "buds", "flower", "flowers", "nug", "nugs", "trichome", "trichomes",
    "terpene", "terpenes", "indica", "sativa", "hybrid", "strain", "strains",
    "hemp", "cbd", "cannabinoid", "cannabinoids", "cannabis", "wellness",
    "botanical", "herb", "plant",
}

WORD_RE = re.compile(r"[a-zA-ZäöüÄÖÜßéèêàçñ]+")


def rule_check(prompt: str) -> PreFilterResult | None:
    text = prompt.lower()
    tokens = set(WORD_RE.findall(text))
    hits = tokens & HARD_BLOCK
    if hits:
        return PreFilterResult(
            allow=False,
            reason=f"Blocked term detected: {', '.join(sorted(hits))}",
            category="rule_block",
            flagged_terms=sorted(hits),
        )
    bigrams = re.findall(r"[a-z]+ [a-z]+", text)
    for bg in bigrams:
        if bg in HARD_BLOCK:
            return PreFilterResult(
                allow=False, reason=f"Blocked phrase: {bg}",
                category="rule_block", flagged_terms=[bg],
            )
    return None


async def llm_judge(prompt: str) -> PreFilterResult:
    settings = get_settings()
    if not settings.gemini_api_key:
        return PreFilterResult(allow=True, reason="LLM judge skipped (no API key)", category="ok")
    system = (
        "Du bist Compliance-Filter für einen legalen Cannabis-Verpackungs-Mockup-Service "
        "(CBD <1% THC, CH/EU). "
        "ERLAUBT: Cannabis-Buds, Hanf-Pflanzen, Trichome, abstrakte/psychedelische Muster, "
        "Strain-Ästhetik, natur-/botanische Motive, Verpackungs-relevante Visuals. "
        "VERBOTEN: Personen unter 25 (auch Anschein), aktive Konsum-Darstellung, andere "
        "Marken-Logos/Namen, Schrift/Text als Hauptmotiv, illegale Drogen (Kokain, Heroin), "
        "Waffen, sexueller Content, Hassmotive. "
        "Antworte STRICT als JSON: "
        '{"allow": bool, "reason": "kurze Begruendung", '
        '"flagged_terms": ["term1"], '
        '"category": "minor|brand|text|drugs|nsfw|weapon|hate|ok"}.'
    )
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": f"USER_PROMPT: {prompt}"}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": c, "threshold": "OFF"}
            for c in (
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
            return PreFilterResult(**parsed)
        except Exception as e:
            return PreFilterResult(
                allow=True,
                reason=f"LLM judge error, fail-open: {type(e).__name__}",
                category="ok",
            )


async def run(prompt: str) -> PreFilterResult:
    settings = get_settings()
    rule = rule_check(prompt)
    if rule is not None:
        return rule
    if getattr(settings, "fast_mode", False):
        return PreFilterResult(allow=True, category="ok", reason="rule-only (fast_mode)")
    return await llm_judge(prompt)
