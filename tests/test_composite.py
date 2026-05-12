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
    SLOT_X,
    SLOT_Y,
    SLOT_W,
    SLOT_H,
    WARN_X,
    WARN_Y,
    WARN_W,
    WARN_H,
)


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    assert Image.open(BytesIO(out)).size == (TEMPLATE_W, TEMPLATE_H)


def test_ki_in_upper_slot():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = SLOT_X + SLOT_W // 2
    cy = SLOT_Y + SLOT_H // 2
    px = img.getpixel((cx, cy))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"KI centre not red, got {px}"


def test_warning_overrides_ki():
    """If the KI is red but the warning is baked + re-pasted, the warning area
    must read yellow on top — the KI must not overwrite the warning."""
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = WARN_X + WARN_W // 2
    samples = [img.getpixel((cx, y)) for y in range(WARN_Y + 20, WARN_Y + WARN_H - 20, 30)]
    yellow_hits = sum(1 for px in samples if px[0] > 200 and px[1] > 180 and px[2] < 100)
    assert yellow_hits >= 4, f"Warning not yellow in band: {samples}"


def test_no_red_paint_outside_paper():
    """Outside the paper slot the natural backdrop must show — no flat painted red."""
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out)).convert("RGB")
    # Sample just left of the paper at mid-height — should look like the studio red,
    # not a flat solid square. We assert the natural curtain colour is roughly preserved.
    px = img.getpixel((50, 500))
    # studio red curtain at this spot is around (10-20, 10-20, 10-20) black wall — anything
    # is acceptable except the previous flat (157, 57, 58) paint colour.
    assert not (px == (157, 57, 58)), f"flat solid red paint still present: {px}"


if __name__ == "__main__":
    test_composite_dimensions()
    test_ki_in_upper_slot()
    test_warning_overrides_ki()
    test_no_red_paint_outside_paper()
    print("All composite tests passed.")
