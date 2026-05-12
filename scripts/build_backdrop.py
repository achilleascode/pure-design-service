from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).parent.parent
SRC_BACKDROP = Path("/Users/achisumma/Downloads/KI_Packaging_Design_Sources/Backdrop/KI_Packaging_Design_Backdrop.png")
SRC_WARNING = Path("/Users/achisumma/Downloads/KI_Packaging_Design_Sources/Warning/PNG/Warning.png")
OUT = ROOT / "assets" / "backdrop_base.png"

WARNING_X, WARNING_Y = 234, 825
WARNING_W, WARNING_H = 612, 345


def main() -> None:
    bd = Image.open(SRC_BACKDROP).convert("RGBA")
    assert bd.size == (1080, 1350), f"unexpected backdrop size: {bd.size}"

    warning = Image.open(SRC_WARNING).convert("RGBA")
    warning_fit = ImageOps.fit(warning, (WARNING_W, WARNING_H), Image.LANCZOS, centering=(0.5, 0.5))

    bd.paste(warning_fit, (WARNING_X, WARNING_Y), warning_fit)
    bd.save(OUT, format="PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
