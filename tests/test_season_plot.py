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