from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, Colormap, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

from pond.booking_slots import logical_slot


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUTPUT_PATH = REPO_ROOT / "www-root" / "season-plot.png"
ARCHIVE_GLOB = "bookings-*.csv"
POND_CAPACITY = 120
SOLD_OUT_THRESHOLD = 5
SOLD_OUT_POINTS_PER_DAY = 10
MAX_SOLD_OUT_DAYS = 7
VENUES = ("Men's", "Ladies", "Mixed")
VENUE_CAPACITIES = {**dict.fromkeys(VENUES, POND_CAPACITY), "Lido": 650}
POND_SLOT_IDS = tuple(f"P{index}" for index in range(1, 8))

SlotHistory = dict[tuple[str, str, str], list[tuple[datetime, int, str]]]


def parse_snapshot_time(path: Path) -> datetime:
	return datetime.strptime(path.stem.removeprefix("bookings-"), "%Y-%m%d-%H%M")


def parse_slot_start(date_text: str, time_text: str) -> datetime:
	return datetime.strptime(f"{date_text} {time_text.split('-', 1)[0]}", "%Y-%m%d %H:%M")


def demand_score(
	points: list[tuple[datetime, int]],
	slot_start: datetime,
	capacity: int = POND_CAPACITY,
) -> float | None:
	observed = sorted((snapshot_time, count) for snapshot_time, count in points if snapshot_time <= slot_start)
	if not observed:
		return None

	availability_at_start = observed[-1][1]
	if availability_at_start >= SOLD_OUT_THRESHOLD:
		return float(max(0, min(capacity, capacity - availability_at_start)))

	first_sold_out = next(
		snapshot_time
		for snapshot_time, count in observed
		if count < SOLD_OUT_THRESHOLD
	)
	lead_hours = max((slot_start - first_sold_out).total_seconds() / 3600, 0)
	lead_points = min(
		lead_hours / (24 / SOLD_OUT_POINTS_PER_DAY),
		MAX_SOLD_OUT_DAYS * SOLD_OUT_POINTS_PER_DAY,
	)
	return capacity + lead_points


def load_slot_history(data_dir: Path) -> tuple[datetime, SlotHistory]:
	archives = sorted(data_dir.glob(ARCHIVE_GLOB), key=parse_snapshot_time)
	if not archives:
		raise FileNotFoundError(f"No booking snapshots matched {data_dir / ARCHIVE_GLOB}")

	history: SlotHistory = defaultdict(list)
	for archive in archives:
		snapshot_time = parse_snapshot_time(archive)
		with archive.open(newline="", encoding="utf-8") as handle:
			for row in csv.DictReader(handle):
				location = (row.get("location") or "").strip()
				time_text = (row.get("time") or "").strip()
				mapped = logical_slot(location, time_text)
				if location not in VENUE_CAPACITIES or mapped is None:
					continue
				availability_text = (row.get("availability") or "").strip()
				if not availability_text.isdigit():
					continue
				key = ((row.get("date") or "").strip(), location, mapped.id)
				history[key].append((snapshot_time, int(availability_text), time_text))

	return parse_snapshot_time(archives[-1]), history


def build_heatmap(
	history: SlotHistory,
	as_of: datetime,
) -> tuple[list[datetime], list[str], np.ndarray]:
	started_keys = [
		key for key, points in history.items()
		if key[1] in VENUES and parse_slot_start(key[0], _latest_time(points)) <= as_of
	]
	if not started_keys:
		raise ValueError("No completed or started pond slots are available")

	first_date = min(datetime.strptime(key[0], "%Y-%m%d") for key in started_keys)
	last_date = max(datetime.strptime(key[0], "%Y-%m%d") for key in started_keys)
	date_count = (last_date.date() - first_date.date()).days + 1
	dates = [first_date + timedelta(days=offset) for offset in range(date_count)]
	date_indexes = {value.strftime("%Y-%m%d"): index for index, value in enumerate(dates)}
	row_labels = [f"{venue} {slot_id}" for venue in VENUES for slot_id in POND_SLOT_IDS]
	row_indexes = {
		(venue, slot_id): index
		for index, (venue, slot_id) in enumerate(
			(venue, slot_id) for venue in VENUES for slot_id in POND_SLOT_IDS
		)
	}
	matrix = np.full((len(row_labels), len(dates)), np.nan)

	for (date_text, venue, slot_id), points in history.items():
		if venue not in VENUES:
			continue
		time_text = _latest_time(points)
		slot_start = parse_slot_start(date_text, time_text)
		if slot_start > as_of:
			continue
		score = demand_score(
			[(snapshot_time, availability) for snapshot_time, availability, _time_text in points],
			slot_start,
		)
		if score is not None:
			matrix[row_indexes[(venue, slot_id)], date_indexes[date_text]] = score

	return dates, row_labels, matrix


