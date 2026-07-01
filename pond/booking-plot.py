from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"
GLOB_PATTERN = "bookings-*.csv"


@dataclass(frozen=True)
class SlotKey:
	date: str
	time: str
	location: str
	duration: str

	@property
	def label(self) -> str:
		start_dt = parse_slot_start(self)
		return start_dt.strftime("%a %H:%M")


def parse_snapshot_time(path: Path) -> datetime:
	stamp = path.stem.removeprefix("bookings-")
	return datetime.strptime(stamp, "%Y-%m%d-%H%M")


def parse_slot_date(value: str) -> str:
	text = value.strip()
	if len(text) == 9 and text[4] == "-" and text[7:].isdigit() and text[:4].isdigit():
		return text
	raise ValueError(f"Unsupported slot date format: {value!r}")


def parse_slot_start(slot: SlotKey) -> datetime:
	return datetime.strptime(f"{slot.date} {slot.time.split('-', 1)[0]}", "%Y-%m%d %H:%M")


def date_offset(date_text: str, base_date_text: str) -> int:
	date_value = datetime.strptime(date_text, "%Y-%m%d").date()
	base_date_value = datetime.strptime(base_date_text, "%Y-%m%d").date()
	return (date_value - base_date_value).days


def parse_cli_date(value: str) -> str:
	"""Parse CLI date in yy-mm-dd format and convert to internal YYYY-MMDD."""
	try:
		return datetime.strptime(value, "%y-%m-%d").strftime("%Y-%m%d")
	except ValueError as exc:
		raise argparse.ArgumentTypeError(
			f"invalid date '{value}'. Use yy-mm-dd format, for example 26-07-01"
		) from exc


def read_snapshot_rows(path: Path) -> Iterable[dict[str, str]]:
	with path.open(newline="", encoding="utf-8") as handle:
		reader = csv.DictReader(handle)
		yield from reader


def parse_availability(value: str) -> int:
	text = value.strip()
	if text.isdigit():
		return int(text)
	raise ValueError(f"Unsupported availability format: {value!r}")


def load_snapshots(data_dir: Path) -> tuple[list[datetime], dict[SlotKey, list[tuple[datetime, int]]]]:
	snapshots = sorted(data_dir.glob(GLOB_PATTERN))
	if not snapshots:
		raise FileNotFoundError(f"No snapshot files matched {data_dir / GLOB_PATTERN}")

	snapshot_times: list[datetime] = []
	by_slot: dict[SlotKey, list[tuple[datetime, int]]] = defaultdict(list)
	skipped_files: list[tuple[Path, str]] = []

	for snapshot_path in snapshots:
		snapshot_time = parse_snapshot_time(snapshot_path)
		file_rows: list[tuple[SlotKey, int]] = []
		try:
			for row in read_snapshot_rows(snapshot_path):
				slot = SlotKey(
					date=parse_slot_date(row["date"]),
					time=row["time"].strip(),
					location=row["location"].strip(),
					duration=row["duration"].strip(),
				)
				availability = parse_availability((row.get("availability") or "0"))
				file_rows.append((slot, availability))
		except ValueError as exc:
			skipped_files.append((snapshot_path, str(exc)))
			continue

		snapshot_times.append(snapshot_time)
		for slot, availability in file_rows:
			by_slot[slot].append((snapshot_time, availability))

	if skipped_files:
		print(f"Skipped {len(skipped_files)} incompatible snapshot files")
		for path, reason in skipped_files[:10]:
			print(f"  {path.name}: {reason}")
		if len(skipped_files) > 10:
			print(f"  ... and {len(skipped_files) - 10} more")

	return snapshot_times, by_slot


