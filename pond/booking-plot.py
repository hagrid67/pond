from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Iterable

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "www-root"
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


def parse_slot_end(slot: SlotKey) -> datetime:
	return datetime.strptime(f"{slot.date} {slot.time.split('-', 1)[1]}", "%Y-%m%d %H:%M")


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
	plot_days: int | None,
	anchor_date: str,
	include_prevday: bool = False,
	include_nextday: bool = False,
	date_offset_days: int = 0,
	start_date: str | None = None,
	dates: list[str] | None = None,
	max_slots_per_location: int | None = None,
	show_only_changing_slots: bool = False,
) -> dict[SlotKey, list[tuple[datetime, int]]]:
	start_date_text = start_date
	if start_date_text is None:
		anchor_date_value = datetime.strptime(anchor_date, "%Y-%m%d").date()
		start_date_value = anchor_date_value + timedelta(days=date_offset_days)
		start_date_text = start_date_value.strftime("%Y-%m%d")
	filtered: dict[SlotKey, list[tuple[datetime, int]]] = {}
	for slot, points in by_slot.items():
		if venues and slot.location not in venues:
			continue
		if dates and slot.date not in dates:
			continue
		if plot_days is not None and start_date_text is not None:
			offset = date_offset(slot.date, start_date_text)
			min_offset = -1 if include_prevday else 0
			max_offset = plot_days + 1 if include_nextday else plot_days
			if offset < min_offset or offset >= max_offset:
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


def filter_snapshots_by_start_time(
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	start_time: datetime,
) -> dict[SlotKey, list[tuple[datetime, int]]]:
	filtered: dict[SlotKey, list[tuple[datetime, int]]] = {}
	for slot, points in by_slot.items():
		trimmed = [(snapshot_time, value) for snapshot_time, value in points if snapshot_time >= start_time]
		if trimmed:
			filtered[slot] = trimmed
	return filtered


def filter_snapshots_per_slot_start(
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	days_back: float,
	latest_snapshot_time: datetime,
) -> dict[SlotKey, list[tuple[datetime, int]]]:
	window_days = abs(days_back)
	today_date = latest_snapshot_time.date()
	midnight_after_today = datetime.combine(today_date + timedelta(days=1), time(0, 0))
	day_end_by_date: dict[str, datetime] = {}
	for slot in by_slot:
		slot_date = datetime.strptime(slot.date, "%Y-%m%d").date()
		if slot_date > today_date:
			day_end = midnight_after_today
		else:
			day_end = parse_slot_end(slot)
		current = day_end_by_date.get(slot.date)
		if current is None or day_end > current:
			day_end_by_date[slot.date] = day_end

	filtered: dict[SlotKey, list[tuple[datetime, int]]] = {}
	for slot, points in by_slot.items():
		axis_end = day_end_by_date.get(slot.date)
		if axis_end is None:
			continue
		axis_start = axis_end - timedelta(days=window_days)
		trimmed = [
			(snapshot_time, value)
			for snapshot_time, value in points
			if axis_start <= snapshot_time <= axis_end
		]
		if trimmed:
			filtered[slot] = trimmed
	return filtered


def slot_signature(slot: SlotKey) -> tuple[str, str]:
	return (slot.time, slot.duration)


def night_seconds_between(start: datetime, end: datetime) -> float:
	"""Return seconds within [start, end) that fall in the hidden 00:00-06:00 window."""
	if end <= start:
		return 0.0
	total = 0.0
	day = start.date()
	end_day = end.date()
	while day <= end_day:
		window_start = datetime.combine(day, time(0, 0))
		window_end = datetime.combine(day, time(6, 0))
		overlap_start = max(start, window_start)
		overlap_end = min(end, window_end)
		if overlap_end > overlap_start:
			total += (overlap_end - overlap_start).total_seconds()
		day += timedelta(days=1)
	return total


def compress_time_value(value: datetime, origin: datetime) -> datetime:
	"""Map real datetime to compressed axis datetime with 00:00-06:00 removed."""
	real_seconds = (value - origin).total_seconds()
	hidden_seconds = night_seconds_between(origin, value)
	return origin + timedelta(seconds=real_seconds - hidden_seconds)


