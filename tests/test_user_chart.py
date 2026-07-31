from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


user_chart = importlib.import_module("pond.user-chart")
LONDON_TZ = ZoneInfo("Europe/London")


def test_visible_window_spans_twelve_hours_excluding_overnight() -> None:
    end = datetime(2026, 7, 31, 14, 30, tzinfo=LONDON_TZ)

    start = user_chart.visible_window_start(end, 12)
    compressed_end = user_chart.compress_time_value(end, start)

    assert start.astimezone(LONDON_TZ) == datetime(2026, 7, 30, 16, 30, tzinfo=LONDON_TZ)
    assert compressed_end - start == timedelta(hours=12)