from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
import numpy as np


TEMPLATE_W, TEMPLATE_H = 1080, 1350
PAPER_X, PAPER_Y = 234, 135
PAPER_W, PAPER_H = 612, 1035

# Pouch render is 798x1338 and fully fills the paper slot once scaled.
POUCH_W = PAPER_W
_RAW_POUCH = (798, 1338)
POUCH_H = round(_RAW_POUCH[1] * POUCH_W / _RAW_POUCH[0])  # ~1026
POUCH_X = PAPER_X
POUCH_Y = PAPER_Y + (PAPER_H - POUCH_H) // 2
_SCALE = POUCH_W / _RAW_POUCH[0]

# Warning area in source pouch coordinates (798x1338).
_SRC_WARN_BBOX = (35, 893, 760, 1290)

# Design area in source pouch coords — everything between the top badge row and
# the warning. This whole rectangle is wiped (alpha=0) so the KI underneath
# shows through, removing the baked "TRUE BUD PREMIUM CBD INDOOR QUALITY"
# typography that ships with the pouch render.
_SRC_DESIGN_BBOX = (15, 130, 783, 880)

# Pouch cyan that should be punched out and replaced by the KI.
_POUCH_CYAN = np.array([49, 184, 222], dtype=np.int16)
_CYAN_TOLERANCE = 75

# Studio backdrop red — used to repaint the bare paper so the rounded pouch
# corners do not reveal a white border.
_STUDIO_RED = (157, 57, 58, 255)

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
POUCHE_PATH = ASSETS_DIR / "pouche_3d.png"
BUD_PATH = ASSETS_DIR / "bud_overlay.png"
LABELS_DIR = ASSETS_DIR / "labels"


def _scale_bbox(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(round(v * _SCALE) for v in bbox)  # type: ignore


WARN_BBOX = _scale_bbox(_SRC_WARN_BBOX)
DESIGN_BBOX = _scale_bbox(_SRC_DESIGN_BBOX)
SLOT_X, SLOT_Y = POUCH_X, POUCH_Y
SLOT_W, SLOT_H = POUCH_W, POUCH_H
BADGE_SIZE = 88
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


def _load_pouche_scaled() -> tuple[Image.Image, np.ndarray]:
    pouche = Image.open(POUCHE_PATH).convert("RGBA").resize((POUCH_W, POUCH_H), Image.LANCZOS)
    return pouche, np.array(pouche)


def _strip_pouche_design(arr: np.ndarray) -> Image.Image:
    """Make the pouch overlay show only the structural pieces — badges, warning,
    heat-seal line, drop-shadow — and let the KI underneath fill the rest.

    1) Wipe the design rectangle entirely (kills the baked TRUE/BUD typography).
    2) Chroma-key out any remaining pouch-cyan elsewhere (top fold cyan-band
       between badges, etc.) so the KI shows under the badges' surround too.
    """
    out = arr.copy()
    dx1, dy1, dx2, dy2 = DESIGN_BBOX
    out[dy1:dy2, dx1:dx2, 3] = 0

    rgb = out[:, :, :3].astype(np.int32)
    diff = rgb - _POUCH_CYAN
    dist = np.sqrt(np.sum(diff * diff, axis=2))
    out[dist < _CYAN_TOLERANCE, 3] = 0
    return Image.fromarray(out, "RGBA")


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")
    ki_rgb = ki.convert("RGB")

    # 0. Repaint the white paper area with the studio red, otherwise the
    # rounded pouch corners reveal a white margin around the pouch.
    ImageDraw.Draw(backdrop).rectangle(
        (PAPER_X, PAPER_Y, PAPER_X + PAPER_W, PAPER_Y + PAPER_H), fill=_STUDIO_RED
    )

    pouche, arr = _load_pouche_scaled()
    silhouette = pouche.split()[3]

    # 1. KI fitted to the pouch bbox and clipped to the pouch silhouette so it
    # takes the rounded corners + heat-seal shape — no flat rectangle edges.
    ai_fitted = ImageOps.fit(ki, (POUCH_W, POUCH_H), Image.LANCZOS, centering=(0.5, 0.45))
    ai_in_pouch = Image.new("RGBA", (POUCH_W, POUCH_H), (0, 0, 0, 0))
    ai_in_pouch.paste(ai_fitted, (0, 0))
    ai_in_pouch.putalpha(silhouette)
    backdrop.paste(ai_in_pouch, (POUCH_X, POUCH_Y), ai_in_pouch)

    # 2. Pouch overlay stripped of its baked design + cyan background, leaving
    # only the 3D structural elements (badges, warning, heat-seal, shadow).
    pouche_keyed = _strip_pouche_design(arr)
    backdrop.paste(pouche_keyed, (POUCH_X, POUCH_Y), pouche_keyed)

    # 3. Dynamic-colour frame around the warning band — picks up the KI
    # dominant colour so the rim feels on-brief.
    frame_color = _dominant_color(ki_rgb)
    wx1, wy1, wx2, wy2 = WARN_BBOX
    ImageDraw.Draw(backdrop).rectangle(
        [(POUCH_X + wx1 - 3, POUCH_Y + wy1 - 3),
         (POUCH_X + wx2 + 3, POUCH_Y + wy2 + 3)],
        outline=frame_color + (255,),
        width=6,
    )

    # 4. CoA badge — Grammage + Food-Grade are already baked into the pouch.
    coa = Image.open(LABELS_DIR / "Label_CoA.png").convert("RGBA")
    coa = coa.resize((_COA_SIZE, _COA_SIZE), Image.LANCZOS)
    backdrop.paste(
        coa,
        (POUCH_X + 18, POUCH_Y + wy1 - _COA_SIZE - 18),
        coa,
    )

    # 5. Real bud + leaves on top of everything (Flower PSD layer).
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
