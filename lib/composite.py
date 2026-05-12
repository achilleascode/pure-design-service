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

BADGE_SIZE = 72
BADGE_Y = 28
BADGE_INNER_MARGIN = 36


def _trim_near_white_border(img: Image.Image, threshold: int = 245) -> Image.Image:
    """Gemini sometimes leaves a near-white padding on the sides of its output.
    Crop the image down to its actual content bbox before we fit it into the
    pouch slot, otherwise the white survives as visible stripes left and right
    of the motif."""
    rgb = np.array(img.convert("RGB"))
    not_white = (rgb[:, :, 0] < threshold) | (rgb[:, :, 1] < threshold) | (rgb[:, :, 2] < threshold)
    ys, xs = np.where(not_white)
    if len(xs) == 0 or len(ys) == 0:
        return img
    return img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")
    ki = _trim_near_white_border(ki)

    # 1. KI fits cleanly into the upper paper slot (above the baked warning).
    ai_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.5))
    backdrop.paste(ai_fitted, (SLOT_X, SLOT_Y), ai_fitted)

    # 2. Re-paste the warning as a top safety layer so the KI can never end up
    # painting over it — even if the slot constants drift in a future change.
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

    # 4. Real bud + leaves on top (Flower PSD layer).
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