def build_occupancy(
	history: SlotHistory,
	as_of: datetime,
) -> tuple[list[datetime], list[datetime], dict[str, tuple[list[float], list[float]]]]:
	daily_totals: dict[tuple[datetime, str], list[int]] = defaultdict(lambda: [0, 0])
	incomplete_days: set[tuple[datetime, str]] = set()
	for (date_text, venue, _slot_id), points in history.items():
		day = datetime.strptime(date_text, "%Y-%m%d")
		if venue not in VENUE_CAPACITIES or day + timedelta(days=1) > as_of:
			continue
		slot_start = parse_slot_start(date_text, _latest_time(points))
		observed = [(snapshot, available) for snapshot, available, _time in points if snapshot <= slot_start]
		if not observed:
			incomplete_days.add((day, venue))
			continue
		availability = max(observed, key=lambda point: point[0])[1]
		capacity = VENUE_CAPACITIES[venue]
		totals = daily_totals[(day, venue)]
		totals[0] += max(0, min(capacity, capacity - availability))
		totals[1] += capacity
	for key in incomplete_days:
		daily_totals.pop(key, None)
	if not daily_totals:
		raise ValueError("No completed days with pre-start booking observations are available")

	first_day = min(day for day, _venue in daily_totals)
	last_day = max(day for day, _venue in daily_totals)
	dates = [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]
	first_week = first_day - timedelta(days=first_day.weekday())
	last_week = last_day - timedelta(days=last_day.weekday())
	weeks = [first_week + timedelta(weeks=offset) for offset in range((last_week - first_week).days // 7 + 1)]
	weekly_totals: dict[tuple[datetime, str], list[int]] = defaultdict(lambda: [0, 0])
	for (day, venue), (sold, capacity) in daily_totals.items():
		week = day - timedelta(days=day.weekday())
		totals = weekly_totals[(week, venue)]
		totals[0] += sold
		totals[1] += capacity

	percentages = {}
	for venue in VENUE_CAPACITIES:
		daily = [
			100 * daily_totals[(day, venue)][0] / daily_totals[(day, venue)][1]
			if (day, venue) in daily_totals else float("nan")
			for day in dates
		]
		weekly = [
			100 * weekly_totals[(week, venue)][0] / weekly_totals[(week, venue)][1]
			if (week, venue) in weekly_totals else float("nan")
			for week in weeks
		]
		percentages[venue] = (daily, weekly)
	return dates, weeks, percentages


def infer_closure_periods(
	dates: list[datetime],
	history: SlotHistory,
	percentages: dict[str, tuple[list[float], list[float]]],
) -> dict[str, list[tuple[datetime, datetime]]]:
	observed_days = {(date_text, venue) for date_text, venue, _slot_id in history}
	closures: dict[str, list[tuple[datetime, datetime]]] = {}
	for venue, (daily, _weekly) in percentages.items():
		periods = []
		start = None
		for index, day in enumerate(dates):
			missing = (
				not np.isfinite(daily[index])
				and (day.strftime("%Y-%m%d"), venue) not in observed_days
				and any(np.isfinite(values[0][index]) for other, values in percentages.items() if other != venue)
			)
			if missing:
				if start is None:
					start = index
			elif start is not None:
				if index - start >= 2 and start > 0 and np.isfinite(daily[start - 1]) and np.isfinite(daily[index]):
					periods.append((dates[start], day))
				start = None
		closures[venue] = periods
	return closures


def plot_occupancy(history: SlotHistory, as_of: datetime, output_path: Path) -> None:
	dates, weeks, percentages = build_occupancy(history, as_of)
	week_boundaries = [*weeks, weeks[-1] + timedelta(weeks=1)]
	closures = infer_closure_periods(dates, history, percentages)
	has_incomplete_weeks = False
	fig, axes = plt.subplots(len(VENUE_CAPACITIES), 1, figsize=(15, 10), sharex=True, sharey=True, constrained_layout=True)
	for axis, (venue, (daily, weekly)) in zip(axes, percentages.items()):
		for week in week_boundaries:
			axis.axvline(week, color="0.8", linewidth=0.5, zorder=0)
		for start, end in closures[venue]:
			axis.axvspan(start, end, facecolor="0.92", edgecolor="none", zorder=-1)
		axis.plot(dates, daily, color="black", linewidth=0.7, linestyle=":", label="Daily")
		observed_days = {day for day, value in zip(dates, daily) if np.isfinite(value)}
		for index, (week, value) in enumerate(zip(weeks, weekly)):
			if not np.isfinite(value):
				continue
			complete = all(week + timedelta(days=offset) in observed_days for offset in range(7))
			has_incomplete_weeks = has_incomplete_weeks or not complete
			next_value = weekly[index + 1] if index + 1 < len(weekly) else value
			axis.step(
				[week, week_boundaries[index + 1]], [value, next_value], where="post",
				color="black", linewidth=1.8, linestyle="-" if complete else "--",
			)
		axis.set_title(venue, loc="left")
		axis.set_ylabel("Occupancy (%)")
		axis.set_ylim(0, 100)
		axis.set_yticks([0, 25, 50, 75, 100])
		axis.grid(axis="y", color="0.85", linewidth=0.5)
		axis.set_xlim(week_boundaries[0], week_boundaries[-1])
	handles, _labels = axes[0].get_legend_handles_labels()
	handles.append(Line2D([], [], color="black", linewidth=1.8, label="Weekly (Mon-Sun)"))
	if has_incomplete_weeks:
		handles.append(Line2D([], [], color="black", linewidth=1.8, linestyle="--", label="Weekly (missing days)"))
	if any(closures.values()):
		handles.append(Patch(facecolor="0.92", label="Inferred closure"))
	axes[0].legend(handles=handles, loc="upper right")
	axes[-1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
	axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))
	axes[-1].set_xlabel("Slot date")
	fig.suptitle(f"Daily and weekly booking occupancy (as of {as_of:%d %b %Y %H:%M})")
	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close(fig)
	print(f"Saved occupancy plot: {output_path}")


def _latest_time(points: list[tuple[datetime, int, str]]) -> str:
	return max(points, key=lambda point: point[0])[2]


def demand_colormap() -> tuple[Colormap, BoundaryNorm]:
	booked_colors = plt.get_cmap("viridis")(np.linspace(0, 1, POND_CAPACITY))
	sold_out_colors = plt.get_cmap("Reds")(np.linspace(0.45, 1, MAX_SOLD_OUT_DAYS * SOLD_OUT_POINTS_PER_DAY))
	cmap = ListedColormap(np.vstack((booked_colors, sold_out_colors)), name="pond_demand").with_extremes(
		bad="#d8d8d8"
	)
	boundaries = np.arange(POND_CAPACITY + MAX_SOLD_OUT_DAYS * SOLD_OUT_POINTS_PER_DAY + 1)
	return cmap, BoundaryNorm(boundaries, cmap.N, clip=True)


def plot_season(data_dir: Path, output_path: Path, occupancy_output: Path | None = None) -> None:
	as_of, history = load_slot_history(data_dir)
	dates, row_labels, matrix = build_heatmap(history, as_of)

	fig, axis = plt.subplots(figsize=(15, 9), constrained_layout=True)
	cmap, norm = demand_colormap()
	image = axis.imshow(
		matrix,
		aspect="auto",
		interpolation="nearest",
		cmap=cmap,
		norm=norm,
		extent=(mdates.date2num(dates[0]) - 0.5, mdates.date2num(dates[-1]) + 0.5, len(row_labels) - 0.5, -0.5),
	)
	axis.set_yticks(range(len(row_labels)), labels=row_labels)
	axis.xaxis_date()
	axis.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
	axis.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
	axis.set_xlabel("Slot date")
	axis.set_ylabel("Venue and logical slot")
	axis.set_title(f"Pond booking demand through the season (as of {as_of:%d %b %Y %H:%M})")
	axis.axhline(len(POND_SLOT_IDS) - 0.5, color="white", linewidth=2)
	axis.axhline(2 * len(POND_SLOT_IDS) - 0.5, color="white", linewidth=2)
	colorbar = fig.colorbar(image, ax=axis, pad=0.02)
	colorbar.set_label("Demand score: tickets booked; red means sold out, darker for earlier sell-out")
	colorbar.set_ticks([0, 30, 60, 90, 120, 140, 160, 180, 190])
	colorbar.ax.axhline(POND_CAPACITY, color="white", linewidth=2)

	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close(fig)
	print(f"Loaded {len(history)} slot histories through {as_of}")
	print(f"Saved plot: {output_path}")
	plot_occupancy(history, as_of, occupancy_output or output_path.with_name("season-occupancy.png"))


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Plot seasonal booking demand and daily/weekly venue occupancy.")
	parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
	parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
	parser.add_argument("--occupancy-output", type=Path, help="Occupancy figure path (default: season-occupancy.png beside --output).")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	plot_season(args.data_dir, args.output, args.occupancy_output)


if __name__ == "__main__":
	main()