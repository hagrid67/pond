from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import BoundaryNorm, Colormap, ListedColormap, Normalize
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
LIDO_SLOT_IDS = ("L1", "L2", "L3")
LIDO_CAPACITY_ESTIMATES = {"L1": 800, "L2": 800, "L3": 300}

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


def plot_occupancy(history: SlotHistory, as_of: datetime, output_path: Path, *, colour: bool = False) -> None:
	dates, weeks, percentages = build_occupancy(history, as_of)
	week_boundaries = [*weeks, weeks[-1] + timedelta(weeks=1)]
	closures = infer_closure_periods(dates, history, percentages)
	cmap = plt.get_cmap("YlOrRd")
	norm = Normalize(vmin=0, vmax=100)
	has_incomplete_weeks = False
	fig, axes = plt.subplots(len(VENUE_CAPACITIES), 1, figsize=(15, 10), sharex=True, sharey=True, constrained_layout=True)
	for axis, (venue, (daily, weekly)) in zip(axes, percentages.items()):
		for week in week_boundaries:
			axis.axvline(week, color="0.8", linewidth=0.5, zorder=0)
		for start, end in closures[venue]:
			axis.axvspan(start, end, facecolor="0.92", edgecolor="none", zorder=-1)
		axis.plot(dates, daily, color="black", linewidth=0.7, linestyle=":", label="Daily", zorder=3 if colour else 2)
		observed_days = {day for day, value in zip(dates, daily) if np.isfinite(value)}
		for index, (week, value) in enumerate(zip(weeks, weekly)):
			if not np.isfinite(value):
				continue
			if colour:
				axis.bar(
					week, value, width=7, align="edge", color=cmap(norm(value)),
					alpha=0.8, edgecolor="none", zorder=1,
				)
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
	if colour:
		colorbar = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=list(axes), pad=0.02, alpha=0.8)
		colorbar.set_label("Weekly occupancy (%)")
		colorbar.set_ticks([0, 25, 50, 75, 100])
	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close(fig)
	print(f"Saved occupancy plot: {output_path}")


def _latest_time(points: list[tuple[datetime, int, str]]) -> str:
	return max(points, key=lambda point: point[0])[2]


def demand_colormap(capacity: int = POND_CAPACITY) -> tuple[Colormap, BoundaryNorm]:
	booked_colors = plt.get_cmap("viridis")(np.linspace(0, 1, capacity))
	sold_out_colors = plt.get_cmap("Reds")(np.linspace(0.45, 1, MAX_SOLD_OUT_DAYS * SOLD_OUT_POINTS_PER_DAY))
	cmap = ListedColormap(np.vstack((booked_colors, sold_out_colors)), name="pond_demand").with_extremes(
		bad="#d8d8d8"
	)
	boundaries = np.arange(capacity + MAX_SOLD_OUT_DAYS * SOLD_OUT_POINTS_PER_DAY + 1)
	return cmap, BoundaryNorm(boundaries, cmap.N, clip=True)


def build_percentage_heatmap(
	history: SlotHistory,
	as_of: datetime,
	lido_capacities: dict[str, int] | None = None,
) -> tuple[list[datetime], list[str], np.ndarray]:
	lido_capacities = LIDO_CAPACITY_ESTIMATES if lido_capacities is None else lido_capacities
	if any(lido_capacities[slot] <= 0 for slot in LIDO_SLOT_IDS):
		raise ValueError("Lido capacity estimates must be positive")
	rows = [(venue, slot) for venue in VENUES for slot in POND_SLOT_IDS] + [("Lido", slot) for slot in LIDO_SLOT_IDS]
	row_indexes = {key: index for index, key in enumerate(rows)}
	started = {
		key: points for key, points in history.items()
		if key[1:] in row_indexes and parse_slot_start(key[0], _latest_time(points)) <= as_of
	}
	if not started:
		raise ValueError("No completed or started venue slots are available")
	days = [datetime.strptime(key[0], "%Y-%m%d") for key in started]
	first_day, last_day = min(days), max(days)
	dates = [first_day + timedelta(days=offset) for offset in range((last_day - first_day).days + 1)]
	matrix = np.full((len(rows), len(dates)), np.nan)
	for (date_text, venue, slot), points in started.items():
		slot_start = parse_slot_start(date_text, _latest_time(points))
		observed = [(snapshot, available) for snapshot, available, _time in points if snapshot <= slot_start]
		if not observed:
			continue
		capacity = lido_capacities[slot] if venue == "Lido" else POND_CAPACITY
		availability = max(observed, key=lambda point: point[0])[1]
		percentage = 100 * max(0, min(capacity, capacity - availability)) / capacity
		# This heatmap measures demand reached, not whether cancellations left tickets at the start.
		# Keep the first true sell-out (zero remaining), ignoring subsequent cancellations or rebookings.
		first_sold_out = min((snapshot for snapshot, available in observed if available == 0), default=None)
		if first_sold_out is not None:
			lead_days = (slot_start - first_sold_out).total_seconds() / 86400
			percentage = 100 + min(lead_days, MAX_SOLD_OUT_DAYS) * SOLD_OUT_POINTS_PER_DAY
		column = (datetime.strptime(date_text, "%Y-%m%d") - first_day).days
		matrix[row_indexes[(venue, slot)], column] = percentage
	return dates, [f"{venue} {slot}" for venue, slot in rows], matrix


