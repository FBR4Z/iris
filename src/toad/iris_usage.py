"""Subscription usage limits (Claude's 5-hour and weekly windows) for the Íris orb."""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any

WINDOWS = {"five_hour": "5h", "seven_day": "semana"}
"""ACP window key -> short label shown under the orb."""

SPOKEN_WINDOWS = {"five_hour": "de cinco horas", "seven_day": "semanal"}

WARN_LEVEL = 0.7
DANGER_LEVEL = 0.9
ANNOUNCE_LEVELS = (0.8, 0.95)
"""Íris says something (once per window reset) when usage crosses these levels."""
SAME_WINDOW_SECONDS = 600

WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


@dataclass(frozen=True)
class UsageWindow:
    key: str
    utilization: float
    """0..1"""
    resets_at: float | None
    """Unix timestamp."""

    @property
    def label(self) -> str:
        return WINDOWS.get(self.key, self.key)

    def current(self, now: float | None = None) -> float:
        """Utilization, or 0 once the window has reset since the agent last told us."""
        now = time() if now is None else now
        if self.resets_at is not None and now >= self.resets_at:
            return 0.0
        return self.utilization


@dataclass(frozen=True)
class RateLimits:
    windows: tuple[UsageWindow, ...]
    limited: bool = False
    """The agent refused to work until a window resets."""
    resets_at: float | None = None
    """When the binding window resets."""
    saved_at: float | None = None
    """Set when loaded from disk: when the agent last reported it (shown dimmed, with its age)."""

    def window(self, key: str) -> UsageWindow | None:
        return next((window for window in self.windows if window.key == key), None)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse_rate_limits(meta: Any) -> RateLimits | None:
    """Read `_meta["_claude/rateLimit"]` from an ACP `usage_update`."""
    if not isinstance(meta, dict):
        return None
    data = meta.get("_claude/rateLimit")
    if not isinstance(data, dict):
        return None
    windows: list[UsageWindow] = []
    unified = data.get("unifiedWindows")
    if isinstance(unified, dict):
        for key in WINDOWS:
            entry = unified.get(key)
            if not isinstance(entry, dict):
                continue
            utilization = _number(entry.get("utilization"))
            if utilization is None:
                continue
            windows.append(
                UsageWindow(
                    key, min(max(utilization, 0.0), 1.0), _number(entry.get("resetsAt"))
                )
            )
    status = data.get("status")
    limited = isinstance(status, str) and status not in ("allowed", "allowed_warning")
    if not windows and not limited:
        return None
    return RateLimits(tuple(windows), limited, _number(data.get("resetsAt")))


def save_rate_limits(limits: RateLimits, path: Path, now: float | None = None) -> None:
    """Remember the latest limits, so the next Íris starts with them (dimmed)."""
    data = {
        "saved_at": time() if now is None else now,
        "limited": limits.limited,
        "resets_at": limits.resets_at,
        "windows": [
            {"key": w.key, "utilization": w.utilization, "resets_at": w.resets_at}
            for w in limits.windows
        ],
    }
    with suppress(OSError):
        path.write_text(json.dumps(data), encoding="utf-8")


def load_rate_limits(path: Path) -> RateLimits | None:
    """Limits saved by a previous Íris, or None if missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        windows = tuple(
            UsageWindow(
                str(entry["key"]),
                min(max(float(entry["utilization"]), 0.0), 1.0),
                _number(entry.get("resets_at")),
            )
            for entry in data["windows"]
        )
        saved_at = _number(data["saved_at"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if saved_at is None or (not windows and not data.get("limited")):
        return None
    return RateLimits(windows, bool(data.get("limited")), _number(data.get("resets_at")), saved_at)


def format_age(seconds: float) -> str:
    """"há 5min", "há 3h", "há 2d"."""
    minutes = max(int(seconds // 60), 1)
    if minutes < 60:
        return f"há {minutes}min"
    if minutes < 24 * 60:
        return f"há {minutes // 60}h"
    return f"há {minutes // (24 * 60)}d"


def format_reset(resets_at: float | None, now: float | None = None) -> str:
    """Short local time for a reset: "14:00" today, "sáb 09:00" this week."""
    if resets_at is None:
        return ""
    now = time() if now is None else now
    moment = datetime.fromtimestamp(resets_at)
    today = datetime.fromtimestamp(now).date()
    if moment.date() == today:
        return moment.strftime("%H:%M")
    if (moment.date() - today).days < 7:
        return f"{WEEKDAYS[moment.weekday()]} {moment:%H:%M}"
    return moment.strftime("%d/%m")


def level(utilization: float) -> str:
    """"ok", "warn" or "danger" — picks the color under the orb."""
    if utilization >= DANGER_LEVEL:
        return "danger"
    if utilization >= WARN_LEVEL:
        return "warn"
    return "ok"


def usage_segments(
    limits: RateLimits, now: float | None = None, compact: bool = False
) -> list[tuple[str, str]]:
    """Pieces of the usage line as (text, level) pairs.

    e.g. [("5h 17%", "ok"), (" ↻14:00", "dim"), (" · ", "dim"), ("semana 9%", "ok")]

    Limits saved by a previous Íris are all "dim", followed by their age: usage on
    other devices since then isn't counted until the agent reports again.
    """
    now = time() if now is None else now
    segments = _live_segments(limits, now, compact)
    if limits.saved_at is None:
        return segments
    segments = [(text, "dim") for text, _ in segments]
    segments.append((f" ({format_age(now - limits.saved_at)})", "dim"))
    return segments


def _live_segments(limits: RateLimits, now: float, compact: bool) -> list[tuple[str, str]]:
    if limits.limited and (limits.resets_at is None or now < limits.resets_at):
        segments = [("limite atingido", "danger")]
        if reset := format_reset(limits.resets_at, now):
            segments.append((f" ↻{reset}", "danger"))
        return segments
    segments: list[tuple[str, str]] = []
    for window in limits.windows:
        utilization = window.current(now)
        if segments:
            segments.append((" · ", "dim"))
        segments.append((f"{window.label} {round(utilization * 100)}%", level(utilization)))
        # The reset time matters most for the short window; the weekly one is noise.
        if not compact and window.key == "five_hour" and utilization > 0:
            if reset := format_reset(window.resets_at, now):
                segments.append((f" ↻{reset}", "dim"))
    return segments


def crossed_levels(
    limits: RateLimits,
    announced: set[tuple[str, float, float | None]],
    now: float | None = None,
) -> list[tuple[UsageWindow, float]]:
    """Windows that crossed an announcement level not yet announced for this reset.

    Marks them in `announced`, so each level is spoken once per window.
    """

    def said(key: str, value: float, resets_at: float | None) -> bool:
        # Reset times can wobble slightly between updates; still the same window.
        return any(
            key == said_key
            and value == said_value
            and (
                resets_at == said_reset
                or (
                    resets_at is not None
                    and said_reset is not None
                    and abs(resets_at - said_reset) < SAME_WINDOW_SECONDS
                )
            )
            for said_key, said_value, said_reset in announced
        )

    crossed: list[tuple[UsageWindow, float]] = []
    for window in limits.windows:
        reached = [value for value in ANNOUNCE_LEVELS if window.current(now) >= value]
        if not reached:
            continue
        top = max(reached)
        if not said(window.key, top, window.resets_at):
            crossed.append((window, top))
        announced.update((window.key, value, window.resets_at) for value in reached)
    return crossed
