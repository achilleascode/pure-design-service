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
    BADGE_SIZE,
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


def test_composite_ki_slot_filled():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = SLOT_X + SLOT_W // 2
    cy = SLOT_Y + SLOT_H // 2
    px = img.getpixel((cx, cy))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"KI centre not red, got {px}"


def test_composite_warning_baked_in():
    out = composite(_synthetic_ki(color=(0, 0, 255, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # warning has dark borders + black text — sample multiple points and require >=1 yellow
    samples = [
        img.getpixel((SLOT_X + SLOT_W // 2, y))
        for y in (855, 870, 940, 980, 1040, 1080, 1140)
    ]
    yellow_hits = sum(1 for px in samples if px[0] > 200 and px[1] > 180 and px[2] < 100)
    assert yellow_hits >= 1, f"No yellow pixels found in warning band: {samples}"


def test_composite_badges_present():
    # badges have transparent backgrounds with black ink only — check the outer ring
    # of each badge contains dark pixels (not raw KI red).
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    badge_origins = [
        (SLOT_X + 15, SLOT_Y + 15),                              # Grammage top-left
        (SLOT_X + SLOT_W - 15 - BADGE_SIZE, SLOT_Y + 15),        # Food-Grade top-right
        (SLOT_X + 15, SLOT_Y + SLOT_H - 15 - BADGE_SIZE),        # CoA bottom-left
    ]
    for bx, by in badge_origins:
        # scan the top edge of the badge — outer black ring lives here
        dark = 0
        for x in range(bx + 5, bx + BADGE_SIZE - 5):
            px = img.getpixel((x, by + 4))
            if px[0] < 80 and px[1] < 80 and px[2] < 80:
                dark += 1
        assert dark > 0, f"No dark ring pixels at badge origin ({bx},{by})"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_ki_slot_filled()
    test_composite_warning_baked_in()
    test_composite_badges_present()
    print("All composite tests passed.")
