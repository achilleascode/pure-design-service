from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
import numpy as np


TEMPLATE_W, TEMPLATE_H = 1080, 1350

# Slightly oversize the red-fill so it covers the real studio paper area
# (which extends from y=133..1164, x=235..844) without leaving a white edge.
PAPER_X, PAPER_Y = 226, 122
PAPER_W, PAPER_H = 628, 1052

# Pouch occupies the paper slot exactly (width matches paper interior 612).
POUCH_W = 612
_RAW_POUCH = (798, 1338)
POUCH_H = round(_RAW_POUCH[1] * POUCH_W / _RAW_POUCH[0])  # ~1026
POUCH_X = 234
POUCH_Y = 135 + (1035 - POUCH_H) // 2  # ~139
_SCALE = POUCH_W / _RAW_POUCH[0]

# Source-coord regions inside the 798x1338 pouch template
_SRC_WARN_BBOX = (35, 893, 760, 1290)
# Wipe the whole upper face (including baked badges) so the KI fills it cleanly
# — we add our own badges on top in known positions.
_SRC_KI_BBOX = (8, 8, 790, 880)

# Studio backdrop red, sampled from the floor — used to repaint the paper.
_STUDIO_RED = (157, 57, 58, 255)

# Chroma-key threshold around the pouch cyan (RGB ~49, 184, 222) — wide enough
# to also strip the slightly lighter heat-seal band at the very top.
_POUCH_CYAN = np.array([49, 184, 222], dtype=np.int32)
_CYAN_TOLERANCE = 90

ASSETS_DIR = Path(__file__).parent.parent / "assets"
BACKDROP_PATH = ASSETS_DIR / "backdrop_base.png"
POUCHE_PATH = ASSETS_DIR / "pouche_3d.png"
BUD_PATH = ASSETS_DIR / "bud_overlay.png"
LABELS_DIR = ASSETS_DIR / "labels"


