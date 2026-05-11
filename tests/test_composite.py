from io import BytesIO
from pathlib import Path
from PIL import Image

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from lib.composite import composite, TEMPLATE_W, TEMPLATE_H, KI_H, LOGO_Y, LOGO_H, WARNING_STRIP_Y, WARNING_STRIP_H


def _synthetic_ki(color=(50, 130, 200, 255)) -> bytes:
    img = Image.new("RGBA", (1024, 1536), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_composite_dimensions():
    out = composite(_synthetic_ki())
    img = Image.open(BytesIO(out))
    assert img.size == (TEMPLATE_W, TEMPLATE_H), f"Expected {TEMPLATE_W}x{TEMPLATE_H}, got {img.size}"


def test_composite_ki_fills_top_two_thirds():
    out = composite(_synthetic_ki(color=(255, 0, 0, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    px = img.getpixel((TEMPLATE_W // 2, KI_H // 2))
    assert px[0] > 200 and px[1] < 60 and px[2] < 60, f"KI top 2/3 not filled, got {px}"


def test_composite_warning_strip_is_third():
    out = composite(_synthetic_ki(color=(0, 0, 255, 255)))
    img = Image.open(BytesIO(out)).convert("RGB")
    # sample inside the yellow BG band, above where warning.png sits (top padding region)
    px = img.getpixel((10, WARNING_STRIP_Y + 5))
    assert px[0] > 200 and px[1] > 180 and px[2] < 100, f"Warning strip not yellow: {px}"


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




if __name__ == "__main__":
    test_composite_dimensions()
    test_composite_ki_fills_top_two_thirds()
    test_composite_warning_strip_is_third()
    test_composite_logo_watermark_visible()
    print("All composite tests passed.")
