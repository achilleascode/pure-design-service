from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350

# === Layout: KI fills top 2/3, yellow warning strip bottom 1/3 ===
KI_H = (TEMPLATE_H * 2) // 3              # 900
WARNING_STRIP_H = TEMPLATE_H - KI_H       # 450
WARNING_STRIP_Y = KI_H                    # 900

# === Logo watermark on KI ===
LOGO_W = 320
LOGO_H = 80
LOGO_X = (TEMPLATE_W - LOGO_W) // 2
LOGO_Y = 50

# === Warning image inside yellow strip (centered, with margin) ===
WARNING_PAD = 30
_warn_h_max = WARNING_STRIP_H - WARNING_PAD * 2          # 390
_warn_w_max = TEMPLATE_W - WARNING_PAD * 2               # 1020
# warning.png is 1040x599 → aspect 1.7362
WARNING_ASPECT = 1000 / 532
WARNING_H = _warn_h_max
WARNING_W = int(WARNING_H * WARNING_ASPECT)
if WARNING_W > _warn_w_max:
    WARNING_W = _warn_w_max
    WARNING_H = int(WARNING_W / WARNING_ASPECT)
WARNING_X = (TEMPLATE_W - WARNING_W) // 2
WARNING_Y = WARNING_STRIP_Y + (WARNING_STRIP_H - WARNING_H) // 2

# === Colors ===
WARNING_BG_COLOR = (242, 215, 26, 255)   # match warning.png yellow
DOMAIN_COLOR = (30, 20, 0, 255)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "pure_logo.png"
WARNING_PATH = ASSETS_DIR / "warning.png"


def composite(ki_bytes: bytes) -> bytes:
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    canvas = Image.new("RGBA", (TEMPLATE_W, TEMPLATE_H), (0, 0, 0, 255))

    # 1) KI cover-fits the top 2/3 region
    ki_fitted = ImageOps.fit(ki, (TEMPLATE_W, KI_H), Image.LANCZOS, centering=(0.5, 0.5))
    canvas.alpha_composite(ki_fitted, (0, 0))

    # 2) Yellow warning strip — full-width, bottom 1/3
    strip = Image.new("RGBA", (TEMPLATE_W, WARNING_STRIP_H), WARNING_BG_COLOR)
    canvas.alpha_composite(strip, (0, WARNING_STRIP_Y))

    # 3) Warning image centered inside strip (preserves aspect)
    if WARNING_PATH.exists():
        warn = Image.open(WARNING_PATH).convert("RGBA").resize(
            (WARNING_W, WARNING_H), Image.LANCZOS
        )
        canvas.alpha_composite(warn, (WARNING_X, WARNING_Y))

    # 4) //pure logo watermark, top-center, NO drop shadow (clean overlay)
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA").resize(
            (LOGO_W, LOGO_H), Image.LANCZOS
        )
        canvas.alpha_composite(logo, (LOGO_X, LOGO_Y))

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
