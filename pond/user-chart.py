#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
UPDATES_DIR = REPO_ROOT / "user-updates"
OUTPUT_PNG = REPO_ROOT / "www-root" / "user-updates.png"
OUTPUT_TEST_PNG = REPO_ROOT / "www-root" / "user-updates-test.png"
LONDON_TZ = ZoneInfo("Europe/London")

# Approximate count mappings for slider values from the UI.
QUEUE_GRASS_COUNT_MAP = {
    1: 0.0,
    2: 5.0,
    3: 10.0,
    4: 20.0,
    5: 30.0,
    6: 50.0,
    7: 70.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a chart of recent user updates with EWMA trend lines."
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="How many recent hours to include (default: 24).",
    )
    parser.add_argument(
        "--halflife-hours",
        type=float,
        default=10.0 / 60.0,
        help="EWMA half-life in hours (default: 0.1667, i.e. 10 minutes).",
    )
    parser.add_argument(
        "--input-dir",
        default=str(UPDATES_DIR),
        help="Directory containing user-updates-*.jsonl files.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PNG),
        help="Primary output PNG path for filtered (non-apitest) chart.",
    )
    parser.add_argument(
        "--output-test",
        default=str(OUTPUT_TEST_PNG),
        help="Output PNG path for full-data test chart.",
    )
    return parser.parse_args()


