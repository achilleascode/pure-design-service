from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np


TEMPLATE_W, TEMPLATE_H = 1080, 1350

# Studio paper slot — the bright rectangle in the backdrop, runs y=132..1164
# at x=234..846 (612×1032). The warning band has been baked into the lower
# third of this slot inside assets/backdrop_base.png.
PAPER_X, PAPER_Y = 234, 132
PAPER_W, PAPER_H = 612, 1032

# KI fills only the upper two-thirds; warning lives below. SLOT_Y overshoots
# the paper top by 2px on purpose so no white strip survives at the seam.
SLOT_X, SLOT_Y = PAPER_X, PAPER_Y - 2
SLOT_W, SLOT_H = PAPER_W, 822 - (PAPER_Y - 2)  # ends just before the warning
WARN_X, WARN_Y = 234, 820
WARN_W, WARN_H = 612, 350
DESIGN_BBOX = (SLOT_X, SLOT_Y, SLOT_X + SLOT_W, SLOT_Y + SLOT_H)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
WARNING_PATH = ASSETS_DIR / "warning.png"
BUD_PATH = ASSETS_DIR / "bud_overlay.png"
LABELS_DIR = ASSETS_DIR / "labels"

BADGE_SIZE = 88   # ~20% smaller than v9's 110
BADGE_Y = 30
BADGE_INNER_MARGIN = 40


def _trim_uniform_padding(img: Image.Image, std_threshold: float = 15.0) -> Image.Image:
    """Gemini regularly emits a uniform-colour padding band on the sides of its
    1024×1536 output — sometimes pure white, sometimes a flat pink-purple etc.
    A simple white-threshold misses the coloured padding and a stripe survives
    inside the pouch slot.

    Scan columns/rows from each edge inward; treat any row/column whose pixel
    stddev is below `std_threshold` as padding and crop past it once real
    content (higher variance) starts.
    """
    rgb = np.array(img.convert("RGB")).astype(np.float32)
    h, w, _ = rgb.shape

    left = 0
    for x in range(w // 2):
        if rgb[:, x, :].std() > std_threshold:
            left = x
            break
    right = w
    for x in range(w - 1, w // 2, -1):
        if rgb[:, x, :].std() > std_threshold:
            right = x + 1
            break
    top = 0
    for y in range(h // 2):
        if rgb[y, :, :].std() > std_threshold:
            top = y
            break
    bottom = h
    for y in range(h - 1, h // 2, -1):
        if rgb[y, :, :].std() > std_threshold:
            bottom = y + 1
            break
    if right <= left or bottom <= top:
        return img
    return img.crop((left, top, right, bottom))


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")
    ki = _trim_uniform_padding(ki)

    # 1. KI fits cleanly into the upper paper slot (above the baked warning).
    ai_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.5))
    backdrop.paste(ai_fitted, (SLOT_X, SLOT_Y), ai_fitted)

    # 2. Re-paste the warning as a top safety layer so the KI never paints
    # over it.
    warning = Image.open(WARNING_PATH).convert("RGBA")
    backdrop.paste(warning, (WARN_X, WARN_Y), warning)

    # 3. Three brand badges across the top of the KI area.
    badge_files = ("Label_Grammage.png", "Label_CoA.png", "Label_Food_Grade.png")
    n = len(badge_files)
    span = SLOT_W - 2 * BADGE_INNER_MARGIN
    gap = (span - n * BADGE_SIZE) // (n - 1)
    for i, fname in enumerate(badge_files):
        badge = Image.open(LABELS_DIR / fname).convert("RGBA")
        badge = badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)
        bx = SLOT_X + BADGE_INNER_MARGIN + i * (BADGE_SIZE + gap)
        by = SLOT_Y + BADGE_Y
        backdrop.paste(badge, (bx, by), badge)

    # 4. Bud + leaves last so the bud sits in FRONT of the warning — the leaf
    # tip overlaps the yellow band like the brand reference shows.
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
