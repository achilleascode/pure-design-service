from io import BytesIO
from pathlib import Path
from PIL import Image

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lib.composite import composite, TEMPLATE_W, TEMPLATE_H, SLOT_X, SLOT_Y, SLOT_W, SLOT_H


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out))
    assert img.size == (TEMPLATE_W, TEMPLATE_H)


def test_composite_slot_filled():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = SLOT_X + SLOT_W // 2
    cy = SLOT_Y + SLOT_H // 2
    px = img.getpixel((cx, cy))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"Slot centre not red, got {px}"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_slot_filled()
    print("All composite tests passed.")
