from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType


def _load_booking_plot_module():
	saved_modules = {
		name: sys.modules.get(name)
		for name in ("matplotlib", "matplotlib.dates", "matplotlib.pyplot")
	}

	class _StubObject:
		def __init__(self, *args, **kwargs):
			self.args = args
			self.kwargs = kwargs

	matplotlib = ModuleType("matplotlib")
	mdates = ModuleType("matplotlib.dates")
	plt = ModuleType("matplotlib.pyplot")
	mdates.DateFormatter = _StubObject
	mdates.HourLocator = _StubObject
	mdates.MinuteLocator = _StubObject
	mdates.num2date = lambda value: value
	plt.get_cmap = lambda _name: (lambda index: f"color-{index}")
	plt.subplots = lambda *args, **kwargs: None
	matplotlib.dates = mdates
	matplotlib.pyplot = plt

	sys.modules["matplotlib"] = matplotlib
	sys.modules["matplotlib.dates"] = mdates
	sys.modules["matplotlib.pyplot"] = plt

	module_name = "pond_booking_plot_under_test"
	spec = importlib.util.spec_from_file_location(
		module_name,
		Path(__file__).resolve().parents[1] / "pond" / "booking-plot.py",
	)
	if spec is None or spec.loader is None:
		raise RuntimeError("Could not load booking-plot.py for testing")
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	try:
		spec.loader.exec_module(module)
	finally:
		for name, previous in saved_modules.items():
			if previous is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = previous
	return module


booking_plot = _load_booking_plot_module()


def _date(text: str) -> str:
	return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m%d")


def _snapshot(date_text: str, hour: int = 10) -> datetime:
	return datetime.strptime(f"{date_text} {hour:02d}:00", "%Y-%m%d %H:%M")


@dataclass
class _FakeLine:
	color: str

	def get_color(self) -> str:
		return self.color


class _FakeXAxis:
	def __init__(self) -> None:
		self.major_locator = None
		self.major_formatter = None
		self.minor_locator = None

	def set_major_locator(self, locator) -> None:
		self.major_locator = locator

	def set_major_formatter(self, formatter) -> None:
		self.major_formatter = formatter

	def set_minor_locator(self, locator) -> None:
		self.minor_locator = locator


class _FakeAxis:
	def __init__(self) -> None:
		self.xaxis = _FakeXAxis()
		self.transAxes = object()
		self.plots = []
		self.annotations = []
		self.texts = []
		self.titles = []
		self.xlabel = None
		self.ylabel = None
		self.ylim = None
		self.xlim = None
		self.xticks = None
		self.xticklabels = None
		self.axis_off = False

	def plot(self, *args, **kwargs):
		self.plots.append((args, kwargs))
		return (_FakeLine(kwargs.get("color", "color-0")),)

	def annotate(self, *args, **kwargs) -> None:
		self.annotations.append((args, kwargs))

	def text(self, *args, **kwargs) -> None:
		self.texts.append((args, kwargs))

	def set_axis_off(self) -> None:
		self.axis_off = True

	def set_title(self, value) -> None:
		self.titles.append(value)

	def set_ylabel(self, value) -> None:
		self.ylabel = value

	def set_xlabel(self, value) -> None:
		self.xlabel = value

	def set_ylim(self, *args) -> None:
		self.ylim = args

	def set_xlim(self, *args) -> None:
		self.xlim = args

	def grid(self, *args, **kwargs) -> None:
		return None

	def legend(self, *args, **kwargs) -> None:
		return None

	def axvline(self, *args, **kwargs) -> None:
		return None

	def set_xticks(self, ticks) -> None:
		self.xticks = list(ticks)

	def set_xticklabels(self, labels) -> None:
		self.xticklabels = list(labels)


class _FakeFigure:
	def __init__(self) -> None:
		self.legend_calls = []
		self.suptitles = []
		self.saved_paths = []

	def legend(self, *args, **kwargs) -> None:
		self.legend_calls.append((args, kwargs))

	def suptitle(self, value) -> None:
		self.suptitles.append(value)

	def savefig(self, path, **kwargs) -> None:
		self.saved_paths.append((path, kwargs))


def _slot(date_text: str, time_text: str = "10:00-11:00", location: str = "Men's"):
	return booking_plot.SlotKey(
		date=date_text,
		time=time_text,
		location=location,
		duration="60",
	)


def test_plot_no_slots_saves_current_empty_state(monkeypatch, tmp_path) -> None:
	axis = _FakeAxis()
	figure = _FakeFigure()
	monkeypatch.setattr(booking_plot.plt, "subplots", lambda **_kwargs: (figure, axis))
	monkeypatch.setattr(booking_plot, "OUTPUT_DIR", tmp_path)

	booking_plot.plot_no_slots(["Ladies"], datetime(2026, 8, 23, 18, 6))

	assert axis.texts[0][0][2] == "No slots available for Ladies"
	assert axis.axis_off
	assert figure.saved_paths[0][0] == tmp_path / "booking-plot-ladies.png"


def test_filter_slots_keeps_today_and_previous_four_days() -> None:
	by_slot = {
		_slot(_date("2026-07-06")): [(datetime(2026, 7, 10, 8, 0), 1)],
		_slot(_date("2026-07-07")): [(datetime(2026, 7, 10, 8, 0), 2)],
		_slot(_date("2026-07-08")): [(datetime(2026, 7, 10, 8, 0), 3)],
		_slot(_date("2026-07-09")): [(datetime(2026, 7, 10, 8, 0), 4)],
		_slot(_date("2026-07-10")): [(datetime(2026, 7, 10, 8, 0), 5)],
		_slot(_date("2026-07-11")): [(datetime(2026, 7, 10, 8, 0), 6)],
	}

	filtered = booking_plot.filter_slots(
		by_slot,
		venues=["Men's"],
		plot_days=5,
		anchor_date=_date("2026-07-10"),
		date_offset_days=-4,
	)

	assert sorted(slot.date for slot in filtered) == [
		_date("2026-07-06"),
		_date("2026-07-07"),
		_date("2026-07-08"),
		_date("2026-07-09"),
		_date("2026-07-10"),
	]


def test_separate_axes_creates_one_column_per_filtered_date(monkeypatch) -> None:
	by_slot = {
		_slot(_date("2026-07-06")): [(_snapshot(_date("2026-07-06")), 1)],
		_slot(_date("2026-07-07")): [(_snapshot(_date("2026-07-07")), 2)],
		_slot(_date("2026-07-08")): [(_snapshot(_date("2026-07-08")), 3)],
		_slot(_date("2026-07-09")): [(_snapshot(_date("2026-07-09")), 4)],
		_slot(_date("2026-07-10")): [(_snapshot(_date("2026-07-10")), 5)],
	}
	axes = [_FakeAxis() for _ in range(5)]
	figure = _FakeFigure()
	captured = {}

	def fake_subplots(*, nrows, ncols, **kwargs):
		captured["nrows"] = nrows
		captured["ncols"] = ncols
		captured["kwargs"] = kwargs
		return figure, axes

	monkeypatch.setattr(booking_plot.plt, "subplots", fake_subplots)

	booking_plot.plot_slots_separate_axes(
		by_slot,
		venues=["Men's"],
		focus_date=_date("2026-07-10"),
		latest_snapshot_time=datetime(2026, 7, 10, 12, 0),
		show_prevday=False,
		show_nextday=False,
		per_slot_from_days=None,
		include_night=True,
	)

	assert captured["nrows"] == 1
	assert captured["ncols"] == 5
	assert len(axes) == 5
	assert all(axis.plots for axis in axes)