from __future__ import annotations

import importlib.util
import os
from datetime import datetime
from pathlib import Path


def _load_booking_report_module():
	module_path = Path(__file__).resolve().parents[1] / "pond" / "booking-report.py"
	spec = importlib.util.spec_from_file_location("pond_booking_report_under_test", module_path)
	if spec is None or spec.loader is None:
		raise RuntimeError("Could not load booking-report.py for testing")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


booking_report = _load_booking_report_module()


def test_report_loads_csv_and_writes_html(tmp_path) -> None:
	csv_path = tmp_path / "bookings.csv"
	html_path = tmp_path / "bookings.html"
	csv_path.write_text(
		"date,time,location,duration,availability\n"
		"2026-07-06,10:00-11:00,Men's,60,12\n"
		"2026-07-06,10:00-11:00,Ladies,60,0\n"
		"2026-07-07,11:00-12:00,Mixed,60,5\n",
		encoding="utf-8",
	)

	all_slots, date_sequence = booking_report.load_slots_from_csv(csv_path)
	assert date_sequence == ["2026-07-06", "2026-07-07"]

	booking_report.write_html_report(all_slots, date_sequence, html_path, "https://example.test/source")
	html = html_path.read_text(encoding="utf-8")

	assert "Hampstead Heath Swimming Bookings" in html
	assert "Monday 2026-07-06" in html
	assert "Tuesday 2026-07-07" in html
	assert "Men&#x27;s" in html
	assert "fully-booked" in html
	assert "https://example.test/source" in html


def test_report_headings_include_relative_day_labels(tmp_path) -> None:
	csv_path = tmp_path / "bookings.csv"
	html_path = tmp_path / "bookings.html"
	csv_path.write_text(
		"date,time,location,duration,availability\n"
		"2026-07-09,10:00-11:00,Men's,60,12\n"
		"2026-07-10,10:00-11:00,Men's,60,8\n"
		"2026-07-11,10:00-11:00,Men's,60,6\n",
		encoding="utf-8",
	)

	all_slots, date_sequence = booking_report.load_slots_from_csv(csv_path)
	booking_report.write_html_report(
		all_slots,
		date_sequence,
		html_path,
		"https://example.test/source",
		reference_time=datetime(2026, 7, 10, 14, 0),
	)
	html = html_path.read_text(encoding="utf-8")

	assert "<a href='#today'>Jump to today</a>" in html
	assert "<h3 id='today'>Friday 2026-07-10 (today)</h3>" in html
	assert "Thursday 2026-07-09 (yesterday)" in html
	assert "Friday 2026-07-10 (today)" in html
	assert "Saturday 2026-07-11 (tomorrow)" in html


def test_report_includes_filter_controls_when_enabled(tmp_path) -> None:
	csv_path = tmp_path / "bookings.csv"
	html_path = tmp_path / "bookings.html"
	csv_path.write_text(
		"date,time,location,duration,availability\n"
		"2026-07-10,10:00-11:00,Men's,60,8\n"
		"2026-07-10,10:30-13:30,Lido,180,60\n"
		"2026-07-10,11:00-12:00,Ladies,60,5\n"
		"2026-07-11,10:00-11:00,Mixed,60,6\n",
		encoding="utf-8",
	)

	all_slots, date_sequence = booking_report.load_slots_from_csv(csv_path)
	booking_report.write_html_report(
		all_slots,
		date_sequence,
		html_path,
		"https://example.test/source",
		reference_time=datetime(2026, 7, 10, 14, 0),
		include_filters=True,
	)
	html = html_path.read_text(encoding="utf-8")

	assert "<h3>Filters</h3>" in html
	assert "Toggle dark background" in html
	assert "Remember my filters on this device: Off" in html
	assert "No login, no tracking; stored only in this browser." in html
	assert "data-filter-group='slot-group' data-filter-value='pond'" in html
	assert "data-filter-group='slot-group' data-filter-value='lido'" in html
	assert "data-filter-group='day-group' data-filter-value='past'" in html
	assert "data-filter-group='day-group' data-filter-value='present'" in html
	assert "data-filter-group='day-group' data-filter-value='future'" in html
	assert "data-filter-group='venue'" in html
	assert "data-filter-group='day'" not in html
	assert "data-day-group='present'" in html
	assert "data-day-group='future'" in html
	assert "data-filter-group='time'" in html
	assert "data-filter-group='time' data-slot-group='pond'" in html
	assert "data-filter-group='time' data-slot-group='lido'" in html
	assert "class='booking-day' data-day='2026-07-10'" in html
	assert "class='bookings-table' data-day='2026-07-10'" in html
	assert "tr data-time='10:00-11:00'" in html
	assert "data-slot-group='pond'" in html
	assert "data-slot-group='lido'" in html


def test_find_latest_bookings_csv_uses_filename_timestamp(tmp_path) -> None:
	older = tmp_path / "bookings-2026-0709-1200.csv"
	newer = tmp_path / "bookings-2026-0710-1200.csv"
	older.write_text("date,time,location,duration,availability\n", encoding="utf-8")
	newer.write_text("date,time,location,duration,availability\n", encoding="utf-8")

	old_stat = older.stat()
	new_stat = newer.stat()
	os.utime(older, (new_stat.st_atime, new_stat.st_mtime + 86400))
	os.utime(newer, (old_stat.st_atime, old_stat.st_mtime - 86400))

	latest = booking_report.find_latest_bookings_csv(tmp_path)
	assert latest == newer


def test_build_report_slots_uses_history_for_disappeared_slots(tmp_path, monkeypatch) -> None:
	def write_archive(name: str, rows: str) -> Path:
		path = tmp_path / name
		path.write_text("date,time,location,duration,availability\n" + rows, encoding="utf-8")
		return path

	write_archive(
		"bookings-2026-0705-0200.csv",
		"2026-0707,10:00-11:00,Men's,60,0\n",
	)
	write_archive(
		"bookings-2026-0707-0955.csv",
		"2026-0707,10:00-11:00,Men's,60,4\n2026-0710,14:00-15:00,Men's,60,8\n",
	)
	write_archive(
		"bookings-2026-0707-1030.csv",
		"2026-0707,10:00-11:00,Men's,60,1\n2026-0710,14:00-15:00,Men's,60,7\n",
	)
	selected = write_archive(
		"bookings-2026-0710-1300.csv",
		"2026-0710,14:00-15:00,Men's,60,6\n",
	)

	monkeypatch.setattr(booking_report, "DATA_DIR", tmp_path)
	report_slots, date_sequence, reference_time = booking_report.build_report_slots(selected)

	assert reference_time == booking_report.parse_archive_timestamp(selected)
	assert "2026-0707" in date_sequence

	historical_slot = next(
		slot
		for slot in report_slots
		if slot["date"] == "2026-0707" and slot["time"] == "10:00-11:00" and slot["location"] == "Men's"
	)
	assert historical_slot["availability_display"] == "4 (1)"
	assert historical_slot["availability_style"] == 4
	assert historical_slot["availability_final"] == 1
	assert historical_slot["booked_out_age"] == "2d8h"