def write_lido_availability_report(
	history: SlotHistory,
	as_of: datetime,
	output_path: Path,
	lido_capacities: dict[str, int],
) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.writer(handle)
		writer.writerow([
			"date", "weekday", "week_start", "slot", "time", "observations",
			"first_snapshot", "first_availability", "max_availability", "last_snapshot",
			"last_availability", "first_lead_hours", "estimated_capacity",
		])
		for (date_text, venue, slot), points in sorted(history.items()):
			if venue != "Lido" or slot not in lido_capacities:
				continue
			time_text = _latest_time(points)
			start = parse_slot_start(date_text, time_text)
			observed = sorted((snapshot, available) for snapshot, available, _time in points if snapshot <= start)
			if start > as_of or not observed:
				continue
			first, last = observed[0], observed[-1]
			writer.writerow([
				start.strftime("%Y-%m-%d"), start.strftime("%a"),
				(start - timedelta(days=start.weekday())).strftime("%Y-%m-%d"), slot, time_text,
				len(observed), first[0].isoformat(), first[1], max(available for _snapshot, available in observed),
				last[0].isoformat(), last[1], round((start - first[0]).total_seconds() / 3600, 2),
				lido_capacities[slot],
			])
	print(f"Saved lido availability report: {output_path}")


def plot_percentage_season(
	history: SlotHistory,
	as_of: datetime,
	output_path: Path,
	lido_capacities: dict[str, int] | None = None,
) -> None:
	lido_capacities = LIDO_CAPACITY_ESTIMATES if lido_capacities is None else lido_capacities
	dates, _labels, matrix = build_percentage_heatmap(history, as_of, lido_capacities)
	fig, axes = plt.subplots(
		4, 1, figsize=(15, 11), sharex=True, constrained_layout=True,
		gridspec_kw={"height_ratios": [7, 7, 7, 3.5]},
	)
	cmap, norm = demand_colormap(capacity=100)
	first_date, last_date = mdates.date2num([dates[0], dates[-1]])
	offset = 0
	for axis, venue in zip(axes, VENUE_CAPACITIES):
		slot_ids = LIDO_SLOT_IDS if venue == "Lido" else POND_SLOT_IDS
		row_count = len(slot_ids)
		image = axis.imshow(
			matrix[offset:offset + row_count], aspect="auto", interpolation="nearest", cmap=cmap, norm=norm,
			extent=(float(first_date) - 0.5, float(last_date) + 0.5, row_count - 0.5, -0.5),
		)
		axis.set_yticks(range(row_count), labels=slot_ids)
		axis.set_title(venue, loc="left", fontsize=11)
		axis.xaxis_date()
		offset += row_count
	axes[-1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
	axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d %b"))
	axes[-1].set_xlabel("Slot date")
	colorbar = fig.colorbar(image, ax=list(axes), pad=0.02)
	colorbar.set_label("Occupancy (%); red: days sold out before the session")
	colorbar.set_ticks([0, 25, 50, 75, 100, 120, 140, 160, 170])
	colorbar.set_ticklabels(["0%", "25%", "50%", "75%", "100%", "2 d", "4 d", "6 d", "7 d"])
	colorbar.ax.axhline(100, color="white", linewidth=2)
	fig.suptitle(f"Seasonal booking occupancy and early sell-outs (as of {as_of:%d %b %Y %H:%M})")
	fig.supxlabel(
		f"Lido estimated capacities: morning {lido_capacities['L1']}, afternoon {lido_capacities['L2']}, "
		f"evening {lido_capacities['L3']} tickets. Grey: no session or no observation.", fontsize=9,
	)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_path, dpi=150, bbox_inches="tight")
	plt.close(fig)
	print(f"Saved percentage season plot: {output_path}")
	write_lido_availability_report(history, as_of, output_path.with_name("lido-availability.csv"), lido_capacities)


def plot_season(
	data_dir: Path,
	output_path: Path,
	occupancy_output: Path | None = None,
	percentage_output: Path | None = None,
	lido_capacities: dict[str, int] | None = None,
	colour_occupancy_output: Path | None = None,
) -> None:
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
	plot_occupancy(history, as_of, colour_occupancy_output or output_path.with_name("season-occupancy-colour.png"), colour=True)
	plot_percentage_season(history, as_of, percentage_output or output_path.with_name("season-percentage.png"), lido_capacities)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Plot seasonal booking demand and daily/weekly venue occupancy.")
	parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
	parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
	parser.add_argument("--occupancy-output", type=Path, help="Occupancy figure path (default: season-occupancy.png beside --output).")
	parser.add_argument("--colour-occupancy-output", type=Path, help="Colour occupancy figure path (default: season-occupancy-colour.png beside --output).")
	parser.add_argument("--percentage-output", type=Path, help="Percentage heatmap path (default: season-percentage.png beside --output).")
	parser.add_argument(
		"--lido-capacities", type=int, nargs=3, metavar=("MORNING", "AFTERNOON", "EVENING"),
		default=tuple(LIDO_CAPACITY_ESTIMATES.values()), help="Estimated lido capacities (default: 800 800 300).",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	plot_season(
		args.data_dir, args.output, args.occupancy_output, args.percentage_output,
		dict(zip(LIDO_SLOT_IDS, args.lido_capacities)),
		args.colour_occupancy_output,
	)


if __name__ == "__main__":
	main()