from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from pond import apitest
from pond.apitest import AuthSession, backfill_timestamps


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


def test_backfill_selects_a_test_user_for_each_entry(monkeypatch) -> None:
    sessions = [
        AuthSession(nickname="joe-test", auth_token="joe-token", show_nickname_on_charts=True),
        AuthSession(nickname="bob-test", auth_token="bob-token", show_nickname_on_charts=True),
        AuthSession(nickname="fred-test", auth_token="fred-token", show_nickname_on_charts=False),
    ]
    timestamps = [
        datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc) + timedelta(minutes=index)
        for index in range(30)
    ]
    submitted_payloads: list[dict[str, object]] = []

    monkeypatch.setattr(
        apitest,
        "parse_args",
        lambda: SimpleNamespace(
            seed=123,
            create_users=False,
            submit=False,
            backfill=1.0,
            freq=30.0,
            url="http://127.0.0.1:8000/api/pondupdate",
            timeout=10.0,
            anonymous=False,
            no_ensure_users=False,
            test_password="unused",
        ),
    )
    monkeypatch.setattr(apitest, "load_test_user_sessions", lambda **_kwargs: sessions)
    monkeypatch.setattr(apitest, "backfill_timestamps", lambda *_args, **_kwargs: timestamps)

    def capture_submit(_url: str, payload: dict[str, object], _timeout: float) -> tuple[int, str]:
        submitted_payloads.append(payload)
        return 200, "{}"

    monkeypatch.setattr(apitest, "submit_update", capture_submit)

    assert apitest.main() == 0
    selected_names = {
        payload["testMeta"]["testUserNickname"]
        for payload in submitted_payloads
        if isinstance(payload.get("testMeta"), dict)
    }
    assert len(submitted_payloads) == len(timestamps)
    assert selected_names == {"joe-test", "bob-test", "fred-test"}