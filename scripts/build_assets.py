"""Regenerate derived assets in assets/ from raw sources.

Outputs:
  assets/backdrop_base.png     — original studio backdrop with the yellow
                                 warning notice BAKED INTO the lower 1/3 of
                                 the white paper slot (hardcoded background).
  assets/warning.png           — the same warning at its final 612×344 size,
                                 kept as a separate asset so it can be
                                 re-pasted as a top safety layer.
  assets/bud_overlay.png       — `Flower` pixel layer extracted from the
                                 backdrop PSD; clean designer alpha.
  assets/labels/Label_*.png    — labels with true-black ink, full alpha.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import numpy as np
from psd_tools import PSDImage

ROOT = Path(__file__).parent.parent
SRC_DIR = Path("/Users/achisumma/Downloads/KI_Packaging_Design_Sources")
SRC_BACKDROP_PSD = SRC_DIR / "Backdrop" / "KI_Packaging_Design_Backdrop.psd"
SRC_BACKDROP_PNG = SRC_DIR / "Backdrop" / "KI_Packaging_Design_Backdrop.png"
SRC_WARNING_PNG = SRC_DIR / "Warning" / "PNG" / "Warning.png"
SRC_LABELS = SRC_DIR / "Labels" / "PNG"

ASSETS = ROOT / "assets"
LABELS_OUT = ASSETS / "labels"

# Position inside the studio paper (paper = x=234..846, y=132..1164, 612×1032).
# The warning occupies the lower third; KI fills the upper two thirds.
WARN_X, WARN_Y = 234, 820
WARN_W, WARN_H = 612, 350  # extends 6px past the natural paper edge to bury the tiny white seam

# Yellow content bbox inside the source Warning.png (10769x6208, dark frame ~506px)
_WARN_CONTENT_BBOX = (506, 506, 10262, 5701)


def build_warning() -> Image.Image:
    """Crop the yellow content from the source warning, resize it slightly
    smaller than the final slot, then wrap it in a dark frame matching the
    pouche reference design.

    Final asset is 612×344 with a 10px dark border around 592×324 of yellow."""
    border = 10
    dark_frame_color = (38, 37, 36, 255)  # sampled from Pouche reference at y=1300

    src = Image.open(SRC_WARNING_PNG).convert("RGBA")
    cropped = src.crop(_WARN_CONTENT_BBOX)
    inner = cropped.resize((WARN_W - 2 * border, WARN_H - 2 * border), Image.LANCZOS)

    warn = Image.new("RGBA", (WARN_W, WARN_H), dark_frame_color)
    warn.paste(inner, (border, border))
    warn.save(ASSETS / "warning.png", format="PNG", optimize=True)
    return warn


def build_backdrop_with_warning(warning: Image.Image) -> None:
    """Bake the warning into the lower 1/3 of the studio backdrop's white paper."""
    bd = Image.open(SRC_BACKDROP_PNG).convert("RGBA")
    assert bd.size == (1080, 1350)
    bd.paste(warning, (WARN_X, WARN_Y), warning)
    bd.save(ASSETS / "backdrop_base.png", format="PNG", optimize=True)


def build_bud_overlay() -> None:
    """Extract the Flower pixel layer directly from the PSD — already alpha-cut by the designer."""
    psd = PSDImage.open(SRC_BACKDROP_PSD)
    for layer in psd:
        if layer.name == "Flower":
            img = layer.composite()
            assert img.size == (1080, 1350)
            img.save(ASSETS / "bud_overlay.png", format="PNG", optimize=True)
            return
    raise RuntimeError("Flower layer not found in backdrop PSD")


def build_labels() -> None:
    LABELS_OUT.mkdir(exist_ok=True)
    for fname in ("Label_CoA.png", "Label_Food_Grade.png", "Label_Grammage.png"):
        src = SRC_LABELS / fname
        img = Image.open(src).convert("RGBA")
        arr = np.array(img)
        rgb = arr[:, :, :3].astype(np.int16)
        a = arr[:, :, 3]
        lum = rgb.mean(axis=2)
        mask = (lum < 120) & (a > 60)
        arr[mask, 0] = 0
        arr[mask, 1] = 0
        arr[mask, 2] = 0
        arr[mask, 3] = np.maximum(arr[mask, 3], 240)
        Image.fromarray(arr, "RGBA").save(LABELS_OUT / fname, format="PNG", optimize=True)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    warning = build_warning()
    build_backdrop_with_warning(warning)
    build_bud_overlay()
    build_labels()
    # remove obsolete assets from previous iterations
    for stale in ("top_fold.png", "warning_clean.png", "pouche_3d.png"):
        p = ASSETS / stale
        if p.exists():
            p.unlink()
    print("Assets regenerated.")


if __name__ == "__main__":
    main()
