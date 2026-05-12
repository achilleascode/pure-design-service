from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
import numpy as np


TEMPLATE_W, TEMPLATE_H = 1080, 1350
PAPER_X, PAPER_Y = 234, 135
PAPER_W, PAPER_H = 612, 1035

# 3D pouch template is 798x1338; we scale it down to fit the paper slot width.
POUCH_W = 612
_RAW_POUCH = (798, 1338)
POUCH_H = round(_RAW_POUCH[1] * POUCH_W / _RAW_POUCH[0])  # ~1026
POUCH_X = PAPER_X
POUCH_Y = PAPER_Y + (PAPER_H - POUCH_H) // 2  # ~139
_SCALE = POUCH_W / _RAW_POUCH[0]

# Source-coord regions inside the 798x1338 pouch template
_SRC_DESIGN_BBOX = (15, 132, 783, 880)   # the cyan/BUD design surface, to be replaced by the KI
_SRC_WARN_BBOX = (35, 893, 760, 1290)    # the yellow warning area on the pouch front

def _scale_bbox(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    return (round(x1 * _SCALE), round(y1 * _SCALE),
            round(x2 * _SCALE), round(y2 * _SCALE))

DESIGN_BBOX = _scale_bbox(_SRC_DESIGN_BBOX)
WARN_BBOX = _scale_bbox(_SRC_WARN_BBOX)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
POUCHE_PATH = ASSETS_DIR / "pouche_3d.png"
BUD_PATH = ASSETS_DIR / "bud_overlay.png"
LABELS_DIR = ASSETS_DIR / "labels"

# Constants kept for backwards-compat with tests / external callers
SLOT_X, SLOT_Y = POUCH_X, POUCH_Y + DESIGN_BBOX[1]
SLOT_W = DESIGN_BBOX[2] - DESIGN_BBOX[0]
SLOT_H = DESIGN_BBOX[3] - DESIGN_BBOX[1]
BADGE_SIZE = 88

# Third badge (CoA) added as an overlay — the pouch render already carries
# Grammage (top-left) and Food-Grade (top-right) in 3D.
_COA_SIZE = 70


def _dominant_color(img_rgb: Image.Image) -> tuple[int, int, int]:
    small = img_rgb.resize((48, 48))
    pixels = list(small.getdata())
    quant = [(r // 24 * 24, g // 24 * 24, b // 24 * 24) for r, g, b in pixels]
    counts = Counter(quant).most_common(20)
    best = counts[0][0]
    best_score = -1.0
    for (r, g, b), n in counts:
        sat = max(r, g, b) - min(r, g, b)
        lum = (r + g + b) / 3
        if lum < 35 or lum > 225:
            continue
        score = n * (1.0 + sat / 70.0)
        if score > best_score:
            best_score = score
            best = (r, g, b)
    r, g, b = best
    return (min(255, r + 15), min(255, g + 15), min(255, b + 15))


def _pouche_with_hole() -> Image.Image:
    """Load pouche_3d, scale to width POUCH_W, knock out the design area's alpha
    so the KI image placed underneath shows through."""
    pouche = Image.open(POUCHE_PATH).convert("RGBA")
    pouche = pouche.resize((POUCH_W, POUCH_H), Image.LANCZOS)
    arr = np.array(pouche)
    x1, y1, x2, y2 = DESIGN_BBOX
    arr[y1:y2, x1:x2, 3] = 0
    return Image.fromarray(arr, "RGBA")


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")
    ki_rgb = ki.convert("RGB")

    # 1. KI fitted into the pouch's design surface
    dx1, dy1, dx2, dy2 = DESIGN_BBOX
    design_w, design_h = dx2 - dx1, dy2 - dy1
    ki_fitted = ImageOps.fit(ki, (design_w, design_h), Image.LANCZOS, centering=(0.5, 0.45))
    backdrop.paste(ki_fitted, (POUCH_X + dx1, POUCH_Y + dy1))

    # 2. 3D pouch overlay with the design hole punched out — gives us the
    # rounded silhouette, heat-seal fold, built-in badges, drop shadow and
    # warning band in one shot.
    backdrop.paste(_pouche_with_hole(), (POUCH_X, POUCH_Y), _pouche_with_hole())

    # 3. Dynamic-colour frame around the warning band (inside the pouch).
    frame_color = _dominant_color(ki_rgb)
    wx1, wy1, wx2, wy2 = WARN_BBOX
    draw = ImageDraw.Draw(backdrop)
    draw.rectangle(
        [(POUCH_X + wx1 - 3, POUCH_Y + wy1 - 3),
         (POUCH_X + wx2 + 3, POUCH_Y + wy2 + 3)],
        outline=frame_color + (255,),
        width=6,
    )

    # 4. Real bud + leaves on top (Flower layer extracted from the backdrop PSD).
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    # 5. Third badge (CoA) — Grammage and Food-Grade are already in the pouch render.
    coa = Image.open(LABELS_DIR / "Label_CoA.png").convert("RGBA")
    coa = coa.resize((_COA_SIZE, _COA_SIZE), Image.LANCZOS)
    # bottom-left of the design surface, just above the warning — avoids the
    # built-in Grammage / Food-Grade badges at the top of the pouch.
    coa_x = POUCH_X + dx1 + 18
    coa_y = POUCH_Y + dy2 - _COA_SIZE - 18
    backdrop.paste(coa, (coa_x, coa_y), coa)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
