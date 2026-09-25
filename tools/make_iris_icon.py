"""Draws the Íris icon (used by desktop notifications) in the style of the orb.

    uv run --with pillow python tools/make_iris_icon.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 256
SCALE = 4  # supersample for smooth edges
CYAN = (41, 199, 255)
ORANGE = (255, 138, 31)
NAVY = (7, 13, 23)
OUT = Path(__file__).resolve().parents[1] / "src" / "toad" / "data" / "images" / "iris.png"


def ring(draw, center, radius, width, color):
    x, y = center
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius), outline=color, width=width
    )


def main() -> None:
    size = SIZE * SCALE
    center = (size / 2, size / 2)
    unit = size / 256

    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    # Dark disc so the icon reads on light and dark notification backgrounds.
    draw.ellipse((4 * unit, 4 * unit, size - 4 * unit, size - 4 * unit), fill=NAVY + (255,))

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    ring(glow_draw, center, 100 * unit, int(14 * unit), CYAN + (200,))
    glow_draw.ellipse(
        (center[0] - 34 * unit, center[1] - 34 * unit, center[0] + 34 * unit, center[1] + 34 * unit),
        fill=CYAN + (220,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(14 * unit))
    base = Image.alpha_composite(base, glow)
    draw = ImageDraw.Draw(base)

    # Outer ring, with a brighter "comet" arc.
    ring(draw, center, 100 * unit, int(7 * unit), CYAN + (140,))
    box = (center[0] - 100 * unit, center[1] - 100 * unit, center[0] + 100 * unit, center[1] + 100 * unit)
    draw.arc(box, start=-90, end=40, fill=(190, 240, 255, 255), width=int(9 * unit))

    # Dashed inner ring in the execution color.
    inner = 70 * unit
    for index in range(12):
        start = index * 30 + 5
        draw.arc(
            (center[0] - inner, center[1] - inner, center[0] + inner, center[1] + inner),
            start=start,
            end=start + 18,
            fill=ORANGE + (230,),
            width=int(6 * unit),
        )

    # Bright core.
    core = 30 * unit
    draw.ellipse(
        (center[0] - core, center[1] - core, center[0] + core, center[1] + core),
        fill=(210, 245, 255, 255),
    )
    highlight = 12 * unit
    offset = -8 * unit
    draw.ellipse(
        (
            center[0] + offset - highlight,
            center[1] + offset - highlight,
            center[0] + offset + highlight,
            center[1] + offset + highlight,
        ),
        fill=(255, 255, 255, 255),
    )

    icon = base.resize((SIZE, SIZE), Image.LANCZOS)
    icon.save(OUT)
    print(f"salvo em {OUT}")


if __name__ == "__main__":
    main()
