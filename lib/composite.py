from io import BytesIO
from pathlib import Path
from PIL import Image


TEMPLATE_W, TEMPLATE_H = 1080, 1350
SLOT_X, SLOT_Y = 234, 135
SLOT_W, SLOT_H = 612, 918

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
OVERLAY_PATH = ASSETS_DIR / "bottom_overlay.png"


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    overlay = Image.open(OVERLAY_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    ki_resized = ki.resize((SLOT_W, SLOT_H), Image.LANCZOS)

    backdrop.paste(ki_resized, (SLOT_X, SLOT_Y), ki_resized)
    backdrop.paste(overlay, (0, 0), overlay)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
