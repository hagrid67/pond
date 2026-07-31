#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from urllib.parse import urlsplit
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


QUEUE_LABELS = ["don't know", "no queue", "5", "10", "20", "30", "50", "long!"]
GRASS_LABELS = ["don't know", "none", "5", "10", "20", "30", "50", "loads!"]
DEFAULT_TEST_PASSWORD = "pond-test-pass-123"
TEST_USERS = [
    ("joe-test", True),
    ("bob-test", True),
    ("fred-test", False),
]
LONDON_TZ = ZoneInfo("Europe/London")


@dataclass
class AuthSession:
    nickname: str
    auth_token: str
    show_nickname_on_charts: bool


def slider_label(labels: list[str], index: int) -> str:
    if 0 <= index < len(labels):
        return labels[index]
    return labels[0]


def build_random_payload(timestamp: datetime | None = None) -> dict[str, object]:
    slots_options = ["yes", "no", "dont-know"]
    now_iso = (timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    queue_index = random.choices(
        population=[0, 1, 2, 3, 4, 5, 6, 7],
        weights=[50, 25, 15, 5, 2, 1, 1, 1],
        k=1,
    )[0]
    grass_index = random.randint(1, 7)
    water_temp_index = random.randint(0, 29)

    payload = {
        "type": "pond-update",
        "submittedAt": now_iso,
        "submittedDate": now_iso[:10],
        "slotsEnforced": random.choice(slots_options),
        "queue": {
            "index": queue_index,
            "label": slider_label(QUEUE_LABELS, queue_index),
        },
        "grass": {
            "index": grass_index,
            "label": slider_label(GRASS_LABELS, grass_index),
        },
        "waterTemperature": {
            "index": water_temp_index,
            "label": "don't know" if water_temp_index == 0 else f"{water_temp_index - 1}",
            "celsius": None if water_temp_index == 0 else water_temp_index - 1,
        },
        "note": f"apitest sample at {now_iso}",
        "source": "apitest.py",
        "testMeta": {
            "isTestSubmission": True,
        },
    }
    return payload


def backfill_timestamps(hours: float, frequency: float, now: datetime | None = None) -> list[datetime]:
    if hours <= 0:
        raise ValueError("--backfill must be greater than zero")
    if frequency <= 0:
        raise ValueError("--freq must be greater than zero")

    end = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    count = max(1, round(hours * frequency))
    interval_seconds = hours * 3600.0 / count
    start = end - timedelta(hours=hours)
    timestamps: list[datetime] = []
    for index in range(count):
        midpoint_seconds = (index + 0.5) * interval_seconds
        jitter_seconds = random.uniform(-0.4, 0.4) * interval_seconds
        timestamps.append(start + timedelta(seconds=midpoint_seconds + jitter_seconds))
    return sorted(timestamps)


def backfill_end_timestamp(
    date_value: str | None,
    endtime_value: str | None,
    now: datetime | None = None,
) -> datetime:
    current_local = (now or datetime.now(timezone.utc)).astimezone(LONDON_TZ)
    target_date = current_local.date()
    target_time = current_local.time().replace(tzinfo=None)

    if date_value is not None:
        try:
            target_date = datetime.strptime(date_value, "%y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("--date must use yy-mm-dd format") from exc
    if endtime_value is not None:
        try:
            target_time = datetime.strptime(endtime_value, "%H:%M").time()
        except ValueError as exc:
            raise ValueError("--endtime must use hh:mm format") from exc

    return datetime.combine(target_date, target_time, tzinfo=LONDON_TZ).astimezone(timezone.utc)


def auth_base_from_submit_url(submit_url: str) -> str:
    parsed = urlsplit(submit_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid submit URL: {submit_url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def request_json(
    method: str,
    url: str,
    timeout: float,
    payload: dict[str, object] | None = None,
) -> tuple[int, str, dict[str, object] | None]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(
        url=url,
        data=body,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            try:
                response_json = json.loads(response_body)
            except json.JSONDecodeError:
                response_json = None
            return resp.status, response_body, response_json if isinstance(response_json, dict) else None
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
        except json.JSONDecodeError:
            err_json = None
        return exc.code, err_body, err_json if isinstance(err_json, dict) else None


def submit_update(url: str, payload: dict[str, object], timeout: float) -> tuple[int, str]:
    status, response_body, _ = request_json("POST", url, timeout, payload)
    return status, response_body


def register_test_user(api_base_url: str, nickname: str, password: str, show_nickname: bool, timeout: float) -> None:
    register_url = f"{api_base_url}/api/auth/register-nickname"
    login_url = f"{api_base_url}/api/auth/login"
    pref_url = f"{api_base_url}/api/auth/preferences"

    register_payload: dict[str, object] = {
        "nickname": nickname,
        "password": password,
        "isTestUser": True,
    }
    register_status, register_body, _ = request_json("POST", register_url, timeout, register_payload)
    if register_status not in {200, 409}:
        raise RuntimeError(f"register-nickname failed for {nickname}: {register_status} {register_body}")

    login_payload: dict[str, object] = {
        "username": nickname,
        "password": password,
    }
    login_status, login_body, login_data = request_json("POST", login_url, timeout, login_payload)
    if login_status != 200 or login_data is None:
        raise RuntimeError(f"login failed for {nickname}: {login_status} {login_body}")

    auth_token = login_data.get("authToken")
    if not isinstance(auth_token, str) or not auth_token:
        raise RuntimeError(f"login did not return auth token for {nickname}")

    pref_payload: dict[str, object] = {
        "authToken": auth_token,
        "showNicknameOnCharts": show_nickname,
    }
    pref_status, pref_body, _ = request_json("POST", pref_url, timeout, pref_payload)
    if pref_status != 200:
        raise RuntimeError(f"preference update failed for {nickname}: {pref_status} {pref_body}")


def create_test_users(api_base_url: str, timeout: float, password: str) -> None:
    for nickname, show_nickname in TEST_USERS:
        register_test_user(
            api_base_url=api_base_url,
            nickname=nickname,
            password=password,
            show_nickname=show_nickname,
            timeout=timeout,
        )


def login_test_user(api_base_url: str, nickname: str, password: str, timeout: float) -> AuthSession | None:
    login_url = f"{api_base_url}/api/auth/login"
    login_payload: dict[str, object] = {
        "username": nickname,
        "password": password,
    }
    login_status, _, login_data = request_json("POST", login_url, timeout, login_payload)
    if login_status != 200 or login_data is None:
        return None

    auth_token = login_data.get("authToken")
    if not isinstance(auth_token, str) or not auth_token:
        return None

    user_data = login_data.get("user")
    show_nickname = False
    if isinstance(user_data, dict):
        show_raw = user_data.get("showNicknameOnCharts")
        show_nickname = bool(show_raw)

    return AuthSession(
        nickname=nickname,
        auth_token=auth_token,
        show_nickname_on_charts=show_nickname,
    )


def load_test_user_sessions(
    api_base_url: str,
    timeout: float,
    password: str,
    ensure_users: bool,
) -> list[AuthSession]:
    sessions: list[AuthSession] = []
    for nickname, _ in TEST_USERS:
        session = login_test_user(api_base_url, nickname, password, timeout)
        if session is not None:
            sessions.append(session)

    if not sessions and ensure_users:
        create_test_users(api_base_url=api_base_url, timeout=timeout, password=password)
        for nickname, _ in TEST_USERS:
            session = login_test_user(api_base_url, nickname, password, timeout)
            if session is not None:
                sessions.append(session)

    if not sessions:
        raise RuntimeError("No test users could be logged in. Run with --create-users first.")

    return sessions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create apitest users and/or submit a random pond update payload.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/pondupdate",
        help="POST endpoint URL (default: http://127.0.0.1:8000/api/pondupdate)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--create-users",
        action="store_true",
        help="Create the fixed apitest users via the dev-web-api and set chart nickname preferences.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit a test pond update payload (current behavior).",
    )
    parser.add_argument(
        "--backfill",
        type=float,
        metavar="HOURS",
        help="Submit historical test entries covering the previous HOURS.",
    )
    parser.add_argument(
        "--freq",
        type=float,
        default=4.0,
        metavar="PER_HOUR",
        help="Average backfill entries per hour, with jitter (default: 4).",
    )
    parser.add_argument(
        "--date",
        metavar="YY-MM-DD",
        help="London date containing the end of the backfill period (default: today).",
    )
    parser.add_argument(
        "--endtime",
        metavar="HH:MM",
        help="London time at the end of the backfill period (default: current time).",
    )
    parser.add_argument(
        "--anonymous",
        action="store_true",
        help="For --submit, send the payload as an anonymous test submission.",
    )
    parser.add_argument(
        "--no-ensure-users",
        action="store_true",
        help="For --submit, do not auto-create test users if none are available.",
    )
    parser.add_argument(
        "--test-password",
        default=DEFAULT_TEST_PASSWORD,
        help=f"Password for fixed test users (default: {DEFAULT_TEST_PASSWORD}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible payloads.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    do_create_users = bool(args.create_users)
    do_submit = bool(args.submit or args.backfill is not None)
    if args.backfill is None and (args.date is not None or args.endtime is not None):
        print("--date and --endtime require --backfill", file=sys.stderr)
        return 2
    if not do_create_users and not do_submit:
        # Backward compatible default: submit one sample.
        do_submit = True

    try:
        api_base_url = auth_base_from_submit_url(args.url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if do_create_users:
        try:
            create_test_users(api_base_url=api_base_url, timeout=args.timeout, password=args.test_password)
        except (RuntimeError, urllib.error.URLError) as exc:
            print(f"Failed to create test users: {exc}", file=sys.stderr)
            return 2
        print("Created/updated test users: joe-test (show), bob-test (show), fred-test (hidden)")

    if not do_submit:
        return 0

    test_user_sessions: list[AuthSession] = []
    if args.anonymous:
        if args.backfill is not None:
            print("--backfill requires authenticated test users; remove --anonymous", file=sys.stderr)
            return 2
    else:
        try:
            test_user_sessions = load_test_user_sessions(
                api_base_url=api_base_url,
                timeout=args.timeout,
                password=args.test_password,
                ensure_users=not args.no_ensure_users,
            )
        except (RuntimeError, urllib.error.URLError) as exc:
            print(f"Failed to select test user for submission: {exc}", file=sys.stderr)
            return 2
    try:
        backfill_end = backfill_end_timestamp(args.date, args.endtime)
        if args.backfill is not None and backfill_end > datetime.now(timezone.utc):
            raise ValueError("backfill end must not be in the future")
        timestamps = (
            backfill_timestamps(args.backfill, args.freq, now=backfill_end)
            if args.backfill is not None
            else [datetime.now(timezone.utc)]
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    failures = 0
    for timestamp in timestamps:
        payload = build_random_payload(timestamp)
        selected_user = random.choice(test_user_sessions) if test_user_sessions else None
        if selected_user is not None:
            payload["authToken"] = selected_user.auth_token
            payload["testMeta"] = {
                "isTestSubmission": True,
                "isAnonymousTest": False,
                "submissionAuthMode": "authenticated",
                "testUserNickname": selected_user.nickname,
            }
            if args.backfill is not None:
                cast_meta = payload["testMeta"]
                if isinstance(cast_meta, dict):
                    cast_meta["historicalTimestamp"] = timestamp.isoformat()
        else:
            payload["testMeta"] = {
                "isTestSubmission": True,
                "isAnonymousTest": True,
                "submissionAuthMode": "anonymous",
            }

        if len(timestamps) == 1:
            print(f"POST {args.url}")
            print("Payload:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            if selected_user is not None:
                print(
                    f"Submitting as test user: {selected_user.nickname} "
                    f"(showNicknameOnCharts={selected_user.show_nickname_on_charts})"
                )
            elif args.anonymous:
                print("Submitting as anonymous test submission")

        try:
            status, response_body = submit_update(args.url, payload, args.timeout)
        except urllib.error.URLError as exc:
            print(f"Request failed for {timestamp.isoformat()}: {exc}", file=sys.stderr)
            failures += 1
            continue

        if len(timestamps) == 1:
            print(f"\nResponse status: {status}")
            print("Response body:")
            print(response_body)
        elif not 200 <= status < 300:
            print(f"Backfill failed for {timestamp.isoformat()}: {status} {response_body}", file=sys.stderr)
        if not 200 <= status < 300:
            failures += 1

    if args.backfill is not None:
        print(f"Backfill submitted: {len(timestamps) - failures}/{len(timestamps)} entries over {args.backfill:g}h")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