def expand_time_value(value: datetime, origin: datetime) -> datetime:
	"""Inverse of compress_time_value, used for x-axis tick labels."""
	target_seconds = (value - origin).total_seconds()
	if target_seconds <= 0:
		return origin

	low = origin
	day_guess = int(target_seconds // (18 * 3600)) + 3
	high = origin + timedelta(seconds=target_seconds + day_guess * 6 * 3600)

	for _ in range(40):
		mid = low + (high - low) / 2
		mid_seconds = (mid - origin).total_seconds() - night_seconds_between(origin, mid)
		if mid_seconds < target_seconds:
			low = mid
		else:
			high = mid

	return high


def ordinal_day(value: int) -> str:
	if 10 <= (value % 100) <= 20:
		suffix = "th"
	else:
		suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
	return f"{value}{suffix}"


def format_as_of_time(value: datetime) -> str:
	return f"{value.strftime('%a %b')} {ordinal_day(value.day)}, {value.strftime('%H:%M')}"


def plot_no_slots(venues: list[str] | None, latest_snapshot_time: datetime) -> None:
	fig, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
	venue_label = "All venues" if not venues else ", ".join(venues)
	axis.text(
		0.5,
		0.5,
		f"No slots available for {venue_label}",
		transform=axis.transAxes,
		ha="center",
		va="center",
		fontsize=16,
	)
	axis.set_axis_off()
	fig.suptitle(f"Booking availability (as of {format_as_of_time(latest_snapshot_time)})")

	venue = "all" if not venues else "-".join(venues).lower().replace("'", "").replace(" ", "-")
	output_path = OUTPUT_DIR / f"booking-plot-{venue}.png"
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	print(f"No slots available; saved empty plot: {output_path}")


def plot_slots(
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	venues: list[str] | None,
	focus_date: str,
	latest_snapshot_time: datetime,
	show_prevday: bool,
	show_nextday: bool,
	colour_day: bool,
	include_night: bool,
) -> None:
	if not by_slot:
		raise ValueError("No slot series remain after filtering")

	all_snapshot_times = [snapshot_time for points in by_slot.values() for snapshot_time, _ in points]
	time_origin = min(all_snapshot_times)

	def to_axis_time(snapshot_time: datetime) -> datetime:
		if include_night:
			return snapshot_time
		return compress_time_value(snapshot_time, time_origin)

	def compressed_break_positions() -> list[datetime]:
		if include_night:
			return []
		real_max = max(all_snapshot_times)
		breaks: list[datetime] = []
		day = time_origin.date()
		while day <= real_max.date():
			window_start = datetime.combine(day, time(0, 0))
			window_end = datetime.combine(day, time(6, 0))
			if window_end > time_origin and window_start < real_max:
				breaks.append(compress_time_value(window_start, time_origin))
			day += timedelta(days=1)
		return breaks

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
		if colour_day:
			dates_in_location = sorted({slot.date for slot in location_slots})
			palette = plt.get_cmap("tab10")
			color_by_date = {
				date_text: palette(index % 10)
				for index, date_text in enumerate(dates_in_location)
			}
		else:
			color_by_date = {}
		prev_date = (datetime.strptime(focus_date, "%Y-%m%d").date() - timedelta(days=1)).strftime("%Y-%m%d")
		next_date = (datetime.strptime(focus_date, "%Y-%m%d").date() + timedelta(days=1)).strftime("%Y-%m%d")
		location_today_slots = [slot for slot in location_slots if slot.date == focus_date]
		location_prev_slots = [slot for slot in location_slots if show_prevday and slot.date == prev_date]
		location_next_slots = [slot for slot in location_slots if show_nextday and slot.date == next_date]
		today_signatures = {slot_signature(slot) for slot in location_today_slots}
		remaining_slots = [
			slot
			for slot in location_slots
			if slot.date != focus_date
			and (not show_prevday or slot.date != prev_date)
			and (not show_nextday or slot.date != next_date)
		]
		location_max = 0
		color_by_signature: dict[tuple[str, str], str] = {}

		for slot in location_today_slots:
			points = by_slot[slot]
			x_values = [to_axis_time(snapshot_time) for snapshot_time, _ in points]
			y_values = [availability for _, availability in points]
			location_max = max(location_max, max(y_values, default=0))
			line_color = color_by_date.get(slot.date) if colour_day else None
			line, = axis.plot(x_values, y_values, linewidth=1.5, label=slot.label, color=line_color)
			color_by_signature[slot_signature(slot)] = line.get_color()
			axis.annotate(
				slot.label,
				xy=(x_values[-1], y_values[-1]),
				xytext=(4, 0),
				textcoords="offset points",
				color=line.get_color(),
				fontsize=8,
				va="center",
			)

		for slot in location_prev_slots:
			if slot_signature(slot) not in today_signatures:
				continue
			points = by_slot[slot]
			x_values = [to_axis_time(snapshot_time) for snapshot_time, _ in points]
			y_values = [availability for _, availability in points]
			location_max = max(location_max, max(y_values, default=0))
			line_color = (
				color_by_date.get(slot.date)
				if colour_day
				else color_by_signature.get(slot_signature(slot))
			)
			line, = axis.plot(
				x_values,
				y_values,
				linewidth=1.5,
				linestyle=":",
				color=line_color,
				label=slot.label,
			)
			axis.annotate(
				slot.label,
				xy=(x_values[-1], y_values[-1]),
				xytext=(4, 0),
				textcoords="offset points",
				color=line.get_color(),
				fontsize=8,
				va="center",
			)

		for slot in location_next_slots:
			if slot_signature(slot) not in today_signatures:
				continue
			points = by_slot[slot]
			x_values = [to_axis_time(snapshot_time) for snapshot_time, _ in points]
			y_values = [availability for _, availability in points]
			location_max = max(location_max, max(y_values, default=0))
			line_color = (
				color_by_date.get(slot.date)
				if colour_day
				else color_by_signature.get(slot_signature(slot))
			)
			line, = axis.plot(
				x_values,
				y_values,
				linewidth=1.5,
				linestyle="--",
				color=line_color,
				label=slot.label,
			)
			axis.annotate(
				slot.label,
				xy=(x_values[-1], y_values[-1]),
				xytext=(4, 0),
				textcoords="offset points",
				color=line.get_color(),
				fontsize=8,
				va="center",
			)

		for slot in remaining_slots:
			points = by_slot[slot]
			x_values = [to_axis_time(snapshot_time) for snapshot_time, _ in points]
			y_values = [availability for _, availability in points]
			location_max = max(location_max, max(y_values, default=0))
			line_color = color_by_date.get(slot.date) if colour_day else None
			line, = axis.plot(x_values, y_values, linewidth=1.5, label=slot.label, color=line_color)
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
		axis.legend(loc="center left", bbox_to_anchor=(1.12, 0.5), fontsize=8)

		for break_x in compressed_break_positions():
			axis.axvline(break_x, color="0.6", linestyle="--", linewidth=0.8, alpha=0.6)
			dx = timedelta(minutes=18)
			axis.plot(
				[break_x - dx, break_x - dx / 3],
				[-0.02, 0.02],
				transform=axis.get_xaxis_transform(),
				color="black",
				linewidth=1.1,
				clip_on=False,
			)
			axis.plot(
				[break_x + dx / 3, break_x + dx],
				[-0.02, 0.02],
				transform=axis.get_xaxis_transform(),
				color="black",
				linewidth=1.1,
				clip_on=False,
			)

	axes[-1].set_xlabel("Snapshot time")
	if include_night:
		axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
	else:
		def compressed_label(value: float, _pos: int) -> str:
			axis_dt = mdates.num2date(value).replace(tzinfo=None)
			real_dt = expand_time_value(axis_dt, time_origin)
			return real_dt.strftime("%m-%d\n%H:%M")

		axes[-1].xaxis.set_major_formatter(compressed_label)
	axes[-1].xaxis.set_minor_locator(mdates.MinuteLocator(interval=5))
	fig.suptitle(
		f"Booking availability by slot over time (as of {format_as_of_time(latest_snapshot_time)})"
	)

	venue = "all" if not venues else "-".join(venues).lower().replace("'", "").replace(" ", "-")
	output_path = OUTPUT_DIR / f"booking-plot-{venue}.png"
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	print(f"Saved plot: {output_path}")
	#plt.show()


def axis_end_for_slot_date(
	slot_date_text: str,
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	latest_snapshot_time: datetime,
) -> datetime:
	slot_date = datetime.strptime(slot_date_text, "%Y-%m%d").date()
	today_date = latest_snapshot_time.date()
	if slot_date > today_date:
		return datetime.combine(today_date + timedelta(days=1), time(0, 0))
	matching_slots = [slot for slot in by_slot if slot.date == slot_date_text]
	if not matching_slots:
		return datetime.combine(slot_date, time(21, 0))
	return max(parse_slot_end(slot) for slot in matching_slots)


def plot_slots_separate_axes(
	by_slot: dict[SlotKey, list[tuple[datetime, int]]],
	venues: list[str] | None,
	focus_date: str,
	latest_snapshot_time: datetime,
	show_prevday: bool,
	show_nextday: bool,
	per_slot_from_days: float | None,
	include_night: bool,
) -> None:
	if not by_slot:
		raise ValueError("No slot series remain after filtering")

	window_days = abs(per_slot_from_days if per_slot_from_days is not None else 1.0)
	plot_dates = sorted({slot.date for slot in by_slot})
	if not plot_dates:
		raise ValueError("No slot days available for separate-axes mode")

	locations = sorted({slot.location for slot in by_slot})
	all_signatures = sorted({slot_signature(slot) for slot in by_slot}, key=lambda item: item[0])
	palette = plt.get_cmap("tab10")
	color_by_signature = {
		signature: palette(index % 10)
		for index, signature in enumerate(all_signatures)
	}

	fig, axes = plt.subplots(
		nrows=len(locations),
		ncols=len(plot_dates),
		figsize=(3.8 * len(plot_dates), max(5.0, 4.4 * len(locations))),
		sharey=True,
		constrained_layout=True,
	)

	if len(locations) == 1 and len(plot_dates) == 1:
		axes_grid = [[axes]]
	elif len(locations) == 1:
		axes_grid = [list(axes)]
	elif len(plot_dates) == 1:
		axes_grid = [[row_axis] for row_axis in axes]
	else:
		axes_grid = axes

	legend_handles: dict[tuple[str, str], any] = {}
	global_max = 0
	for row_index, location in enumerate(locations):
		for col_index, slot_date_text in enumerate(plot_dates):
			axis = axes_grid[row_index][col_index]
			axis_end = axis_end_for_slot_date(slot_date_text, by_slot, latest_snapshot_time)
			axis_start = axis_end - timedelta(days=window_days)
			day_dt = datetime.strptime(slot_date_text, "%Y-%m%d")

			def to_axis_time(snapshot_time: datetime) -> datetime:
				if include_night:
					return snapshot_time
				return compress_time_value(snapshot_time, axis_start)

			def compressed_break_positions() -> list[datetime]:
				if include_night:
					return []
				breaks: list[datetime] = []
				day = axis_start.date()
				while day <= axis_end.date():
					window_start = datetime.combine(day, time(0, 0))
					window_end = datetime.combine(day, time(6, 0))
					if window_end > axis_start and window_start < axis_end:
						breaks.append(compress_time_value(window_start, axis_start))
					day += timedelta(days=1)
				return breaks

			axis_start_plot = axis_start if include_night else compress_time_value(axis_start, axis_start)
			axis_end_plot = axis_end if include_night else compress_time_value(axis_end, axis_start)
			location_day_slots = sorted(
				(
					slot
					for slot in by_slot
					if slot.location == location and slot.date == slot_date_text
				),
				key=parse_slot_start,
			)
			for slot in location_day_slots:
				points = by_slot[slot]
				x_values = [
					to_axis_time(snapshot_time)
					for snapshot_time, _ in points
					if axis_start <= snapshot_time <= axis_end
				]
				y_values = [value for snapshot_time, value in points if axis_start <= snapshot_time <= axis_end]
				if not x_values:
					continue
				global_max = max(global_max, max(y_values, default=0))
				signature = slot_signature(slot)
				line, = axis.plot(
					x_values,
					y_values,
					linewidth=1.5,
					linestyle="-",
					color=color_by_signature.get(signature),
				)
				axis.annotate(
					slot.label,
					xy=(x_values[-1], y_values[-1]),
					xytext=(4, 0),
					textcoords="offset points",
					color=line.get_color(),
					fontsize=8,
					va="center",
				)
				if signature not in legend_handles:
					legend_handles[signature] = line

			axis.set_xlim(axis_start_plot, axis_end_plot)
			axis.grid(True, alpha=0.3)
			if include_night:
				axis.xaxis.set_major_locator(mdates.HourLocator(interval=12))
				axis.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%H:%M"))
			else:
				tick_positions: list[datetime] = []
				tick_labels: list[str] = []
				day = axis_start.date()
				while day <= axis_end.date():
					midnight = datetime.combine(day, time(0, 0))
					midday = datetime.combine(day, time(12, 0))
					evening = datetime.combine(day, time(18, 0))
					if axis_start <= midnight <= axis_end:
						tick_position = compress_time_value(midnight, axis_start)
						if axis_start_plot <= tick_position <= axis_end_plot:
							tick_positions.append(tick_position)
							tick_labels.append(midnight.strftime("%a\n0-6h"))
					if axis_start <= midday <= axis_end:
						tick_position = compress_time_value(midday, axis_start)
						if axis_start_plot <= tick_position <= axis_end_plot:
							tick_positions.append(tick_position)
							tick_labels.append("12h")
					if axis_start <= evening <= axis_end:
						tick_position = compress_time_value(evening, axis_start)
						if axis_start_plot <= tick_position <= axis_end_plot:
							tick_positions.append(tick_position)
							tick_labels.append("18h")
					day += timedelta(days=1)
				if tick_positions:
					axis.set_xticks(tick_positions)
					axis.set_xticklabels(tick_labels)

			for break_x in compressed_break_positions():
				axis.axvline(break_x, color="0.6", linestyle="--", linewidth=0.8, alpha=0.6)
				dx = timedelta(minutes=18)
				axis.plot(
					[break_x - dx, break_x - dx / 3],
					[-0.02, 0.02],
					transform=axis.get_xaxis_transform(),
					color="black",
					linewidth=1.1,
					clip_on=False,
				)
				axis.plot(
					[break_x + dx / 3, break_x + dx],
					[-0.02, 0.02],
					transform=axis.get_xaxis_transform(),
					color="black",
					linewidth=1.1,
					clip_on=False,
				)
			axis.set_title(day_dt.strftime("%a %b %d"))
			if row_index == len(locations) - 1:
				axis.set_xlabel("Snapshot time")
			if col_index == 0:
				axis.set_ylabel(f"{location}\nAvailability")

	for row_index, _location in enumerate(locations):
		for col_index, _slot_date_text in enumerate(plot_dates):
			axis = axes_grid[row_index][col_index]
			axis.set_ylim(0, max(10, int(math.ceil(global_max / 10.0) * 10)))

	if legend_handles:
		ordered_signatures = sorted(legend_handles, key=lambda item: item[0])
		fig.legend(
			[legend_handles[signature] for signature in ordered_signatures],
			[f"{signature[0]}" for signature in ordered_signatures],
			loc="center left",
			bbox_to_anchor=(1.01, 0.5),
			ncol=1,
			fontsize=8,
			frameon=True,
		)

	fig.suptitle(
		f"Booking availability by slot-day panels (as of {format_as_of_time(latest_snapshot_time)})"
	)

	venue = "all" if not venues else "-".join(venues).lower().replace("'", "").replace(" ", "-")
	output_path = OUTPUT_DIR / f"booking-plot-{venue}.png"
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	print(f"Saved plot: {output_path}")


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
		"--plot-days",
		type=int,
		default=1,
		help="Number of slot dates to plot, starting from the anchor date (or --date). Default: 1.",
	)
	parser.add_argument(
		"--days",
		type=int,
		dest="plot_days",
		help=argparse.SUPPRESS,
	)
	parser.add_argument(
		"--date-offset",
		type=int,
		default=0,
		help="Start-date offset in days relative to latest snapshot date: 0=same day, -1=previous day, +1=next day.",
	)
	parser.add_argument(
		"--date",
		type=parse_cli_date,
		default=None,
		help="Explicit start date in yy-mm-dd format (for example 26-07-01). Overrides --date-offset.",
	)
	parser.add_argument(
		"--prevday",
		action="store_true",
		help="Also plot previous-day slots matching today's slot times using dotted lines in the same colors.",
	)
	parser.add_argument(
		"--nextday",
		action="store_true",
		help="Also plot next-day slots matching today's slot times using dashed lines in the same colors.",
	)
	parser.add_argument(
		"--colour-day",
		action="store_true",
		help="Use day-based colours: all slots for a day share one colour, and different days use different colours.",
	)
	parser.add_argument(
		"--separate-axes",
		action="store_true",
		help="Plot slot days on separate side-by-side axes sharing a common y-axis.",
	)
	parser.add_argument(
		"--from-offset",
		type=float,
		default=None,
		help=(
			"First snapshot time offset in days relative to latest snapshot time. "
			"For example -1 means last 24h, -1.5 means last 36h."
		),
	)
	parser.add_argument(
		"--per-slot-from",
		type=float,
		default=None,
		help=(
			"Days before each slot-day axis end to start plotting snapshots. "
			"For example 2 means plot the 2-day window ending at that day's axis end."
		),
	)
	parser.add_argument(
		"--include-night",
		action="store_true",
		help="Include 00:00-06:00 on the x-axis. Default behavior compresses that range out.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	venues = args.venues or ["Men's"]
	start_date = args.date
	snapshot_times, slot_series = load_snapshots(DATA_DIR)
	latest_snapshot_time = max(snapshot_times)
	anchor_date = latest_snapshot_time.strftime("%Y-%m%d")
	effective_start_date = start_date or (
		(datetime.strptime(anchor_date, "%Y-%m%d").date() + timedelta(days=args.date_offset)).strftime("%Y-%m%d")
	)
	filtered_series = filter_slots(
		slot_series,
		venues=venues,
		plot_days=args.plot_days,
		anchor_date=anchor_date,
		include_prevday=args.prevday,
		include_nextday=args.nextday,
		date_offset_days=args.date_offset,
		start_date=start_date,
	)
	first_snapshot_time = None
	if args.from_offset is not None:
		first_snapshot_time = latest_snapshot_time + timedelta(days=args.from_offset)
		filtered_series = filter_snapshots_by_start_time(filtered_series, first_snapshot_time)
	if args.per_slot_from is not None:
		filtered_series = filter_snapshots_per_slot_start(filtered_series, args.per_slot_from, latest_snapshot_time)
	plotted_dates = sorted({slot.date for slot in filtered_series})
	plotted_snapshot_times = [snapshot_time for points in filtered_series.values() for snapshot_time, _ in points]
	print(f"Venues requested: {', '.join(venues)}")
	print(f"Latest snapshot time: {latest_snapshot_time}")
	print(f"Anchor slot date: {effective_start_date}")
	print(f"Dates plotted: {', '.join(plotted_dates) if plotted_dates else 'none'}")
	print(f"Previous-day overlay: {'on' if args.prevday else 'off'}")
	print(f"Next-day overlay: {'on' if args.nextday else 'off'}")
	print(f"Day-based colours: {'on' if args.colour_day else 'off'}")
	print(f"Separate axes mode: {'on' if args.separate_axes else 'off'}")
	if first_snapshot_time is None:
		print("Snapshot start filter: off")
	else:
		print(
			f"Snapshot start filter: on ({args.from_offset:+g} days => {first_snapshot_time})"
		)
	if args.per_slot_from is None:
		print("Per-slot start filter: off")
	else:
		print(f"Per-slot start filter: on ({args.per_slot_from:+g} day window before each slot-day axis end)")
	print(f"Include night hours: {'on' if args.include_night else 'off (00:00-06:00 compressed)'}")

	print(f"Loaded {len(snapshot_times)} snapshots from {snapshot_times[0]} to {snapshot_times[-1]}")
	if plotted_snapshot_times:
		print(
			"Snapshot window plotted: "
			f"{min(plotted_snapshot_times)} to {max(plotted_snapshot_times)}"
		)
	print(f"Plotting {len(filtered_series)} slot series")
	if not filtered_series:
		plot_no_slots(venues, latest_snapshot_time)
		return
	if args.separate_axes:
		plot_slots_separate_axes(
			filtered_series,
			venues=venues,
			focus_date=effective_start_date,
			latest_snapshot_time=latest_snapshot_time,
			show_prevday=args.prevday,
			show_nextday=args.nextday,
			per_slot_from_days=args.per_slot_from,
			include_night=args.include_night,
		)
	else:
		plot_slots(
			filtered_series,
			venues=venues,
			focus_date=effective_start_date,
			latest_snapshot_time=latest_snapshot_time,
			show_prevday=args.prevday,
			show_nextday=args.nextday,
			colour_day=args.colour_day,
			include_night=args.include_night,
		)


if __name__ == "__main__":
	main()
