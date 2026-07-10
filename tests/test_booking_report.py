from __future__ import annotations

import importlib.util
import os
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
	assert "2026-07-06" in html
	assert "2026-07-07" in html
	assert "Men&#x27;s" in html
	assert "fully-booked" in html
	assert "https://example.test/source" in html


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