from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350
SLOT_X, SLOT_Y = 234, 135
SLOT_W, SLOT_H = 612, 1035  # fills entire studio paper (y=135..1170)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
OVERLAY_PATH = ASSETS_DIR / "bottom_overlay.png"


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    overlay = Image.open(OVERLAY_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    # ImageOps.fit center-crops + resizes so the slot is fully covered
    # without horizontal/vertical stretching when KI aspect differs from slot.
    # centering=(0.5, 0.4) keeps a bit more of the upper half.
    ki_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.4))

    backdrop.paste(ki_fitted, (SLOT_X, SLOT_Y), ki_fitted)
    backdrop.paste(overlay, (0, 0), overlay)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
