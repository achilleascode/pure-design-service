"""Regenerate derived assets in assets/ from raw sources.

Outputs:
  assets/backdrop_base.png     — original studio backdrop, no warning baked in
  assets/bud_overlay.png       — only the bud + leaves (transparent elsewhere),
                                 paste over KI to put the real bud in front
  assets/top_fold.png          — heat-seal strip with centre notch, gives the
                                 KI a 3D pouch-fold illusion
  assets/warning_clean.png     — yellow warning content cropped tight (no dark frame)
  assets/labels/Label_*.png    — labels with full alpha + true-black ink (no grey edges)
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import numpy as np

ROOT = Path(__file__).parent.parent
SRC_DIR = Path("/Users/achisumma/Downloads/KI_Packaging_Design_Sources")
SRC_BACKDROP = SRC_DIR / "Backdrop" / "KI_Packaging_Design_Backdrop.png"
SRC_WARNING = SRC_DIR / "Warning" / "PNG" / "Warning.png"
SRC_LABELS = SRC_DIR / "Labels" / "PNG"

ASSETS = ROOT / "assets"
LABELS_OUT = ASSETS / "labels"

# Studio red-floor colour, used as the chroma-key when extracting the bud
RED_FLOOR = np.array([158, 57, 58], dtype=np.int16)
RED_TOLERANCE = 42       # any pixel within this distance to RED_FLOOR is treated as background
BLACK_THRESHOLD = 9      # luminance below this is studio wall → background


def build_backdrop():
    bd = Image.open(SRC_BACKDROP).convert("RGBA")
    assert bd.size == (1080, 1350)
    bd.save(ASSETS / "backdrop_base.png", format="PNG", optimize=True)


def build_bud_overlay():
    """Color-key the bottom-right bud out of the studio backdrop."""
    bd = Image.open(SRC_BACKDROP).convert("RGBA")
    arr = np.array(bd)
    rgb = arr[:, :, :3].astype(np.int16)

    h, w = arr.shape[:2]
    alpha = np.zeros((h, w), dtype=np.uint8)

    # Bud area — kept tight so we don't pick up paper or studio walls
    y1, y2, x1, x2 = 1075, 1285, 730, 995
    region = rgb[y1:y2, x1:x2]
    dist_red = np.sqrt(np.sum((region - RED_FLOOR) ** 2, axis=2))
    lum = region.mean(axis=2)
    # also drop near-paper-white (R>180 G>175 B>170)
    paper = (region[:, :, 0] > 180) & (region[:, :, 1] > 175) & (region[:, :, 2] > 170)
    keep = (dist_red > RED_TOLERANCE) & (lum > BLACK_THRESHOLD) & ~paper
    alpha[y1:y2, x1:x2] = np.where(keep, 255, 0).astype(np.uint8)

    # Soft edges
    alpha_img = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(radius=0.8))
    out = bd.copy()
    out.putalpha(alpha_img)
    out.save(ASSETS / "bud_overlay.png", format="PNG", optimize=True)


def build_top_fold():
    """Heat-seal strip at the top of the pouch with a small centre notch.

    Sits at y=135..168 in the 1080x1350 backdrop frame, full SLOT_W wide.
    Mid-grey body + soft drop shadow below → 3D fold illusion.
    """
    SLOT_X, SLOT_Y = 234, 135
    SLOT_W = 612
    SEAL_H = 33
    SHADOW_H = 14

    canvas = Image.new("RGBA", (1080, 1350), (0, 0, 0, 0))
    seal = Image.new("RGBA", (SLOT_W, SEAL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(seal)

    # Body of the seal: slightly off-white, very subtle texture via a gradient
    for y in range(SEAL_H):
        # darken toward bottom for a folded look
        t = y / max(1, SEAL_H - 1)
        v = int(245 - 35 * t)            # 245 → 210
        draw.rectangle([(0, y), (SLOT_W - 1, y)], fill=(v, v, v, 255))

    # Centre notch: a small dark triangle gap
    notch_w = 28
    cx = SLOT_W // 2
    draw.polygon(
        [(cx - notch_w // 2, 0), (cx + notch_w // 2, 0), (cx, SEAL_H - 8)],
        fill=(60, 38, 30, 255),
    )

    # Drop shadow underneath (separate strip blurred)
    shadow = Image.new("RGBA", (SLOT_W, SHADOW_H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    for y in range(SHADOW_H):
        a = int(120 * (1 - y / SHADOW_H))
        sdraw.rectangle([(0, y), (SLOT_W - 1, y)], fill=(0, 0, 0, a))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2.5))

    canvas.paste(seal, (SLOT_X, SLOT_Y), seal)
    canvas.paste(shadow, (SLOT_X, SLOT_Y + SEAL_H - 2), shadow)
    canvas.save(ASSETS / "top_fold.png", format="PNG", optimize=True)


def build_warning_clean():
    """Crop the source Warning.png to just the yellow content area (drop the dark frame)."""
    warn = Image.open(SRC_WARNING).convert("RGBA")
    arr = np.array(warn)
    rgb = arr[:, :, :3]
    # the dark frame is essentially R<60 AND G<60. Find bbox of non-frame pixels.
    is_content = (rgb[:, :, 0] > 80) | (rgb[:, :, 1] > 80)
    ys, xs = np.where(is_content)
    if len(xs) == 0:
        warn.save(ASSETS / "warning_clean.png")
        return
    y1, y2 = ys.min(), ys.max()
    x1, x2 = xs.min(), xs.max()
    cropped = warn.crop((x1, y1, x2 + 1, y2 + 1))
    cropped.save(ASSETS / "warning_clean.png", format="PNG", optimize=True)


def build_labels():
    """Re-save labels with their black ink forced to pure black (no grey-on-dark fringing)."""
    LABELS_OUT.mkdir(exist_ok=True)
    for fname in ("Label_CoA.png", "Label_Food_Grade.png", "Label_Grammage.png"):
        src = SRC_LABELS / fname
        img = Image.open(src).convert("RGBA")
        arr = np.array(img)
        rgb = arr[:, :, :3].astype(np.int16)
        a = arr[:, :, 3]
        # Anything below ~120 luminance on an opaque pixel → force RGB to pure black
        lum = rgb.mean(axis=2)
        mask = (lum < 120) & (a > 60)
        arr[mask, 0] = 0
        arr[mask, 1] = 0
        arr[mask, 2] = 0
        # Boost alpha of the dark ink so it doesn't read as grey when blended
        arr[mask, 3] = np.maximum(arr[mask, 3], 240)
        out = Image.fromarray(arr, "RGBA")
        out.save(LABELS_OUT / fname, format="PNG", optimize=True)


def main():
    ASSETS.mkdir(exist_ok=True)
    build_backdrop()
    build_bud_overlay()
    build_top_fold()
    build_warning_clean()
    build_labels()
    print("Assets regenerated.")


if __name__ == "__main__":
    main()
