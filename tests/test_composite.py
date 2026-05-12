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
    """Anywhere the pouch was originally pure cyan, the KI should now show through."""
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # Scan a vertical strip on the left side of the pouch — plenty of original cyan there.
    red_hits = 0
    for y in range(POUCH_Y + 200, POUCH_Y + 700, 30):
        for x in range(POUCH_X + 20, POUCH_X + 120, 30):
            px = img.getpixel((x, y))
            if px[0] > 200 and px[1] < 80 and px[2] < 80:
                red_hits += 1
    assert red_hits >= 10, f"KI red did not show through cyan replacement, hits={red_hits}"


def test_composite_warning_yellow():
    out = composite(_synthetic_ki(color=(0, 0, 255, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = POUCH_X + (WARN_BBOX[0] + WARN_BBOX[2]) // 2
    samples = [img.getpixel((cx, POUCH_Y + y)) for y in range(WARN_BBOX[1] + 10, WARN_BBOX[3] - 10, 20)]
    yellow_hits = sum(1 for px in samples if px[0] > 200 and px[1] > 180 and px[2] < 100)
    assert yellow_hits >= 2, f"Warning band not yellow: {samples}"


def test_three_badges_top_row():
    # all three badges should leave dark-ink pixels at roughly the same Y in the upper pouch area
    from lib.composite import POUCH_X, POUCH_W, BADGE_SIZE, BADGE_Y
    out = composite(_synthetic_ki(color=(255, 220, 0, 255)))  # bright yellow KI
    img = Image.open(BytesIO(out)).convert("RGB")
    # Sample the badge ring at y = BADGE_Y + 6 (top edge inside the ring) across the pouch width
    by = POUCH_Y + BADGE_Y + 6
    dark_runs = []
    in_dark = False
    start = 0
    for x in range(POUCH_X, POUCH_X + POUCH_W):
        px = img.getpixel((x, by))
        is_dark = px[0] < 80 and px[1] < 80 and px[2] < 80
        if is_dark and not in_dark:
            start = x; in_dark = True
        elif not is_dark and in_dark:
            dark_runs.append((start, x)); in_dark = False
    if in_dark:
        dark_runs.append((start, POUCH_X + POUCH_W))
    # Three separate badge ring intersections expected
    assert len(dark_runs) >= 3, f"expected 3+ badge rings at y={by}, found {dark_runs}"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_design_area_shows_ki()
    test_composite_warning_yellow()
    test_three_badges_top_row()
    print("All composite tests passed.")
