from io import BytesIO
from pathlib import Path
from PIL import Image

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lib.composite import composite, TEMPLATE_W, TEMPLATE_H, LOGO_Y, LOGO_H, WARNING_Y, WARNING_STRIP_H


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out))
    assert img.size == (TEMPLATE_W, TEMPLATE_H), f"Expected {TEMPLATE_W}x{TEMPLATE_H}, got {img.size}"


def test_composite_ki_fills_canvas():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # KI is full-bleed: top half of image should be saturated red
    px = img.getpixel((TEMPLATE_W // 2, TEMPLATE_H // 4))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"KI not full-bleed, got {px}"


def test_composite_logo_watermark_visible():
    out = composite(_synthetic_ki(color=(0, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # Logo is white on black canvas — scan the logo band for any bright pixel
    bright = 0
    for x in range(TEMPLATE_W // 4, 3 * TEMPLATE_W // 4):
        for y in range(LOGO_Y, LOGO_Y + LOGO_H):
            if max(img.getpixel((x, y))) > 180:
                bright += 1
                if bright > 50:
                    return
    assert False, f"Watermark logo not bright enough; bright={bright}"


def test_composite_warning_strip_yellow():
    out = composite(_synthetic_ki(color=(0, 100, 200, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    px = img.getpixel((TEMPLATE_W // 2, TEMPLATE_H - WARNING_STRIP_H // 2))
    assert px[0] > 200 and px[1] > 180 and px[2] < 100, f"Warning strip not yellow: {px}"


def test_composite_domain_under_warning():
    out = composite(_synthetic_ki(color=(255, 255, 255, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # Domain row should still show yellow strip BG with some dark pixels (text)
    found_dark = False
    for x in range(TEMPLATE_W // 4, 3 * TEMPLATE_W // 4):
        px = img.getpixel((x, TEMPLATE_H - 20))
        if max(px) < 120:
            found_dark = True
            break
    assert found_dark, "Domain text not visible in lower strip"


if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_ki_fills_canvas()
    test_composite_logo_watermark_visible()
    test_composite_warning_strip_yellow()
    test_composite_domain_under_warning()
    print("All composite tests passed.")
