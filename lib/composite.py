from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350
SLOT_X, SLOT_Y = 234, 135
SLOT_W, SLOT_H = 612, 690  # 2/3 of the paper (lower 1/3 has the warning baked into the backdrop)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
LABELS_DIR = ASSETS_DIR / "labels"

BADGE_SIZE = 80
BADGE_POSITIONS = {
    "Label_Grammage.png":   (SLOT_X + 15,                        SLOT_Y + 15),
    "Label_Food_Grade.png": (SLOT_X + SLOT_W - 15 - BADGE_SIZE,  SLOT_Y + 15),
    "Label_CoA.png":        (SLOT_X + 15,                        SLOT_Y + SLOT_H - 15 - BADGE_SIZE),
}


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    ki_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.5))
    backdrop.paste(ki_fitted, (SLOT_X, SLOT_Y), ki_fitted)

    for fname, pos in BADGE_POSITIONS.items():
        badge = Image.open(LABELS_DIR / fname).convert("RGBA")
        badge = badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)
        backdrop.paste(badge, pos, badge)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