def filter_slots(
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	venues: list[str] | None,
	days_ahead: int | None,
	date_offset_days: int = 0,
	start_date: str | None = None,
	dates: list[str] | None = None,
	max_slots_per_location: int | None = None,
	show_only_changing_slots: bool = False,
) -> dict[SlotKey, list[tuple[datetime, int]]]:
	base_date_text = min((slot.date for slot in by_slot), default=None)
	start_date_text = start_date or base_date_text
	if start_date is None and base_date_text is not None:
		base_date_value = datetime.strptime(base_date_text, "%Y-%m%d").date()
		start_date_value = base_date_value + timedelta(days=date_offset_days)
		start_date_text = start_date_value.strftime("%Y-%m%d")
	filtered: dict[SlotKey, list[tuple[datetime, int]]] = {}
	for slot, points in by_slot.items():
		if venues and slot.location not in venues:
			continue
		if dates and slot.date not in dates:
			continue
		if days_ahead is not None and start_date_text is not None:
			offset = date_offset(slot.date, start_date_text)
			if offset < 0 or offset >= days_ahead:
				continue
		if show_only_changing_slots and len({value for _, value in points}) <= 1:
			continue
		filtered[slot] = sorted(points)

	if max_slots_per_location is None:
		return filtered

	limited: dict[SlotKey, list[tuple[datetime, int]]] = {}
	slots_by_location: dict[str, list[SlotKey]] = defaultdict(list)
	for slot in filtered:
		slots_by_location[slot.location].append(slot)

	for location, slots in slots_by_location.items():
		ordered = sorted(slots, key=parse_slot_start)
		for slot in ordered[:max_slots_per_location]:
			limited[slot] = filtered[slot]
	return limited


def plot_slots(by_slot: dict[SlotKey, list[tuple[datetime, int]]], venues: list[str] | None) -> None:
	if not by_slot:
		raise ValueError("No slot series remain after filtering")

	locations = sorted({slot.location for slot in by_slot})
	fig, axes = plt.subplots(
		nrows=len(locations),
		ncols=1,
		figsize=(8, max(4, 3.6 * len(locations))),
		sharex=True,
		constrained_layout=True,
	)

	if len(locations) == 1:
		axes = [axes]

	for axis, location in zip(axes, locations):
		location_slots = sorted(
			(slot for slot in by_slot if slot.location == location),
			key=parse_slot_start,
		)
		location_max = 0
		for slot in location_slots:
			points = by_slot[slot]
			x_values = [snapshot_time for snapshot_time, _ in points]
			y_values = [availability for _, availability in points]
			location_max = max(location_max, max(y_values, default=0))
			line, = axis.plot(x_values, y_values, linewidth=1.5, label=slot.label)
			axis.annotate(
				slot.label,
				xy=(x_values[-1], y_values[-1]),
				xytext=(4, 0),
				textcoords="offset points",
				color=line.get_color(),
				fontsize=8,
				va="center",
			)

		axis.set_title(location)
		axis.set_ylabel("Availability")
		axis.set_ylim(0, max(10, int(math.ceil(location_max / 10.0) * 10)))
		axis.grid(True, alpha=0.3)
		axis.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)

	axes[-1].set_xlabel("Snapshot time")
	axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
	axes[-1].xaxis.set_minor_locator(mdates.MinuteLocator(interval=5))
	fig.suptitle("Booking availability by slot over snapshot time")

	venue = "all" if not venues else "-".join(venues).lower().replace("'", "").replace(" ", "-")
	output_path = OUTPUT_DIR / f"booking-plot-{venue}.png"
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	print(f"Saved plot: {output_path}")
	#plt.show()


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Plot booking availability through time from archived bookings CSV snapshots."
	)
	parser.add_argument(
		"--venue",
		action="append",
		dest="venues",
		default=None,
		help="Venue to include. Repeat to include multiple venues. Default: Men's.",
	)
	parser.add_argument(
		"--days",
		type=int,
		default=1,
		help="Number of days ahead to include, starting from the earliest slot date. Default: 1.",
	)
	parser.add_argument(
		"--date-offset",
		type=int,
		default=0,
		help="Start-date offset in days relative to the earliest slot date: 0=today, -1=yesterday, +1=tomorrow.",
	)
	parser.add_argument(
		"--date",
		type=parse_cli_date,
		default=None,
		help="Explicit start date in yy-mm-dd format (for example 26-07-01). Overrides --date-offset.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	venues = args.venues or ["Men's"]
	start_date = args.date
	snapshot_times, slot_series = load_snapshots(DATA_DIR)
	filtered_series = filter_slots(
		slot_series,
		venues=venues,
		days_ahead=args.days,
		date_offset_days=args.date_offset,
		start_date=start_date,
	)

	print(f"Loaded {len(snapshot_times)} snapshots from {snapshot_times[0]} to {snapshot_times[-1]}")
	print(f"Plotting {len(filtered_series)} slot series")
	plot_slots(filtered_series, venues=venues)


if __name__ == "__main__":
	main()
