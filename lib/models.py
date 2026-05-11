from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    lang: Optional[str] = "de"


class GenerateResponse(BaseModel):
    job_id: str
    status: Literal["queued"] = "queued"


class StatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "done", "failed", "rejected"]
    image_url: Optional[str] = None
    reason_code: Optional[str] = None
    attempts: int = 0


class PromptVariant(BaseModel):
    image_prompt: str
    negative_prompt: str
    aspect_ratio: str = "2:3"
    image_size: str = "1K"
    seed: int = 0
    temperature: float = 0.7
    model: str = ""


class PreFilterResult(BaseModel):
    allow: bool
    reason: str = ""
    category: str = "ok"
    flagged_terms: list[str] = []


class VisionChecks(BaseModel):
    no_text_in_image: bool
    no_foreign_logos: bool
    no_minors_or_humans: bool
    composition_centered: bool
    on_brief_similarity: float
    detected_brands: list[str] = []


class VisionVerdict(BaseModel):
    overall_pass: bool
    checks: VisionChecks
    retry_hint: str = ""
