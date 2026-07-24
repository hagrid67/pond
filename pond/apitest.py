#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


QUEUE_LABELS = ["don't know", "no queue", "5", "10", "20", "30", "50", "long!"]
GRASS_LABELS = ["don't know", "none", "5", "10", "20", "30", "50", "loads!"]


def slider_label(labels: list[str], index: int) -> str:
    if 0 <= index < len(labels):
        return labels[index]
    return labels[0]


def build_random_payload() -> dict[str, object]:
    slots_options = ["yes", "no", "dont-know"]
    now_iso = datetime.now(timezone.utc).isoformat()
    queue_index = random.randint(1, 7)
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
    }
    return payload


def submit_update(url: str, payload: dict[str, object], timeout: float) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            return resp.status, response_body
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        return exc.code, err_body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a random pond update payload.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:9000/api/pondupdate",
        help="POST endpoint URL (default: http://127.0.0.1:9000/api/pondupdate)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
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

    payload = build_random_payload()
    print(f"POST {args.url}")
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        status, response_body = submit_update(args.url, payload, args.timeout)
    except urllib.error.URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 2

    print(f"\nResponse status: {status}")
    print("Response body:")
    print(response_body)

    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