def _scale_bbox(bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return tuple(round(v * _SCALE) for v in bbox)  # type: ignore


WARN_BBOX = _scale_bbox(_SRC_WARN_BBOX)
DESIGN_BBOX = _scale_bbox(_SRC_KI_BBOX)
SLOT_X, SLOT_Y = POUCH_X, POUCH_Y
SLOT_W, SLOT_H = POUCH_W, POUCH_H

BADGE_SIZE = 72
BADGE_Y = 55  # clear of the pouch's rounded-corner arc


def _load_pouche_scaled() -> tuple[Image.Image, np.ndarray]:
    pouche = Image.open(POUCHE_PATH).convert("RGBA").resize((POUCH_W, POUCH_H), Image.LANCZOS)
    return pouche, np.array(pouche)


def _strip_pouche_to_structure(arr: np.ndarray) -> Image.Image:
    """Return the pouch render with everything OUTSIDE the warning band stripped.

    Keeps: drop shadow at the very bottom, the warning yellow + black text + dark
    border. Drops: heat-seal cyan band, baked badges, cyan design surface and
    the TRUE/BUD/PREMIUM CBD typography.
    """
    out = arr.copy()
    # Wipe the whole upper face so the KI underneath shows through cleanly.
    kx1, ky1, kx2, ky2 = DESIGN_BBOX
    out[ky1:ky2, kx1:kx2, 3] = 0
    # Then chroma-key everything still cyan (rounded corners, heat-seal band).
    rgb = out[:, :, :3].astype(np.int32)
    diff = rgb - _POUCH_CYAN
    dist = np.sqrt(np.sum(diff * diff, axis=2))
    out[dist < _CYAN_TOLERANCE, 3] = 0
    return Image.fromarray(out, "RGBA")


def _ki_alpha_mask(silhouette: Image.Image) -> Image.Image:
    """Pouch silhouette capped at the top edge of the warning band — KI is not
    allowed to bleed into the yellow warning."""
    arr = np.array(silhouette)
    arr[WARN_BBOX[1] - 2:, :] = 0
    return Image.fromarray(arr, "L")


def _shading_layer(pouche: Image.Image) -> Image.Image:
    """Extract the slow lighting variations from the 3D pouch render and convert
    them into a soft-light overlay. Heavy blur first removes the BUD typography
    so only the body shading + drop-shadow remains.
    """
    blurred = pouche.convert("L").filter(ImageFilter.GaussianBlur(radius=18))
    arr = np.array(blurred).astype(np.float32)
    mean = arr.mean()
    # delta around mean → [-1, 1] scaled gain
    delta = (arr - mean) / max(1.0, mean)
    delta = np.clip(delta, -0.55, 0.55)
    # Convert into an RGBA layer of mid-grey with variable alpha so it lightens
    # bright spots and darkens shadowed spots when blended in soft-light style.
    h, w = arr.shape
    layer = np.zeros((h, w, 4), dtype=np.uint8)
    layer[..., 0] = 128
    layer[..., 1] = 128
    layer[..., 2] = 128
    # encode brightness/darkness as one rgb channel: bright→white, dark→black
    bright = (delta > 0)
    dark = (delta < 0)
    layer[bright, 0] = 255
    layer[bright, 1] = 255
    layer[bright, 2] = 255
    layer[dark, 0] = 0
    layer[dark, 1] = 0
    layer[dark, 2] = 0
    alpha = np.clip(np.abs(delta) * 255 * 1.4, 0, 255).astype(np.uint8)
    layer[..., 3] = alpha
    return Image.fromarray(layer, "RGBA")


def composite(ki_bytes: bytes) -> bytes:
    backdrop = Image.open(BACKDROP_PATH).convert("RGBA")
    ki = Image.open(BytesIO(ki_bytes)).convert("RGBA")

    # 0. Cover the studio paper completely with the studio red so the rounded
    # pouch corners do not reveal any white at top or sides.
    ImageDraw.Draw(backdrop).rectangle(
        (PAPER_X, PAPER_Y, PAPER_X + PAPER_W, PAPER_Y + PAPER_H), fill=_STUDIO_RED
    )

    pouche, arr = _load_pouche_scaled()
    silhouette = pouche.split()[3]
    ki_mask = _ki_alpha_mask(silhouette)

    # 1. KI fitted into the pouch silhouette, capped above the warning band.
    ai_fitted = ImageOps.fit(ki, (POUCH_W, POUCH_H), Image.LANCZOS, centering=(0.5, 0.52))
    ai_in_pouch = ai_fitted.convert("RGBA")
    ai_in_pouch.putalpha(ki_mask)
    backdrop.paste(ai_in_pouch, (POUCH_X, POUCH_Y), ai_in_pouch)

    # 2. 3D shading overlay derived from the pouche render's blurred luminance,
    # masked to the KI region only so it does not darken the warning.
    shading = _shading_layer(pouche)
    shading.putalpha(ImageChops.multiply(shading.split()[3], ki_mask))
    backdrop.paste(shading, (POUCH_X, POUCH_Y), shading)

    # 3. Structural pouch overlay (warning band + drop shadow) — no violet
    # frame any more, the pouch render's own dark border around the warning
    # stays.
    pouche_struct = _strip_pouche_to_structure(arr)
    backdrop.paste(pouche_struct, (POUCH_X, POUCH_Y), pouche_struct)

    # 4. Three badges in a single top row, positioned inside the pouch.
    badge_files = ("Label_Grammage.png", "Label_CoA.png", "Label_Food_Grade.png")
    n = len(badge_files)
    inner_margin = 60  # stays inside the pouch's rounded top corners
    span = POUCH_W - 2 * inner_margin
    gap = (span - n * BADGE_SIZE) // (n - 1)
    for i, fname in enumerate(badge_files):
        bx = POUCH_X + inner_margin + i * (BADGE_SIZE + gap)
        by = POUCH_Y + BADGE_Y
        badge = Image.open(LABELS_DIR / fname).convert("RGBA")
        badge = badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)
        backdrop.paste(badge, (bx, by), badge)

    # 5. Real bud + leaves on top (Flower PSD layer).
    bud = Image.open(BUD_PATH).convert("RGBA")
    backdrop.paste(bud, (0, 0), bud)

    out = BytesIO()
    backdrop.save(out, format="PNG", optimize=True)
    return out.getvalue()
