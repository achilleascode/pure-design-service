from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


TEMPLATE_W, TEMPLATE_H = 1080, 1350

# === Logo watermark (top-center, white-tinted, drop shadow) ===
LOGO_W = 380           # ~35% of template width
LOGO_H = 113           # aspect 672/168 = 4.0
LOGO_X = (TEMPLATE_W - LOGO_W) // 2
LOGO_Y = 80
LOGO_TINT = (255, 255, 255)      # white
LOGO_OPACITY = 1.0
LOGO_SHADOW_OFFSET = (0, 8)
LOGO_SHADOW_BLUR = 18
LOGO_SHADOW_OPACITY = 0.6

# === Warning band at bottom (full-width yellow strip) ===
WARNING_STRIP_H = 240
WARNING_PAD_TOP = 24
WARNING_BG_COLOR = (242, 215, 26, 255)
WARNING_H = WARNING_STRIP_H - WARNING_PAD_TOP * 2 - 40  # leave space for URL line under
WARNING_W = int(WARNING_H * (1040 / 599))               # preserve aspect 1.735
if WARNING_W > TEMPLATE_W - 100:
    WARNING_W = TEMPLATE_W - 100
    WARNING_H = int(WARNING_W * (599 / 1040))
WARNING_X = (TEMPLATE_W - WARNING_W) // 2
WARNING_Y = TEMPLATE_H - WARNING_STRIP_H + WARNING_PAD_TOP

# === Domain text under warning (inside the strip) ===
DOMAIN_TEXT = "WWW.PURE-CANNABIS.COM"
DOMAIN_COLOR = (40, 30, 0, 255)

# === KI image: full bleed (1080x1350 cover) ===
KI_CENTERING = (0.5, 0.5)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "pure_logo.png"
WARNING_PATH = ASSETS_DIR / "warning.png"


def _tint(img: Image.Image, color: tuple[int, int, int], opacity: float = 1.0) -> Image.Image:
    """Recolor a transparent-bg glyph image to a single colour, preserving alpha."""
    r, g, b, a = img.split()
    tinted = Image.merge("RGBA", (
        Image.new("L", img.size, color[0]),
        Image.new("L", img.size, color[1]),
        Image.new("L", img.size, color[2]),
        a.point(lambda v: int(v * opacity)),
    ))
    return tinted


def _drop_shadow(img: Image.Image, offset: tuple[int, int], blur: int, opacity: float) -> Image.Image:
    """Return a new RGBA with a drop-shadow halo + img on top."""
    pad = blur * 2 + max(abs(offset[0]), abs(offset[1]))
    w, h = img.size
    base = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    shadow_mask = img.split()[-1].point(lambda v: int(v * opacity))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 255))
    shadow.putalpha(shadow_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(shadow, (pad + offset[0], pad + offset[1]))
    base.alpha_composite(img, (pad, pad))
    return base


def _font(size: int) -> ImageFont.FreeTypeFont:
    """Best-effort font loading; falls back to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def composite(ki_bytes: bytes) -> bytes:
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    # 1) KI as full-bleed canvas (center-crop to 1080x1350)
    canvas = ImageOps.fit(ki, (TEMPLATE_W, TEMPLATE_H), Image.LANCZOS, centering=KI_CENTERING)

    # 2) Bottom warning strip — full-width opaque yellow
    strip = Image.new("RGBA", (TEMPLATE_W, WARNING_STRIP_H), WARNING_BG_COLOR)
    canvas.alpha_composite(strip, (0, TEMPLATE_H - WARNING_STRIP_H))

    if WARNING_PATH.exists():
        warn = Image.open(WARNING_PATH).convert("RGBA").resize((WARNING_W, WARNING_H), Image.LANCZOS)
        canvas.alpha_composite(warn, (WARNING_X, WARNING_Y))

    # 3) Domain text below warning, inside strip
    draw = ImageDraw.Draw(canvas)
    domain_font = _font(20)
    bbox = draw.textbbox((0, 0), DOMAIN_TEXT, font=domain_font)
    tx = (TEMPLATE_W - (bbox[2] - bbox[0])) // 2
    ty = TEMPLATE_H - 32
    draw.text((tx, ty), DOMAIN_TEXT, font=domain_font, fill=DOMAIN_COLOR)

    # 4) //pure watermark — top-center, white, drop shadow
    if LOGO_PATH.exists():
        logo_src = Image.open(LOGO_PATH).convert("RGBA").resize((LOGO_W, LOGO_H), Image.LANCZOS)
        logo_white = _tint(logo_src, LOGO_TINT, LOGO_OPACITY)
        logo_with_shadow = _drop_shadow(
            logo_white, LOGO_SHADOW_OFFSET, LOGO_SHADOW_BLUR, LOGO_SHADOW_OPACITY
        )
        pad = LOGO_SHADOW_BLUR * 2 + max(abs(LOGO_SHADOW_OFFSET[0]), abs(LOGO_SHADOW_OFFSET[1]))
        canvas.alpha_composite(logo_with_shadow, (LOGO_X - pad, LOGO_Y - pad))

    out = BytesIO()
    canvas.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
