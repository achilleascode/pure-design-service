import os
from functools import lru_cache
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings(BaseModel):
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    postgres_url: str = ""
    public_base_url: str = ""
    image_model: str = "gemini-3.1-flash-image-preview"
    image_model_pro: str = "gemini-3-pro-image-preview"
    text_model: str = "gemini-2.5-flash"
    vision_judge_model: str = "gemini-3-pro"
    vision_fallback_model: str = "claude-sonnet-4-7"

    fast_mode: bool = True  # Vercel Hobby (10s) friendly: skip LLM prompt-build + vision-judge
    max_attempts: int = 1
    stage_timeout_gemini_s: int = 8
    stage_timeout_judge_s: int = 3
    stage_timeout_total_s: int = 9


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        postgres_url=os.getenv("POSTGRES_URL", os.getenv("DATABASE_URL", "")),
        public_base_url=os.getenv("PUBLIC_BASE_URL", ""),
        fast_mode=os.getenv("FAST_MODE", "1") != "0",
    )
