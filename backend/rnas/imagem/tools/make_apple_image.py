from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "treinos" / "sample_images" / "maca.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (512, 512), (245, 245, 245))
    d = ImageDraw.Draw(img)

    # Apple body
    cx, cy, r = 256, 290, 140
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(220, 20, 60), outline=(120, 0, 20), width=6)

    # Highlight
    d.ellipse((cx - 80, cy - 90, cx + 20, cy + 10), fill=(255, 120, 160))

    # Stem
    d.polygon([(248, 150), (266, 150), (272, 210), (246, 210)], fill=(90, 60, 30))

    # Leaf
    d.ellipse((270, 130, 360, 210), fill=(30, 160, 60), outline=(10, 90, 30), width=4)
    d.line([(300, 210), (330, 150)], fill=(10, 90, 30), width=3)

    # Shadow
    d.ellipse((cx - 120, cy + 110, cx + 120, cy + 150), fill=(220, 220, 220))

    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
