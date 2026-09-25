"""The Íris orb: an animated braille ring that reflects the agent's mode and activity."""

from __future__ import annotations

import math
from time import monotonic
from typing import TYPE_CHECKING

from rich.style import Style
from rich.text import Text

from textual.app import RenderResult
from textual.color import Color
from textual.widget import Widget

if TYPE_CHECKING:
    from toad.widgets.conversation import Conversation

TAU = math.tau

# Bit for the dot at (x, y) inside a 2x4 braille cell, indexed as DOT_BITS[y][x].
DOT_BITS = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))

DEFAULT_PLAN_COLOR = "#29c7ff"
DEFAULT_EXEC_COLOR = "#ff8a1f"
DEFAULT_PLAN_MODES = "plan, read-only"

WHITE = Color(255, 255, 255)


class IrisOrb(Widget):
    """Arc-reactor style ring.

    Color follows the agent's session mode (planning vs execution). The ring
    breathes slowly while idle and spins fast while the agent is working.
    """

    DEFAULT_CSS = """
    IrisOrb {
        width: 1fr;
        height: 11;
        background: transparent;
    }
    """

    FPS = 24
    LABEL_LINES = 2

    def __init__(
        self, name: str | None = None, id: str | None = None, classes: str | None = None
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._start = monotonic()
        self._last_frame = self._start
        # Integrated rotation angle, so speed changes don't make the ring jump.
        self._angle = 0.0
        self._color = Color.parse(DEFAULT_PLAN_COLOR)
        self._activity = 0.0
        """0 = idle, 1 = busy; eased so transitions are smooth."""

    def on_mount(self) -> None:
        self.set_interval(1 / self.FPS, self.refresh)

    def _setting(self, key: str, default: str) -> str:
        try:
            value = self.app.settings.get(key, str)
        except Exception:
            return default
        return value or default

    def _parse_color(self, key: str, default: str) -> Color:
        try:
            return Color.parse(self._setting(key, default))
        except Exception:
            return Color.parse(default)

    def _conversation(self) -> Conversation | None:
        from toad.widgets.conversation import Conversation

        return self.screen.query_one_optional(Conversation)

    def _read_state(self) -> tuple[bool, bool, bool, str]:
        """Returns (connected, busy, planning, mode name)."""
        conversation = self._conversation()
        if conversation is None:
            return False, False, True, ""
        mode = conversation.current_mode
        mode_name = mode.name if mode is not None else ""
        plan_words = [
            word.strip().lower()
            for word in self._setting("iris.plan_modes", DEFAULT_PLAN_MODES).split(",")
            if word.strip()
        ]
        mode_id = f"{mode.id} {mode.name}".lower() if mode is not None else ""
        planning = any(word in mode_id for word in plan_words)
        return (
            bool(conversation.agent_ready),
            conversation.busy_count > 0,
            planning,
            mode_name,
        )

    def render(self) -> RenderResult:
        now = monotonic()
        elapsed = now - self._start
        delta = min(now - self._last_frame, 0.25)
        self._last_frame = now

        connected, busy, planning, mode_name = self._read_state()

        target = (
            self._parse_color("iris.plan_color", DEFAULT_PLAN_COLOR)
            if planning
            else self._parse_color("iris.exec_color", DEFAULT_EXEC_COLOR)
        )
        ease = 1 - math.exp(-delta * 6)
        self._color = self._color.blend(target, ease)
        self._activity += ((1.0 if busy else 0.0) - self._activity) * ease

        speed = 0.35 + self._activity * 3.2
        if not connected:
            speed = 1.0
        self._angle = (self._angle + speed * delta) % TAU

        breath = 0.5 + 0.5 * math.sin(elapsed * 1.7)
        intensity = 0.62 + 0.38 * breath
        intensity += (1.0 - intensity) * self._activity
        if not connected:
            intensity = 0.35 + 0.15 * breath

        width = self.size.width
        rows = max(self.size.height - self.LABEL_LINES, 1)
        text = self._render_ring(width, rows, elapsed, intensity)
        text.append(self._render_label(width, connected, busy, planning, mode_name))
        return text

    def _render_ring(
        self, width: int, rows: int, elapsed: float, intensity: float
    ) -> Text:
        dots_w, dots_h = width * 2, rows * 4
        bits = [[0] * width for _ in range(rows)]
        glow = [[0.0] * width for _ in range(rows)]

        def plot(x: float, y: float, brightness: float) -> None:
            ix, iy = int(x), int(y)
            if 0 <= ix < dots_w and 0 <= iy < dots_h:
                cx, cy = ix // 2, iy // 4
                bits[cy][cx] |= DOT_BITS[iy % 4][ix % 2]
                if brightness > glow[cy][cx]:
                    glow[cy][cx] = brightness

        center_x, center_y = dots_w / 2, dots_h / 2
        radius = min(dots_w, dots_h) / 2 - 1
        head = self._angle

        # Outer ring with a bright comet sweeping around it.
        samples = int(TAU * radius * 2)
        for index in range(samples):
            theta = TAU * index / samples
            tail = (head - theta) % TAU
            brightness = 0.25 + 0.75 * max(0.0, 1 - tail / (TAU * 0.45))
            plot(
                center_x + radius * math.cos(theta),
                center_y + radius * math.sin(theta),
                brightness,
            )

        # Dashed inner ring, counter-rotating.
        inner = radius * 0.72
        samples = int(TAU * inner * 2)
        for index in range(samples):
            theta = TAU * index / samples
            if math.sin(6 * (theta + head * 0.6)) > 0.15:
                plot(
                    center_x + inner * math.cos(theta),
                    center_y + inner * math.sin(theta),
                    0.55,
                )

        # Pulsing core.
        core = radius * (0.24 + 0.04 * math.sin(elapsed * 3.4))
        core_int = int(core) + 1
        for dy in range(-core_int, core_int + 1):
            for dx in range(-core_int, core_int + 1):
                if dx * dx + dy * dy <= core * core:
                    plot(center_x + dx, center_y + dy, 1.0)

        background = self.background_colors[1]
        text = Text(no_wrap=True, overflow="crop")
        for y in range(rows):
            for x in range(width):
                cell_bits = bits[y][x]
                if not cell_bits:
                    text.append(" ")
                    continue
                level = glow[y][x] * intensity
                color = background.blend(self._color, min(level, 1.0))
                if level > 0.85:
                    color = color.blend(WHITE, min((level - 0.85) * 2, 0.5))
                text.append(chr(0x2800 + cell_bits), Style(color=color.rich_color))
            text.append("\n")
        return text

    def _render_label(
        self, width: int, connected: bool, busy: bool, planning: bool, mode_name: str
    ) -> Text:
        if not connected:
            phase, status = "conectando", "…"
        else:
            phase = "planejamento" if planning else "execução"
            status = "trabalhando…" if busy else "pronto"
        label = Text(no_wrap=True, overflow="crop")
        label.append(
            f"{phase.upper()} · {status}".center(width),
            Style(color=self._color.rich_color, bold=True),
        )
        label.append("\n")
        label.append((mode_name or " ").center(width), Style(dim=True))
        return label
