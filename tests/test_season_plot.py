from __future__ import annotations

import importlib.util
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np


def _load_module():
	module_path = Path(__file__).resolve().parents[1] / "pond" / "season-plot.py"
	spec = importlib.util.spec_from_file_location("pond_season_plot_under_test", module_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Could not load season-plot.py")
	module = importlib.util.module_from_spec(spec)
	sys.modules[spec.name] = module
	spec.loader.exec_module(module)
	return module


season_plot = _load_module()


def test_demand_score_counts_bookings_when_slot_is_not_sold_out() -> None:
	start = datetime(2026, 8, 30, 12)
	assert season_plot.demand_score([(start - timedelta(hours=1), 35)], start) == 85


def test_demand_score_adds_ten_points_per_day_sold_out_early() -> None:
	start = datetime(2026, 8, 30, 12)
	points = [
		(start - timedelta(hours=60), 6),
		(start - timedelta(hours=48), 4),
		(start - timedelta(hours=1), 0),
	]
	assert season_plot.demand_score(points, start) == 140


def test_demand_score_caps_sold_out_lead_at_seven_days() -> None:
	start = datetime(2026, 8, 30, 12)
	assert season_plot.demand_score([(start - timedelta(days=9), 0)], start) == 190


def test_demand_score_requires_slot_to_remain_sold_out_at_start() -> None:
	start = datetime(2026, 8, 30, 12)
	points = [(start - timedelta(days=2), 0), (start - timedelta(hours=1), 20)]
	assert season_plot.demand_score(points, start) == 100


def test_demand_colormap_switches_sharply_to_red_at_sold_out() -> None:
	cmap, norm = season_plot.demand_colormap()
	booked_color = np.array(cmap(norm(119)))[:3]
	sold_out_color = np.array(cmap(norm(120)))[:3]

	assert np.linalg.norm(booked_color - sold_out_color) > 0.4
	assert sold_out_color[0] > sold_out_color[1] > sold_out_color[2]


def test_heatmap_merges_aliases_leaves_closures_blank_and_excludes_future() -> None:
	history = {
		("2026-0829", "Men's", "P4"): [
			(datetime(2026, 8, 29, 14), 20, "15:45-16:45"),
		],
		("2026-0830", "Men's", "P4"): [
			(datetime(2026, 8, 30, 14), 10, "15:40-16:40"),
		],
		("2026-0831", "Men's", "P4"): [
			(datetime(2026, 8, 30, 14), 8, "15:40-16:40"),
		],
	}

	dates, row_labels, matrix = season_plot.build_heatmap(history, datetime(2026, 8, 30, 18))

	assert [date.strftime("%Y-%m%d") for date in dates] == ["2026-0829", "2026-0830"]
	mens_p4 = row_labels.index("Men's P4")
	ladies_p4 = row_labels.index("Ladies P4")
	assert matrix[mens_p4].tolist() == [100, 110]
	assert all(math.isnan(value) for value in matrix[ladies_p4])


def test_occupancy_sums_seven_slots_without_sold_out_demand_bonus() -> None:
	history = {
		("2026-0830", "Men's", slot_id): [(datetime(2026, 8, 29), 20, "12:00-13:00")]
		for slot_id in season_plot.POND_SLOT_IDS
	}
	dates, weeks, percentages = season_plot.build_occupancy(history, datetime(2026, 8, 31))
	assert dates == [datetime(2026, 8, 30)]
	assert weeks == [datetime(2026, 8, 24)]
	assert math.isclose(percentages["Men's"][0][0], 700 / 840 * 100)
	assert percentages["Men's"][1] == percentages["Men's"][0]


def test_occupancy_weights_week_by_capacity_and_includes_lido() -> None:
	history = {
		("2026-0824", "Men's", "P1"): [(datetime(2026, 8, 23), 0, "12:00-13:00")],
		("2026-0825", "Men's", "P1"): [(datetime(2026, 8, 23), 120, "12:00-13:00")],
		("2026-0825", "Men's", "P2"): [(datetime(2026, 8, 23), 120, "13:15-14:15")],
		("2026-0824", "Lido", "L1"): [(datetime(2026, 8, 23), 325, "10:30-13:30")],
		("2026-0824", "Lido", "L2"): [(datetime(2026, 8, 23), 0, "14:30-17:30")],
	}
	_dates, _weeks, percentages = season_plot.build_occupancy(history, datetime(2026, 8, 26))
	assert percentages["Men's"][0] == [100, 0]
	assert math.isclose(percentages["Men's"][1][0], 100 / 3)
	assert percentages["Lido"][0][0] == 75
	assert math.isnan(percentages["Lido"][0][1])
	assert percentages["Lido"][1] == [75]


def test_occupancy_uses_last_pre_start_count_and_excludes_unfinished_days() -> None:
	history = {
		("2026-0824", "Mixed", "P1"): [
			(datetime(2026, 8, 24, 11), 4, "12:00-13:00"),
			(datetime(2026, 8, 24, 13), 120, "12:00-13:00"),
		],
		("2026-0825", "Mixed", "P1"): [(datetime(2026, 8, 24), 0, "12:00-13:00")],
	}
	dates, _weeks, percentages = season_plot.build_occupancy(history, datetime(2026, 8, 25, 14))
	assert dates == [datetime(2026, 8, 24)]
	assert math.isclose(percentages["Mixed"][0][0], 116 / 120 * 100)


def test_occupancy_omits_day_with_missing_pre_start_slot_observation() -> None:
	history = {
		("2026-0824", "Men's", "P1"): [(datetime(2026, 8, 23), 0, "12:00-13:00")],
		("2026-0825", "Men's", "P1"): [(datetime(2026, 8, 24), 0, "12:00-13:00")],
		("2026-0825", "Men's", "P2"): [(datetime(2026, 8, 25, 14), 120, "13:15-14:15")],
	}
	dates, _weeks, percentages = season_plot.build_occupancy(history, datetime(2026, 8, 26))
	assert dates == [datetime(2026, 8, 24)]
	assert percentages["Men's"][0] == [100]


def test_season_outputs_separate_occupancy_figure_and_keeps_lido_out_of_heatmap(tmp_path) -> None:
	data_dir = tmp_path / "data"
	data_dir.mkdir()
	(data_dir / "bookings-2026-0829-1000.csv").write_text(
		"date,time,location,duration,availability\n"
		"2026-0830,12:00-13:00,Men's,60,20\n"
		"2026-0830,10:30-13:30,Lido,180,325\n"
		"2026-0830,15:45-16:45,Men's,60,20\n",
		encoding="utf-8",
	)
	(data_dir / "bookings-2026-0831-0003.csv").write_text(
		"date,time,location,duration,availability\n"
		"2026-0830,15:40-16:40,Men's,60,10\n",
		encoding="utf-8",
	)
	as_of, history = season_plot.load_slot_history(data_dir)
	assert ("2026-0830", "Lido", "L1") in history
	assert len(history) == 3
	_dates, labels, _matrix = season_plot.build_heatmap(history, as_of)
	assert len(labels) == 21
	assert not any("Lido" in label for label in labels)
	season_plot.plot_season(data_dir, tmp_path / "season-plot.png")
	assert (tmp_path / "season-plot.png").stat().st_size > 0
	assert (tmp_path / "season-occupancy.png").stat().st_size > 0


def test_closure_detection_requires_bounded_venue_specific_gaps() -> None:
	dates = [datetime(2026, 8, 24) + timedelta(days=offset) for offset in range(12)]
	history = {
		(day.strftime("%Y-%m%d"), venue, "P1"): [(day - timedelta(days=1), 60, "12:00-13:00")]
		for day in dates
		for venue in ("Men's", "Ladies")
		if venue != "Ladies" or not datetime(2026, 8, 26) <= day < datetime(2026, 9, 3)
	}
	percentages = {
		"Men's": ([50.0] * 12, []),
		"Ladies": ([50.0, 50.0] + [float("nan")] * 8 + [50.0, 50.0], []),
		"Mixed": ([float("nan")] * 12, []),
		"Lido": ([50.0] * 5 + [0.0] + [50.0] * 6, []),
	}
	closures = season_plot.infer_closure_periods(dates, history, percentages)
	assert closures == {
		"Men's": [],
		"Ladies": [(datetime(2026, 8, 26), datetime(2026, 9, 3))],
		"Mixed": [],
		"Lido": [],
	}
	percentages["Men's"][0][2:10] = [float("nan")] * 8
	assert season_plot.infer_closure_periods(dates, history, percentages)["Men's"] == []
	percentages["Lido"][0][2:10] = [float("nan")] * 8
	assert season_plot.infer_closure_periods(dates, history, percentages)["Ladies"] == []


def test_closure_detection_does_not_shade_an_isolated_missing_day() -> None:
	dates = [datetime(2026, 8, 24) + timedelta(days=offset) for offset in range(3)]
	percentages = {"Men's": ([50.0] * 3, []), "Ladies": ([50.0, float("nan"), 50.0], [])}
	assert season_plot.infer_closure_periods(dates, {}, percentages) == {"Men's": [], "Ladies": []}


def test_occupancy_figure_marks_monday_boundaries_and_shades_closures(tmp_path, monkeypatch) -> None:
	dates = [datetime(2026, 8, 24) + timedelta(days=offset) for offset in range(12)]
	history = {
		(day.strftime("%Y-%m%d"), venue, "P1"): [(day - timedelta(days=1), 60, "12:00-13:00")]
		for day in dates
		for venue in ("Men's", "Ladies")
		if venue != "Ladies" or not datetime(2026, 8, 26) <= day < datetime(2026, 9, 3)
	}
	figures = []
	monkeypatch.setattr(season_plot.plt.Figure, "savefig", lambda figure, *args, **kwargs: figures.append(figure))
	season_plot.plot_occupancy(history, datetime(2026, 9, 5), tmp_path / "occupancy.png")
	figure = figures[0]
	week_boundaries = [datetime(2026, 8, 24), datetime(2026, 8, 31), datetime(2026, 9, 7)]
	for axis in figure.axes:
		boundaries = [line for line in axis.lines if line.get_zorder() == 0]
		assert [line.get_xdata()[0] for line in boundaries] == week_boundaries
		weekly_line = next(line for line in axis.lines if line.get_label() == "Weekly (Mon-Sun)")
		assert weekly_line.get_drawstyle() == "steps-post"
		assert list(weekly_line.get_xdata()) == week_boundaries
		np.testing.assert_allclose(weekly_line.get_ydata()[-1], weekly_line.get_ydata()[-2])
		np.testing.assert_allclose(axis.get_xticks(), season_plot.mdates.date2num(week_boundaries))
	formatter = figure.axes[-1].xaxis.get_major_formatter()
	assert formatter(season_plot.mdates.date2num(week_boundaries[0])) == "Mon\n24 Aug"
	assert [len(axis.patches) for axis in figure.axes] == [0, 1, 0, 0]
	assert figure.axes[1].patches[0].get_facecolor()[:3] == (0.92, 0.92, 0.92)
	assert [text.get_text() for text in figure.axes[0].get_legend().get_texts()] == [
		"Daily", "Weekly (Mon-Sun)", "Inferred closure",
	]