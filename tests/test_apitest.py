from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from pond.apitest import backfill_timestamps


def test_backfill_timestamps_match_frequency_with_bounded_jitter() -> None:
    random.seed(1234)
    now = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)

    timestamps = backfill_timestamps(hours=2, frequency=10, now=now)

    assert len(timestamps) == 20
    assert timestamps == sorted(timestamps)
    interval = timedelta(minutes=6)
    start = now - timedelta(hours=2)
    for index, timestamp in enumerate(timestamps):
        midpoint = start + (index + 0.5) * interval
        assert abs(timestamp - midpoint) <= 0.4 * interval