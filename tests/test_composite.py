from io import BytesIO
from pathlib import Path
from PIL import Image

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lib.composite import composite, TEMPLATE_W, TEMPLATE_H, SLOT_X, SLOT_Y, SLOT_W, SLOT_H, LOGO_Y, WARNING_Y, WARNING_H


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out))
    assert img.size == (TEMPLATE_W, TEMPLATE_H), f"Expected {TEMPLATE_W}x{TEMPLATE_H}, got {img.size}"


def test_composite_slot_filled_with_ki_color():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    cx = SLOT_X + SLOT_W // 2
    cy = SLOT_Y + SLOT_H // 2
    px = img.getpixel((cx, cy))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"Slot centre not red, got {px}"


def test_composite_logo_preserved():
    out = composite(_synthetic_ki(color=(0, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # Studio backdrop logo
    px = img.getpixel((TEMPLATE_W // 2, 50))
    assert max(px) > 100, f"Studio logo blacked out: {px}"
    # Hardcoded //pure wordmark on paper
    px2 = img.getpixel((TEMPLATE_W // 2, LOGO_Y + 40))
    # logo is dark brown on white → at least one channel should be much darker than pure white
    assert min(px2) < 200, f"Hardcoded pure logo not visible: {px2}"


def test_composite_warning_visible():
    out = composite(_synthetic_ki(color=(0, 100, 200, 255)))  # blue KI
    img = Image.open(BytesIO(out)).convert("RGB")
    # Warning is yellow (R>200, G>200, B<100) — sample inside warning rectangle
    px = img.getpixel((TEMPLATE_W // 2, WARNING_Y + WARNING_H // 2))
    is_yellow = px[0] > 180 and px[1] > 180 and px[2] < 150
    assert is_yellow, f"Warning yellow not visible at warning centre: {px}"


def test_composite_domain_preserved():
    out = composite(_synthetic_ki(color=(0, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    px = img.getpixel((TEMPLATE_W // 2, TEMPLATE_H - 50))
    assert max(px) > 80, f"Bottom domain area looks blacked out: {px}"


def test_composite_buds_preserved():
    out = composite(_synthetic_ki(color=(255, 0, 255, 255)))  # vivid magenta KI
    img = Image.open(BytesIO(out)).convert("RGB")
    # sample inside buds region (right-lower area)
    px = img.getpixel((850, 1100))
    r, g, b = px
    is_magenta = (r > 200 and b > 200 and g < 100)
    assert not is_magenta, f"Buds region was overwritten by KI magenta: {px}"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_slot_filled_with_ki_color()
    test_composite_logo_preserved()
    test_composite_domain_preserved()
    test_composite_buds_preserved()
    print("All composite tests passed.")
