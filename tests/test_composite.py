from io import BytesIO
from pathlib import Path
from PIL import Image

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lib.composite import (
    composite,
    TEMPLATE_W,
    TEMPLATE_H,
    POUCH_X,
    POUCH_Y,
    DESIGN_BBOX,
    WARN_BBOX,
)


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out))
    assert img.size == (TEMPLATE_W, TEMPLATE_H)


def test_composite_design_area_shows_ki():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = POUCH_X + (DESIGN_BBOX[0] + DESIGN_BBOX[2]) // 2
    cy = POUCH_Y + (DESIGN_BBOX[1] + DESIGN_BBOX[3]) // 2
    px = img.getpixel((cx, cy))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"Design centre not red, got {px}"


def test_composite_warning_yellow():
    out = composite(_synthetic_ki(color=(0, 0, 255, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = POUCH_X + (WARN_BBOX[0] + WARN_BBOX[2]) // 2
    samples = [img.getpixel((cx, POUCH_Y + y)) for y in range(WARN_BBOX[1] + 10, WARN_BBOX[3] - 10, 20)]
    yellow_hits = sum(1 for px in samples if px[0] > 200 and px[1] > 180 and px[2] < 100)
    assert yellow_hits >= 2, f"Warning band not yellow: {samples}"


def test_dynamic_frame_color():
    # red KI → scanning a row across the frame zone should hit reddish pixels somewhere
    out = composite(_synthetic_ki(color=(220, 30, 30, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    wx1, wy1, wx2, wy2 = WARN_BBOX
    # the rectangle outline is 6px wide just outside the warning bbox; scan ±10px around it
    cy = POUCH_Y + wy1 - 2  # inside the 6px frame outline (drawn at wy1-3..wy1+3)
    reddish = 0
    for x in range(POUCH_X + wx1, POUCH_X + wx2 + 1, 4):
        px = img.getpixel((x, cy))
        if px[0] > 150 and px[0] > px[1] + 40 and px[0] > px[2] + 40:
            reddish += 1
    assert reddish > 10, f"frame not reddish enough, hits={reddish}"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_design_area_shows_ki()
    test_composite_warning_yellow()
    test_dynamic_frame_color()
    print("All composite tests passed.")
