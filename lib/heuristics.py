from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageStat
import numpy as np


def laplacian_variance(arr: np.ndarray) -> float:
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    h, w = arr.shape
    a = arr.astype(np.float32)
    pad = np.pad(a, 1, mode="edge")
    out = np.zeros_like(a)
    for dy in range(3):
        for dx in range(3):
            k = kernel[dy, dx]
            if k:
                out += k * pad[dy:dy + h, dx:dx + w]
    return float(out.var())


def passes(img_bytes: bytes) -> tuple[bool, str]:
    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        return False, f"decode_error:{type(e).__name__}"

    mean = ImageStat.Stat(img).mean
    avg_brightness = sum(mean) / len(mean)
    if avg_brightness < 25:
        return False, f"too_dark:{avg_brightness:.1f}"
    if avg_brightness > 230:
        return False, f"too_bright:{avg_brightness:.1f}"

    small = img.resize((256, 256))
    arr = np.asarray(small, dtype=np.uint8)
    var = laplacian_variance(arr)
    if var < 80:
        return False, f"too_blurry_or_flat:lap_var={var:.1f}"

    hist = np.histogram(arr, bins=32, range=(0, 256))[0]
    nonzero_bins = (hist > 10).sum()
    if nonzero_bins < 5:
        return False, f"too_monotone:bins={nonzero_bins}"

    return True, "ok"