def parse_iso_ts(value: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def load_records(input_dir: Path, since_utc: datetime) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(input_dir.glob("user-updates-*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            received_at = row.get("receivedAt")
            if not isinstance(received_at, str):
                continue
            ts = parse_iso_ts(received_at)
            if ts is None or ts < since_utc:
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            records.append({"timestamp": ts, "payload": payload})
    records.sort(key=lambda r: r["timestamp"])
    return records


def slots_value(payload: dict[str, object]) -> float | None:
    raw = payload.get("slotsEnforced")
    if raw == "yes":
        return 1.0
    if raw == "no":
        return 0.0
    return None


def slider_count_value(payload: dict[str, object], key: str) -> float | None:
    raw = payload.get(key)
    if not isinstance(raw, dict):
        return None
    idx = raw.get("index")
    if isinstance(idx, float):
        idx = int(idx)
    if not isinstance(idx, int):
        return None
    return QUEUE_GRASS_COUNT_MAP.get(idx)


def ewma_time_series(
    points: list[tuple[datetime, float]], halflife_hours: float
) -> list[tuple[datetime, float]]:
    if not points:
        return []
    if halflife_hours <= 0:
        return points

    halflife_seconds = halflife_hours * 3600.0
    out: list[tuple[datetime, float]] = []
    last_t, last_ewma = points[0]
    out.append((last_t, last_ewma))

    for current_t, x in points[1:]:
        dt = max((current_t - last_t).total_seconds(), 0.0)
        alpha = 1.0 - math.exp(-math.log(2.0) * dt / halflife_seconds)
        last_ewma = alpha * x + (1.0 - alpha) * last_ewma
        last_t = current_t
        out.append((current_t, last_ewma))

    return out


def plot_metric(
    ax: plt.Axes,
    points: list[tuple[datetime, float]],
    ewma_points: list[tuple[datetime, float]],
    unknown_times: list[datetime],
    unknown_y: float,
    title: str,
    y_label: str,
    color: str,
    point_colors: list[str] | None = None,
) -> None:
    if points:
        ax.scatter(
            [p[0] for p in points],
            [p[1] for p in points],
            s=28,
            alpha=0.75,
            color=point_colors if point_colors else color,
            label="submissions",
            zorder=3,
        )
    if unknown_times:
        ax.scatter(
            unknown_times,
            [unknown_y] * len(unknown_times),
            s=52,
            alpha=0.5,
            marker="X",
            color="#5f6368",
            edgecolors="#f1f3f4",
            linewidths=0.8,
            label="unknown",
            zorder=5,
        )
    if ewma_points:
        ax.plot(
            [p[0] for p in ewma_points],
            [p[1] for p in ewma_points],
            linewidth=2.0,
            color=color,
            alpha=0.5,
            label="EWMA",
        )
    ax.set_title(title)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)


def is_apitest_payload(payload: dict[str, object]) -> bool:
    source = payload.get("source")
    if isinstance(source, str) and source in {"apitest.py", "api-test.py"}:
        return True

    note = payload.get("note")
    if isinstance(note, str):
        note_lower = note.lower()
        if "apitest sample" in note_lower or "api-test sample" in note_lower:
            return True

    return False


def build_chart(
    records: list[dict[str, object]],
    output_path: Path,
    hours: float,
    halflife_hours: float,
    title_prefix: str,
) -> tuple[int, int, int]:
    slots_points: list[tuple[datetime, float]] = []
    queue_points: list[tuple[datetime, float]] = []
    grass_points: list[tuple[datetime, float]] = []
    slots_unknown_times: list[datetime] = []
    queue_unknown_times: list[datetime] = []
    grass_unknown_times: list[datetime] = []

    for record in records:
        ts = record["timestamp"]
        payload = record["payload"]
        if not isinstance(ts, datetime) or not isinstance(payload, dict):
            continue

        v_slots = slots_value(payload)
        if v_slots is not None:
            slots_points.append((ts, v_slots))
        else:
            slots_unknown_times.append(ts)

        v_queue = slider_count_value(payload, "queue")
        if v_queue is not None:
            queue_points.append((ts, v_queue))
        else:
            queue_unknown_times.append(ts)

        v_grass = slider_count_value(payload, "grass")
        if v_grass is not None:
            grass_points.append((ts, v_grass))
        else:
            grass_unknown_times.append(ts)

    slots_ewma = ewma_time_series(slots_points, halflife_hours)
    queue_ewma = ewma_time_series(queue_points, halflife_hours)
    grass_ewma = ewma_time_series(grass_points, halflife_hours)

    # In the slots panel, highlight "yes" in red and keep "no" green.
    slots_point_colors = ["#e03131" if value >= 0.5 else "#2b8a3e" for _, value in slots_points]

    fig, axes = plt.subplots(3, 1, figsize=(6, 4), sharex=True)
    fig.suptitle(
        f"{title_prefix}: last {hours:g}h",
        fontsize=13,
    )

    plot_metric(
        axes[0],
        slots_points,
        slots_ewma,
        slots_unknown_times,
        0.5,
        title="Slots enforced",
        y_label="No/Yes",
        color="#2b8a3e",
        point_colors=slots_point_colors,
    )
    axes[0].set_yticks([0.0, 1.0], labels=["No", "Yes"])
    axes[0].set_ylim(-0.2, 1.2)

    plot_metric(
        axes[1],
        queue_points,
        queue_ewma,
        queue_unknown_times,
        36.5,
        title="Queue length",
        y_label="People",
        color="#1c7ed6",
    )
    axes[1].set_ylim(-2, 75)

    plot_metric(
        axes[2],
        grass_points,
        grass_ewma,
        grass_unknown_times,
        36.5,
        title="People on grass",
        y_label="People",
        color="#e67700",
    )
    axes[2].set_ylim(-2, 75)

    axes[2].set_xlabel("Time (Europe/London)")
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%a %H:%M", tz=LONDON_TZ))
    fig.autofmt_xdate()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path, dpi=160)
    plt.close(fig)

    return len(slots_points), len(queue_points), len(grass_points)


def main() -> int:
    args = parse_args()

    input_dir = Path(args.input_dir)
    output_path = Path(args.output)
    output_test_path = Path(args.output_test)

    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=args.hours)

    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    records = load_records(input_dir=input_dir, since_utc=since_utc)

    test_slots, test_queue, test_grass = build_chart(
        records=records,
        output_path=output_test_path,
        hours=args.hours,
        halflife_hours=args.halflife_hours,
        title_prefix="Pond user updates (all submissions)",
    )

    filtered_records = [
        record
        for record in records
        if isinstance(record.get("payload"), dict) and not is_apitest_payload(record["payload"])
    ]

    live_slots, live_queue, live_grass = build_chart(
        records=filtered_records,
        output_path=output_path,
        hours=args.hours,
        halflife_hours=args.halflife_hours,
        title_prefix="Pond user updates",
    )

    print(f"Wrote chart: {output_test_path}")
    print(
        f"All submissions: records={len(records)}, slots={test_slots}, queue={test_queue}, grass={test_grass}"
    )
    print(f"Wrote chart: {output_path}")
    print(
        f"Non-apitest submissions: records={len(filtered_records)}, slots={live_slots}, queue={live_queue}, grass={live_grass}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
