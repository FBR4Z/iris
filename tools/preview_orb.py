"""Preview the orb's eye (Sharingan theme) in each state, without starting the app.

    uv run python tools/preview_orb.py [largura] [linhas]
    uv run --with pillow python tools/preview_orb.py 40 12 --png sharingan.png

Without --png it prints the braille text; with --png it draws the dots, in color,
side by side on a dark background.
"""

import sys

from rich.console import Console
from toad.widgets.iris_orb import IrisOrb, OrbState

STATES = (
    ("planejamento", OrbState(connected=True, planning=True), 0.0),
    ("execução", OrbState(connected=True, planning=False), 0.0),
    ("mangekyō", OrbState(connected=True, planning=False, elevated=True), 1.0),
)
BACKGROUND = (18, 18, 24)
DOT = 6
"""Pixels per braille dot."""


def render(state: OrbState, elevation: float, width: int, rows: int):
    orb = IrisOrb()
    orb._elapsed = 10.0
    orb._angle = 0.6
    orb._state = state
    orb._elevation = elevation
    # Settle the color on the state's target, as the running app would.
    for _ in range(60):
        orb._color = orb._color.blend(_target(state, elevation), 0.3)
    return orb._render_eye(width, rows)


def _target(state: OrbState, elevation: float):
    from textual.color import Color
    from toad.widgets import iris_orb

    if elevation > 0.5:
        return Color.parse(iris_orb.MANGEKYO_COLOR)
    if state.planning:
        return Color.parse(iris_orb.SHARINGAN_PLAN_COLOR)
    return Color.parse(iris_orb.SHARINGAN_EXEC_COLOR)


def save_png(path: str, width: int, rows: int) -> None:
    from PIL import Image, ImageDraw

    console = Console(color_system="truecolor")
    gap = 4 * DOT
    panel_w, panel_h = width * 2 * DOT, rows * 4 * DOT
    image = Image.new(
        "RGB", (len(STATES) * panel_w + (len(STATES) + 1) * gap, panel_h + 2 * gap), BACKGROUND
    )
    draw = ImageDraw.Draw(image)
    for panel, (_title, state, elevation) in enumerate(STATES):
        text = render(state, elevation, width, rows)
        left = gap + panel * (panel_w + gap)
        row = col = 0
        for offset, char in enumerate(text.plain):
            if char == "\n":
                row, col = row + 1, 0
                continue
            code = ord(char) - 0x2800
            if 0 < code < 256:
                style = text.get_style_at_offset(console, offset)
                color = style.color.get_truecolor() if style.color else (255, 255, 255)
                for dy, bits in enumerate(((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))):
                    for dx, bit in enumerate(bits):
                        if code & bit:
                            x = left + (col * 2 + dx) * DOT
                            y = gap + (row * 4 + dy) * DOT
                            draw.ellipse((x + 1, y + 1, x + DOT - 1, y + DOT - 1), fill=tuple(color))
            col += 1
    image.save(path)
    print(path)


def main() -> None:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    width = int(args[0]) if len(args) > 0 else 30
    rows = int(args[1]) if len(args) > 1 else 9
    if "--png" in sys.argv:
        save_png(sys.argv[sys.argv.index("--png") + 1], width, rows)
        return
    for title, state, elevation in STATES:
        print(f"--- {title} ---")
        print(render(state, elevation, width, rows).plain)


if __name__ == "__main__":
    main()
