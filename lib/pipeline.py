from __future__ import annotations

import time
from typing import Any
from lib import prompt_builder, gemini_image, heuristics, vision_judge, composite, storage, jobs
from lib.gemini_image import GeminiSafetyBlock, GeminiImageError
from lib.settings import get_settings


async def run(job_id: str, user_prompt: str, t_start: float) -> dict[str, Any]:
    s = get_settings()
    attempts_log: list[dict[str, Any]] = []
    last_hint = ""

    for attempt in range(s.max_attempts):
        if time.time() - t_start > s.stage_timeout_total_s - 10:
            break

        variant = await prompt_builder.build(user_prompt, attempt, last_hint)
        a_t0 = time.time()
        log: dict[str, Any] = {
            "attempt": attempt,
            "model": variant.model,
            "temperature": variant.temperature,
            "seed": variant.seed,
            "image_prompt": variant.image_prompt[:300],
        }

        try:
            img_bytes = await gemini_image.generate(variant)
        except GeminiSafetyBlock as e:
            log["rejected_by"] = f"gemini_safety:{e}"
            attempts_log.append(log)
            last_hint = "safer abstract botanical motifs only, no people, no recognisable brands"
            continue
        except GeminiImageError as e:
            log["rejected_by"] = f"gemini_error:{e}"
            attempts_log.append(log)
            continue

        ok, why = heuristics.passes(img_bytes)
        log["heuristics"] = {"pass": ok, "reason": why}
        if not ok:
            log["rejected_by"] = f"heuristics:{why}"
            attempts_log.append(log)
            last_hint = f"previous output failed heuristic '{why}', produce richer detail and balanced exposure"
            continue

        verdict = await vision_judge.judge(img_bytes, user_prompt)
        log["vision_judge"] = verdict.model_dump()
        if not verdict.overall_pass:
            log["rejected_by"] = "vision_judge"
            attempts_log.append(log)
            last_hint = verdict.retry_hint or "improve composition centering, remove any text or logos"
            continue

        try:
            final_bytes = composite.composite(img_bytes)
            image_url = storage.upload(job_id, final_bytes)
        except Exception as e:
            log["rejected_by"] = f"composite_or_upload:{type(e).__name__}:{e}"
            attempts_log.append(log)
            continue

        log["latency_ms"] = int((time.time() - a_t0) * 1000)
        log["image_url"] = image_url
        attempts_log.append(log)

        total = int((time.time() - t_start) * 1000)
        jobs.update(
            job_id,
            status="done",
            final_image_url=image_url,
            attempts=attempts_log,
            total_latency_ms=total,
        )
        return {
            "status": "done",
            "image_url": image_url,
            "attempts": attempt + 1,
            "latency_ms": total,
        }

    total = int((time.time() - t_start) * 1000)
    jobs.update(
        job_id,
        status="failed",
        reason_code="all_attempts_exhausted",
        attempts=attempts_log,
        total_latency_ms=total,
    )
    return {
        "status": "failed",
        "reason": "all_attempts_exhausted",
        "attempts": len(attempts_log),
        "latency_ms": total,
    }
