"""Unit tests for the subscription usage shown under the orb."""

from datetime import datetime

from toad.iris_usage import (
    RateLimits,
    UsageWindow,
    crossed_levels,
    format_age,
    format_reset,
    load_rate_limits,
    parse_rate_limits,
    save_rate_limits,
    usage_segments,
)

# A Thursday, 10:00 local time.
NOW = datetime(2026, 9, 24, 10, 0).timestamp()
IN_4H = datetime(2026, 9, 24, 14, 0).timestamp()
SATURDAY = datetime(2026, 9, 26, 9, 0).timestamp()

# As sent by Claude Code in `usage_update._meta`.
META = {
    "_claude/rateLimit": {
        "status": "allowed",
        "resetsAt": IN_4H,
        "rateLimitType": "five_hour",
        "unifiedWindows": {
            "five_hour": {"utilization": 0.17, "resetsAt": IN_4H},
            "seven_day": {"utilization": 0.09, "resetsAt": SATURDAY},
        },
    },
    "_claude/model": "claude-opus-5-5",
}


def plain(segments):
    return "".join(text for text, _ in segments)


def test_parse_rate_limits():
    limits = parse_rate_limits(META)
    assert limits is not None and not limits.limited
    assert [(w.key, w.utilization, w.resets_at) for w in limits.windows] == [
        ("five_hour", 0.17, IN_4H),
        ("seven_day", 0.09, SATURDAY),
    ]


def test_parse_rate_limits_ignores_other_agents():
    assert parse_rate_limits(None) is None
    assert parse_rate_limits({"_claude/model": "x"}) is None
    assert parse_rate_limits({"_claude/rateLimit": {"status": "allowed"}}) is None
    assert parse_rate_limits({"_claude/rateLimit": {"unifiedWindows": {"five_hour": {"utilization": "x"}}}}) is None


def test_parse_rate_limits_rejected():
    limits = parse_rate_limits({"_claude/rateLimit": {"status": "rejected", "resetsAt": IN_4H}})
    assert limits is not None and limits.limited and limits.resets_at == IN_4H
    assert usage_segments(limits, NOW) == [("limite atingido", "danger"), (" ↻14:00", "danger")]


def test_format_reset():
    assert format_reset(IN_4H, NOW) == "14:00"
    assert format_reset(SATURDAY, NOW) == "sáb 09:00"
    assert format_reset(datetime(2026, 10, 20, 9, 0).timestamp(), NOW) == "20/10"
    assert format_reset(None, NOW) == ""


def test_usage_line():
    limits = parse_rate_limits(META)
    assert plain(usage_segments(limits, NOW)) == "5h 17% ↻14:00 · semana 9%"
    assert plain(usage_segments(limits, NOW, compact=True)) == "5h 17% · semana 9%"


def test_usage_levels_color_the_line():
    limits = RateLimits(
        (UsageWindow("five_hour", 0.92, IN_4H), UsageWindow("seven_day", 0.75, SATURDAY))
    )
    levels = dict(usage_segments(limits, NOW, compact=True))
    assert levels["5h 92%"] == "danger"
    assert levels["semana 75%"] == "warn"


def test_usage_resets_to_zero_after_the_window():
    limits = parse_rate_limits(META)
    after = IN_4H + 60
    assert plain(usage_segments(limits, after)) == "5h 0% · semana 9%"


def test_saved_limits_round_trip(tmp_path):
    path = tmp_path / "iris-usage.json"
    assert load_rate_limits(path) is None
    save_rate_limits(parse_rate_limits(META), path, now=NOW - 3 * 3600)
    limits = load_rate_limits(path)
    assert limits is not None and limits.saved_at == NOW - 3 * 3600
    assert [(w.key, w.utilization, w.resets_at) for w in limits.windows] == [
        ("five_hour", 0.17, IN_4H),
        ("seven_day", 0.09, SATURDAY),
    ]
    path.write_text("{lixo", encoding="utf-8")
    assert load_rate_limits(path) is None


def test_saved_limits_are_dim_with_their_age():
    limits = RateLimits(
        (UsageWindow("five_hour", 0.92, IN_4H), UsageWindow("seven_day", 0.09, SATURDAY)),
        saved_at=NOW - 3 * 3600,
    )
    segments = usage_segments(limits, NOW)
    assert plain(segments) == "5h 92% ↻14:00 · semana 9% (há 3h)"
    assert {level for _, level in segments} == {"dim"}


def test_format_age():
    assert format_age(5) == "há 1min"
    assert format_age(25 * 60) == "há 25min"
    assert format_age(3 * 3600 + 59 * 60) == "há 3h"
    assert format_age(2 * 86400) == "há 2d"


def test_crossed_levels_announce_once_per_reset():
    announced: set = set()
    low = RateLimits((UsageWindow("five_hour", 0.5, IN_4H),))
    assert crossed_levels(low, announced, NOW) == []

    high = RateLimits((UsageWindow("five_hour", 0.83, IN_4H),))
    assert [(w.key, value) for w, value in crossed_levels(high, announced, NOW)] == [("five_hour", 0.8)]
    assert crossed_levels(high, announced, NOW) == []
    wobble = RateLimits((UsageWindow("five_hour", 0.84, IN_4H + 3),))
    assert crossed_levels(wobble, announced, NOW) == []

    # Jumping straight past both levels says only the highest one.
    top = RateLimits((UsageWindow("five_hour", 0.97, IN_4H),))
    assert [value for _, value in crossed_levels(top, announced, NOW)] == [0.95]

    # A new window (new reset time) can be announced again.
    later = RateLimits((UsageWindow("five_hour", 0.97, IN_4H + 5 * 3600),))
    assert [value for _, value in crossed_levels(later, announced, NOW)] == [0.95]
