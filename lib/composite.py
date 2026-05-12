from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350
SLOT_X, SLOT_Y = 234, 135
SLOT_W, SLOT_H = 612, 690  # upper 2/3 of the paper — bud overlay sits below

# Warning band — rendered fresh on every composite so we can draw a
# dynamically-coloured frame around it.
WARN_X, WARN_Y = 234, 825
WARN_W, WARN_H = 612, 345
WARN_FRAME = 10  # px of dynamic-colour rim around the warning

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
BUD_PATH = ASSETS_DIR / "bud_overlay.png"
TOP_FOLD_PATH = ASSETS_DIR / "top_fold.png"
WARN_PATH = ASSETS_DIR / "warning_clean.png"
LABELS_DIR = ASSETS_DIR / "labels"

BADGE_SIZE = 110
BADGE_POSITIONS = {
    "Label_Grammage.png":   (SLOT_X + 18,                        SLOT_Y + 18),
    "Label_Food_Grade.png": (SLOT_X + SLOT_W - 18 - BADGE_SIZE,  SLOT_Y + 18),
    "Label_CoA.png":        (SLOT_X + 18,                        SLOT_Y + SLOT_H - 18 - BADGE_SIZE),
}


def _dominant_color(img_rgb: Image.Image) -> tuple[int, int, int]:
    """Pick a vivid dominant colour from the KI image.

    Down-samples, quantises to a coarse palette to suppress noise, and prefers
    saturated colours over near-greys so the frame reads as on-brief rather
    than a muddy average.
    """
    small = img_rgb.resize((48, 48))
    pixels = list(small.getdata())
    quant = [(r // 24 * 24, g // 24 * 24, b // 24 * 24) for r, g, b in pixels]
    counts = Counter(quant).most_common(15)
    best = counts[0][0]
    best_score = -1.0
    for (r, g, b), n in counts:
        sat = max(r, g, b) - min(r, g, b)
        lum = (r + g + b) / 3
        # penalise very dark, near-black, near-white
        if lum < 30 or lum > 230:
            continue
        score = n * (1.0 + sat / 80.0)
        if score > best_score:
            best_score = score
            best = (r, g, b)
    # nudge toward saturated by boosting the dominant channel a bit
    r, g, b = best
    return (min(255, r + 12), min(255, g + 12), min(255, b + 12))


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")
    ki_rgb = ki.convert("RGB")

    # 1. KI fills upper 2/3 of the paper
    ki_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.45))
    backdrop.paste(ki_fitted, (SLOT_X, SLOT_Y), ki_fitted)

    # 2. Heat-seal fold on top of the KI — gives the 3D pouch illusion
    top_fold = Image.open(TOP_FOLD_PATH).convert("RGBA")
    backdrop.paste(top_fold, (0, 0), top_fold)

    # 3. Warning band with a dynamic-coloured frame around it.
    frame_color = _dominant_color(ki_rgb)
    frame_draw = ImageDraw.Draw(backdrop)
    frame_draw.rectangle(
        [
            (WARN_X - WARN_FRAME, WARN_Y - WARN_FRAME),
            (WARN_X + WARN_W + WARN_FRAME, WARN_Y + WARN_H + WARN_FRAME),
        ],
        fill=frame_color + (255,),
    )
    warning = Image.open(WARN_PATH).convert("RGBA")
    warning_fit = ImageOps.fit(warning, (WARN_W, WARN_H), Image.LANCZOS, centering=(0.5, 0.5))
    backdrop.paste(warning_fit, (WARN_X, WARN_Y), warning_fit)

    # 4. Real bud + leaves overlay — drawn AFTER the warning so it sits in front
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    # 5. Three transparent label badges on the KI region
    for fname, pos in BADGE_POSITIONS.items():
        badge = Image.open(LABELS_DIR / fname).convert("RGBA")
        badge = badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)
        backdrop.paste(badge, pos, badge)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
