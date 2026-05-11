from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350

# Paper bounds inside the studio backdrop
PAPER_X, PAPER_Y = 234, 135
PAPER_W, PAPER_H = 612, 1035

# Padding inside paper for brand elements
LOGO_PAD_TOP = 45
WARNING_PAD_BOT = 200  # lifts warning above the buds region in the overlay
GAP = 30

# Logo placement (typographic //pure)
LOGO_W, LOGO_H = 281, 90
LOGO_X = PAPER_X + (PAPER_W - LOGO_W) // 2
LOGO_Y = PAPER_Y + LOGO_PAD_TOP

# Warning placement (DE/FR/IT health text, ~85% of paper width)
WARNING_W, WARNING_H = 520, 299
WARNING_X = PAPER_X + (PAPER_W - WARNING_W) // 2
WARNING_Y = PAPER_Y + PAPER_H - WARNING_PAD_BOT - WARNING_H

# KI slot — sits between logo and warning with GAP each side
SLOT_X = PAPER_X
SLOT_Y = LOGO_Y + LOGO_H + GAP
SLOT_W = PAPER_W
SLOT_H = WARNING_Y - SLOT_Y - GAP

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
OVERLAY_PATH = ASSETS_DIR / "bottom_overlay.png"
LOGO_PATH = ASSETS_DIR / "pure_logo.png"
WARNING_PATH = ASSETS_DIR / "warning.png"


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    overlay = Image.open(OVERLAY_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    # KI inside slot — center crop to fit (no stretching)
    ki_fitted = ImageOps.fit(ki, (SLOT_W, SLOT_H), Image.LANCZOS, centering=(0.5, 0.45))

    # Layer order: KI → logo → warning → bottom overlay (always on very top)
    backdrop.paste(ki_fitted, (SLOT_X, SLOT_Y), ki_fitted)

    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_r = logo.resize((LOGO_W, LOGO_H), Image.LANCZOS) if logo.size != (LOGO_W, LOGO_H) else logo
        backdrop.paste(logo_r, (LOGO_X, LOGO_Y), logo_r)

    if WARNING_PATH.exists():
        warn = Image.open(WARNING_PATH).convert("RGBA")
        warn_r = warn.resize((WARNING_W, WARNING_H), Image.LANCZOS) if warn.size != (WARNING_W, WARNING_H) else warn
        backdrop.paste(warn_r, (WARNING_X, WARNING_Y), warn_r)

    backdrop.paste(overlay, (0, 0), overlay)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
