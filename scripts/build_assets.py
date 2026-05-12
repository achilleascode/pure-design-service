"""Regenerate derived assets in assets/ from raw sources.

Outputs:
  assets/backdrop_base.png     — original studio backdrop, no warning baked in
  assets/bud_overlay.png       — Flower layer extracted directly from the PSD
                                 (clean alpha, no manual chroma-keying)
  assets/pouche_3d.png         — pre-rendered 3D pouch with shading, fold,
                                 built-in Grammage + Food-Grade badges,
                                 and the warning baked in
  assets/labels/Label_*.png    — labels with true-black ink, full alpha
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image
import numpy as np
from psd_tools import PSDImage

ROOT = Path(__file__).parent.parent
SRC_DIR = Path("/Users/achisumma/Downloads/KI_Packaging_Design_Sources")
SRC_BACKDROP_PSD = SRC_DIR / "Backdrop" / "KI_Packaging_Design_Backdrop.psd"
SRC_POUCHE_PSD = SRC_DIR / "Pouche" / "PSD" / "doypack_true_bud_85x140.psd"
SRC_BACKDROP_PNG = SRC_DIR / "Backdrop" / "KI_Packaging_Design_Backdrop.png"
SRC_LABELS = SRC_DIR / "Labels" / "PNG"

ASSETS = ROOT / "assets"
LABELS_OUT = ASSETS / "labels"


def build_backdrop():
    bd = Image.open(SRC_BACKDROP_PNG).convert("RGBA")
    assert bd.size == (1080, 1350)
    bd.save(ASSETS / "backdrop_base.png", format="PNG", optimize=True)


def build_bud_overlay():
    """Extract the Flower pixel layer directly from the PSD — already alpha-cut by the designer."""
    psd = PSDImage.open(SRC_BACKDROP_PSD)
    for layer in psd:
        if layer.name == "Flower":
            img = layer.composite()
            assert img.size == (1080, 1350)
            img.save(ASSETS / "bud_overlay.png", format="PNG", optimize=True)
            return
    raise RuntimeError("Flower layer not found in backdrop PSD")


def build_pouche_3d():
    """Extract the noise-reduced 3D rendered pouch from the Pouche PSD."""
    psd = PSDImage.open(SRC_POUCHE_PSD)
    for layer in psd:
        if layer.name.startswith("Gerendertes Bild (mit"):
            img = layer.topil()
            img.save(ASSETS / "pouche_3d.png", format="PNG", optimize=True)
            return
    raise RuntimeError("Pouche render layer not found")


def build_labels():
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
        out = Image.fromarray(arr, "RGBA")
        out.save(LABELS_OUT / fname, format="PNG", optimize=True)


def main():
    ASSETS.mkdir(exist_ok=True)
    build_backdrop()
    build_bud_overlay()
    build_pouche_3d()
    build_labels()
    # remove obsolete assets from previous iterations
    for stale in ("top_fold.png", "warning_clean.png"):
        p = ASSETS / stale
        if p.exists():
            p.unlink()
    print("Assets regenerated.")


if __name__ == "__main__":
    main()
