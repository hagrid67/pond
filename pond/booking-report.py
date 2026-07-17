from __future__ import annotations

import argparse
import csv
import html as html_lib
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
ARCHIVE_GLOB = "bookings-*.csv"
HISTORICAL_DAYS = 6
BOOKING_LEAD_DAYS = 7
LIDO_SLOT_TIMES = {"10:30-13:30", "14:30-17:30", "18:00-20:00"}


def availability_to_count(availability_value):
	"""Convert availability text/value into an integer ticket count."""
	if availability_value is None:
		return 0
	if isinstance(availability_value, (int, float)):
		return max(int(availability_value), 0)

	text = str(availability_value).strip()
	if not text:
		return 0
	if text.lower() == "fully booked":
		return 0

	try:
		return max(int(text), 0)
	except ValueError:
		return 0


def availability_to_display(availability_value):
	"""Convert availability into a plain numeric string for HTML display."""
	text = "" if availability_value is None else str(availability_value).strip()
	if text.isdigit():
		return text
	return str(availability_to_count(availability_value))


def resolve_output_path(output_dir: str, file_arg: str) -> str:
	"""Resolve output path.
	Bare filenames are placed under output_dir.
	Explicit paths (with directory component) are used as-is.
	"""
	if os.path.dirname(file_arg):
		return file_arg
	return os.path.join(output_dir, file_arg)


def parse_archive_timestamp(path: Path) -> datetime:
	stamp = path.stem.removeprefix("bookings-")
	return datetime.strptime(stamp, "%Y-%m%d-%H%M")


def find_latest_bookings_csv(data_dir: Path) -> Path:
	matches = sorted(data_dir.glob(ARCHIVE_GLOB))
	if not matches:
		raise FileNotFoundError(f"No archived bookings CSV files matched {data_dir / ARCHIVE_GLOB}")
	return max(matches, key=parse_archive_timestamp)


def infer_snapshot_time(path: Path) -> datetime:
	if path.name.startswith("bookings-") and path.suffix == ".csv":
		return parse_archive_timestamp(path)
	return datetime.fromtimestamp(path.stat().st_mtime)


def parse_slot_start(date_text: str, time_text: str) -> datetime:
	return datetime.strptime(f"{date_text} {time_text.split('-', 1)[0]}", "%Y-%m%d %H:%M")


def slot_group_for_time(slot_time: str) -> str:
	return "lido" if slot_time in LIDO_SLOT_TIMES else "pond"


def parse_booking_date(date_text: str) -> date | None:
	clean = (date_text or "").strip()
	for fmt in ("%Y-%m%d", "%Y-%m-%d"):
		try:
			return datetime.strptime(clean, fmt).date()
		except ValueError:
			continue
	return None


def format_relative_day_label(target_date: date, reference_date: date) -> str:
	delta_days = (target_date - reference_date).days
	if delta_days == 0:
		return "today"
	if delta_days == -1:
		return "yesterday"
	if delta_days == 1:
		return "tomorrow"
	if delta_days < 0:
		return f"{abs(delta_days)} days ago"
	return f"in {delta_days} days"


def format_booking_day_heading(date_text: str, reference_date: date | None = None) -> str:
	"""Format booking day headings as Weekday + original date text (+ relative label)."""
	clean = (date_text or "").strip()
	parsed_date = parse_booking_date(clean)
	if parsed_date is None:
		return clean

	heading = f"{parsed_date.strftime('%A')} {clean}"
	if reference_date is not None:
		relative = format_relative_day_label(parsed_date, reference_date)
		heading = f"{heading} ({relative})"
	return heading


def format_elapsed(delta: timedelta) -> str:
	total_hours = max(int(delta.total_seconds() // 3600), 0)
	days, hours = divmod(total_hours, 24)
	if days:
		return f"{days}d{hours}h" if hours else f"{days}d"
	return f"{hours}h"


def find_effective_count(points: list[tuple[datetime, int]], moment: datetime) -> int | None:
	eligible = [count for snapshot_time, count in points if snapshot_time <= moment]
	if eligible:
		return eligible[-1]
	for snapshot_time, count in points:
		if snapshot_time > moment:
			return count
	return None


def load_slot_history(
	selected_csv: Path,
	historical_days: int = HISTORICAL_DAYS,
	booking_lead_days: int = BOOKING_LEAD_DAYS,
) -> tuple[dict[tuple[str, str, str, str], list[tuple[datetime, int]]], list[str], datetime]:
	reference_time = infer_snapshot_time(selected_csv)
	selected_slots, selected_dates = load_slots_from_csv(selected_csv)
	max_report_date = max((slot["date"] for slot in selected_slots), default=reference_time.strftime("%Y-%m%d"))
	min_report_date = (reference_time.date() - timedelta(days=historical_days)).strftime("%Y-%m%d")
	history_start = datetime.combine(reference_time.date() - timedelta(days=historical_days + booking_lead_days), time(0, 0))

	history_by_slot: dict[tuple[str, str, str, str], list[tuple[datetime, int]]] = defaultdict(list)
	for archive_path in sorted(DATA_DIR.glob(ARCHIVE_GLOB), key=parse_archive_timestamp):
		snapshot_time = parse_archive_timestamp(archive_path)
		if snapshot_time < history_start or snapshot_time > reference_time:
			continue
		archive_slots, _archive_dates = load_slots_from_csv(archive_path)
		for slot in archive_slots:
			if not (min_report_date <= slot["date"] <= max_report_date):
				continue
			key = (slot["date"], slot["time"], slot["location"], slot["duration"])
			history_by_slot[key].append((snapshot_time, availability_to_count(slot["availability"])))

	date_sequence = sorted({slot_date for slot_date, *_rest in history_by_slot})
	return history_by_slot, date_sequence, reference_time


def build_report_slots(
	selected_csv: Path,
	historical_days: int = HISTORICAL_DAYS,
	booking_lead_days: int = BOOKING_LEAD_DAYS,
) -> tuple[list[dict[str, str | int]], list[str], datetime]:
	history_by_slot, date_sequence, reference_time = load_slot_history(
		selected_csv,
		historical_days=historical_days,
		booking_lead_days=booking_lead_days,
	)
	report_slots: list[dict[str, str | int]] = []
	for (slot_date, slot_time, location, duration), points in sorted(history_by_slot.items()):
		sorted_points = sorted(points)
		final_count = sorted_points[-1][1]
		start_dt = parse_slot_start(slot_date, slot_time)
		start_count = find_effective_count(sorted_points, start_dt)
		if start_count is None:
			start_count = final_count
		is_historical = start_dt <= reference_time
		if is_historical and start_count != final_count:
			display_text = f"{start_count} ({final_count})"
			display_count = start_count
		else:
			display_text = str(final_count if not is_historical else start_count)
			display_count = final_count if not is_historical else start_count

		booked_out_age = ""
		first_zero = next((snapshot_time for snapshot_time, count in sorted_points if count == 0), None)
		if final_count < 5 and first_zero is not None and start_dt > first_zero:
			booked_out_age = format_elapsed(start_dt - first_zero)

		report_slots.append(
			{
				"date": slot_date,
				"time": slot_time,
				"location": location,
				"duration": duration,
				"availability": final_count,
				"availability_display": display_text,
				"availability_style": display_count,
				"availability_final": final_count,
				"booked_out_age": booked_out_age,
			}
		)
	return report_slots, date_sequence, reference_time


def load_slots_from_csv(csv_path):
	all_slots = []
	date_sequence = []
	with open(csv_path, newline="", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			slot = {
				"date": (row.get("date") or "").strip(),
				"time": (row.get("time") or "").strip(),
				"location": (row.get("location") or "").strip(),
				"duration": (row.get("duration") or "").strip(),
				"availability": (row.get("availability") or "").strip(),
			}
			if not slot["date"] or not slot["time"] or not slot["location"]:
				continue
			all_slots.append(slot)
			if slot["date"] not in date_sequence:
				date_sequence.append(slot["date"])
	return all_slots, date_sequence


def write_html_report(
	all_slots,
	date_sequence,
	html_output,
	source_url,
	reference_time: datetime | None = None,
	include_filters: bool = False,
):
	venues = ["Men's", "Ladies", "Mixed", "Lido"]
	table = defaultdict(lambda: defaultdict(dict))
	for s in all_slots:
		date_label = s.get("date_display") or s.get("date", "")
		table[date_label][s["time"]][s["location"]] = s["availability"]
		if s.get("availability_display") is not None:
			table[date_label][s["time"]][f"{s['location']}__display"] = s["availability_display"]
		if s.get("availability_style") is not None:
			table[date_label][s["time"]][f"{s['location']}__style"] = s["availability_style"]
		if s.get("availability_final") is not None:
			table[date_label][s["time"]][f"{s['location']}__final"] = s["availability_final"]
		if s.get("booked_out_age"):
			table[date_label][s["time"]][f"{s['location']}__age"] = s["booked_out_age"]

	dates = [d for d in date_sequence if d in table]
	all_times = sorted(set(t for d in table.values() for t in d.keys()))

	with open(html_output, "w", encoding="utf-8") as f:
		updated_at = datetime.now().strftime("%a, %d %b %Y %H:%M")
		f.write("<style>\n")
		f.write("  .bookings-widget { font-family: sans-serif; color: #fff; }\n")
		f.write("  .bookings-widget table { border-collapse: collapse; margin: 0 auto 1rem auto; }\n")
		f.write("  .bookings-widget th, .bookings-widget td { border: 1px solid #666; padding: 6px 12px; text-align: center; color: #fff; }\n")
		f.write("  .bookings-widget th { background: #2f3f3f; }\n")
		f.write("  .bookings-widget tr:nth-child(even) { background: #507070; }\n")
		f.write("  .bookings-widget th:nth-child(even) { background: #507070; }\n")
		f.write("  .bookings-widget .meta { margin: 0.25rem 0 1rem 0; color: #aaa; }\n")
		f.write("  .bookings-widget .meta a { color: #8ab4f8; }\n")
		f.write("  .bookings-widget td.available { background: #d4edda; color: #111; font-weight: bold; }\n")
		f.write("  .bookings-widget td.fully-booked { background: #6b2d2d; color: #fff; }\n")
		f.write("  .bookings-widget td.empty { color: #ccc; }\n")
		f.write("  .bookings-widget .booked-out-age { font-size: 0.78em; opacity: 0.85; }\n")
		f.write("  .bookings-widget .filters { margin: 0.5rem auto 1rem auto; max-width: 1100px; }\n")
		f.write("  .bookings-widget .filter-group { margin: 0.5rem 0; }\n")
		f.write("  .bookings-widget .filter-subgroup { margin: 0.35rem 0; }\n")
		f.write("  .bookings-widget .filter-subgroup-label { font-weight: bold; margin-right: 0.4rem; color: #c8dcdc; }\n")
		f.write("  .bookings-widget .filter-group-label { font-weight: bold; margin-right: 0.4rem; }\n")
		f.write("  .bookings-widget .filter-btn { margin: 0.2rem; padding: 0.25rem 0.55rem; border: 1px solid #6a8080; background: #263636; color: #d9efef; cursor: pointer; border-radius: 4px; }\n")
		f.write("  .bookings-widget .filter-btn.active { background: #507070; color: #fff; }\n")
		f.write("  .bookings-widget .permission-note { color: #b8caca; font-size: 0.9em; margin-left: 0.4rem; }\n")
		f.write("  .bookings-widget.dark-bg { background: #050505; padding: 0.75rem; border-radius: 6px; }\n")
		f.write("</style>\n")
		f.write("<div class='bookings-widget'>\n")
		f.write("<h2>Hampstead Heath Swimming Bookings</h2>\n")
		f.write(
			f"<p class='meta'>Last updated: {html_lib.escape(updated_at)} | "
			f"<a href='{html_lib.escape(source_url)}' target='_blank' rel='noopener noreferrer'>"
			"Open City of London bookings page</a></p>\n"
		)

		reference_date = reference_time.date() if reference_time is not None else None
		has_today = bool(
			reference_date is not None
			and any(parse_booking_date(date) == reference_date for date in dates)
		)
		if has_today:
			f.write("<p><a href='#today'>Jump to today</a></p>\n")

		if include_filters:
			day_groups = {"past": [], "present": [], "future": []}
			day_group_by_date: dict[str, str] = {}
			for day in dates:
				parsed_day = parse_booking_date(day)
				if parsed_day is None or reference_date is None:
					group = "present"
				elif parsed_day < reference_date:
					group = "past"
				elif parsed_day > reference_date:
					group = "future"
				else:
					group = "present"
				day_group_by_date[day] = group
				day_groups[group].append(day)

			f.write("<div class='filters'>\n")
			f.write("<h3>Filters</h3>\n")
			f.write("<div class='filter-group'>")
			f.write("<button type='button' class='filter-btn' data-filter-group='ui' data-filter-value='dark-bg'>Toggle dark background</button>")
			f.write("</div>\n")
			f.write("<div class='filter-group'>")
			f.write("<button type='button' class='filter-btn' data-filter-group='prefs' data-filter-value='remember'>Remember my filters on this device: Off</button>")
			f.write("<span class='permission-note'>No login, no tracking; stored only in this browser.</span>")
			f.write("</div>\n")

			f.write("<div class='filter-group'><span class='filter-group-label'>Slot groups:</span>")
			f.write("<button type='button' class='filter-btn active' data-filter-group='slot-group' data-filter-value='pond'>Pond slots</button>")
			f.write("<button type='button' class='filter-btn active' data-filter-group='slot-group' data-filter-value='lido'>Lido slots</button>")
			f.write("</div>\n")

			f.write("<div class='filter-group'><span class='filter-group-label'>Venues:</span>")
			for idx, venue in enumerate(venues):
				f.write(
					f"<button type='button' class='filter-btn active' "
					f"data-filter-group='venue' data-filter-value='{idx}'>"
					f"{html_lib.escape(venue)}</button>"
				)
			f.write("</div>\n")

			f.write("<div class='filter-group'><span class='filter-group-label'>Day groups:</span>")
			for day_group, group_label in (("past", "Past"), ("present", "Present"), ("future", "Future")):
				f.write(
					f"<button type='button' class='filter-btn active' "
					f"data-filter-group='day-group' data-filter-value='{day_group}'>"
					f"{group_label}</button>"
				)
			f.write("</div>\n")

			f.write("<div class='filter-group'><span class='filter-group-label'>Slot times:</span>")
			for slot_time in all_times:
				slot_group = slot_group_for_time(slot_time)
				time_value = html_lib.escape(slot_time, quote=True)
				f.write(
					f"<button type='button' class='filter-btn active' "
					f"data-filter-group='time' data-slot-group='{slot_group}' data-filter-value='{time_value}'>"
					f"{html_lib.escape(slot_time)}</button>"
				)
			f.write("</div>\n")
			f.write("</div>\n")

		for date in dates:
			date_value = html_lib.escape(date, quote=True)
			day_group = day_group_by_date[date] if include_filters else "present"
			f.write(f"<div class='booking-day' data-day='{date_value}' data-day-group='{day_group}'>\n")
			date_heading = format_booking_day_heading(date, reference_date)
			if reference_date is not None and parse_booking_date(date) == reference_date:
				f.write(f"<h3 id='today'>{html_lib.escape(date_heading)}</h3>\n")
			else:
				f.write(f"<h3>{html_lib.escape(date_heading)}</h3>\n")
			f.write(f"<table class='bookings-table' data-day='{date_value}'>\n<tr><th>Time</th>")
			for idx, v in enumerate(venues):
				f.write(f"<th class='venue-col' data-venue-idx='{idx}'>{html_lib.escape(v)}</th>")
			f.write("</tr>\n")
			for t in all_times:
				if t not in table[date]:
					continue
				slot_group = slot_group_for_time(t)
				time_value = html_lib.escape(t, quote=True)
				f.write(
					f"<tr data-time='{time_value}' data-slot-group='{slot_group}'>"
					f"<td><b>{html_lib.escape(t)}</b></td>"
				)
				for idx, v in enumerate(venues):
					avail_raw = table[date][t].get(v)
					if avail_raw is None:
						f.write(f'<td class="empty venue-cell" data-venue-idx="{idx}">—</td>')
						continue

					avail = str(table[date][t].get(f"{v}__display") or availability_to_display(avail_raw))
					ticket_count = availability_to_count(table[date][t].get(f"{v}__style", avail_raw))
					booked_out_age = str(table[date][t].get(f"{v}__age") or "")

					if ticket_count <= 0:
						f.write(f'<td class="fully-booked venue-cell" data-venue-idx="{idx}">')
						f.write(html_lib.escape(avail))
						if booked_out_age:
							f.write(f'<div class="booked-out-age">{html_lib.escape(booked_out_age)}</div>')
						f.write("</td>")
					else:
						max_capacity = 650 if v == "Lido" else 120
						ratio = (ticket_count / max_capacity) if ticket_count > 0 else 0
						percentage = ratio * 100
						if ratio < (1 / 6):
							bar_color = "rgba(234, 88, 12, 0.45)"
							cell_bg_color = "#ffedd5"
						elif ratio < (1 / 3):
							bar_color = "rgba(250, 204, 21, 0.35)"
							cell_bg_color = "#fef9c3"
						else:
							bar_color = "rgba(34, 197, 94, 0.35)"
							cell_bg_color = "#d4edda"
						bar_width = min(percentage, 100)
						f.write(
							f'<td class="available venue-cell" data-venue-idx="{idx}" style="position: relative; padding: 0; '
							f'background: {cell_bg_color};">'
						)
						f.write(
							f'<div style="position: absolute; left: 0; top: 0; bottom: 0; '
							f'width: {bar_width}%; background: {bar_color}; pointer-events: none;"></div>'
						)
						f.write(
							f'<div style="position: relative; padding: 6px 12px;">{html_lib.escape(avail)}'
						)
						if booked_out_age:
							f.write(f'<div class="booked-out-age">{html_lib.escape(booked_out_age)}</div>')
						f.write("</div>")
						f.write("</td>")
				f.write("</tr>\n")
			f.write("</table>\n")
			f.write("</div>\n")

		if include_filters:
			f.write("<script>\n")
			f.write("(function() {\n")
			f.write("  const PREFS_STORAGE_KEY = 'pondBookingsFilterPrefs';\n")
			f.write("  const PREFS_CONSENT_KEY = 'pondBookingsFilterPrefsConsent';\n")
			f.write("  const widget = document.querySelector('.bookings-widget');\n")
			f.write("  const uiButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"ui\\\"]'));\n")
			f.write("  const prefsButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"prefs\\\"]'));\n")
			f.write("  const rememberButton = prefsButtons.find(btn => btn.dataset.filterValue === 'remember');\n")
			f.write("  const slotGroupButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"slot-group\\\"]'));\n")
			f.write("  const venueButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"venue\\\"]'));\n")
			f.write("  const dayGroupButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"day-group\\\"]'));\n")
			f.write("  const timeButtons = Array.from(document.querySelectorAll('.filter-btn[data-filter-group=\\\"time\\\"]'));\n")
			f.write("  const selectedVenues = new Set(venueButtons.map(btn => btn.dataset.filterValue));\n")
			f.write("  const selectedDayGroups = new Set(dayGroupButtons.map(btn => btn.dataset.filterValue));\n")
			f.write("  const selectedTimes = new Set(timeButtons.map(btn => btn.dataset.filterValue));\n")
			f.write("  const selectedSlotGroups = new Set(slotGroupButtons.map(btn => btn.dataset.filterValue));\n")
			f.write("  let persistPrefs = false;\n")
			f.write("\n")
			f.write("  function readStorage(key) {\n")
			f.write("    try {\n")
			f.write("      return window.localStorage.getItem(key);\n")
			f.write("    } catch (_err) {\n")
			f.write("      return null;\n")
			f.write("    }\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function writeStorage(key, value) {\n")
			f.write("    try {\n")
			f.write("      window.localStorage.setItem(key, value);\n")
			f.write("      return true;\n")
			f.write("    } catch (_err) {\n")
			f.write("      return false;\n")
			f.write("    }\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function removeStorage(key) {\n")
			f.write("    try {\n")
			f.write("      window.localStorage.removeItem(key);\n")
			f.write("    } catch (_err) {\n")
			f.write("      // Ignore storage removal failures.\n")
			f.write("    }\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function setButtonState(button, isActive) {\n")
			f.write("    button.classList.toggle('active', isActive);\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function updateRememberButton() {\n")
			f.write("    if (!rememberButton) {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("    rememberButton.textContent = persistPrefs\n")
			f.write("      ? 'Remember my filters on this device: On'\n")
			f.write("      : 'Remember my filters on this device: Off';\n")
			f.write("    setButtonState(rememberButton, persistPrefs);\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function savePreferences() {\n")
			f.write("    if (!persistPrefs) {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("    const payload = {\n")
			f.write("      venues: Array.from(selectedVenues),\n")
			f.write("      dayGroups: Array.from(selectedDayGroups),\n")
			f.write("      times: Array.from(selectedTimes),\n")
			f.write("      slotGroups: Array.from(selectedSlotGroups),\n")
			f.write("      darkBg: !!(widget && widget.classList.contains('dark-bg'))\n")
			f.write("    };\n")
			f.write("    writeStorage(PREFS_STORAGE_KEY, JSON.stringify(payload));\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function loadPreferences() {\n")
			f.write("    const raw = readStorage(PREFS_STORAGE_KEY);\n")
			f.write("    if (!raw) {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("    let parsed = null;\n")
			f.write("    try {\n")
			f.write("      parsed = JSON.parse(raw);\n")
			f.write("    } catch (_err) {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("\n")
			f.write("    if (parsed && Array.isArray(parsed.venues)) {\n")
			f.write("      selectedVenues.clear();\n")
			f.write("      parsed.venues.forEach(value => {\n")
			f.write("        if (venueButtons.some(btn => btn.dataset.filterValue === value)) {\n")
			f.write("          selectedVenues.add(value);\n")
			f.write("        }\n")
			f.write("      });\n")
			f.write("    }\n")
			f.write("    if (parsed && Array.isArray(parsed.dayGroups)) {\n")
			f.write("      selectedDayGroups.clear();\n")
			f.write("      parsed.dayGroups.forEach(value => {\n")
			f.write("        if (dayGroupButtons.some(btn => btn.dataset.filterValue === value)) {\n")
			f.write("          selectedDayGroups.add(value);\n")
			f.write("        }\n")
			f.write("      });\n")
			f.write("    }\n")
			f.write("    if (parsed && Array.isArray(parsed.times)) {\n")
			f.write("      selectedTimes.clear();\n")
			f.write("      parsed.times.forEach(value => {\n")
			f.write("        if (timeButtons.some(btn => btn.dataset.filterValue === value)) {\n")
			f.write("          selectedTimes.add(value);\n")
			f.write("        }\n")
			f.write("      });\n")
			f.write("    }\n")
			f.write("    if (parsed && Array.isArray(parsed.slotGroups)) {\n")
			f.write("      selectedSlotGroups.clear();\n")
			f.write("      parsed.slotGroups.forEach(value => {\n")
			f.write("        if (slotGroupButtons.some(btn => btn.dataset.filterValue === value)) {\n")
			f.write("          selectedSlotGroups.add(value);\n")
			f.write("        }\n")
			f.write("      });\n")
			f.write("    }\n")
			f.write("\n")
			f.write("    if (widget && parsed && parsed.darkBg) {\n")
			f.write("      widget.classList.add('dark-bg');\n")
			f.write("    }\n")
			f.write("\n")
			f.write("    venueButtons.forEach(btn => setButtonState(btn, selectedVenues.has(btn.dataset.filterValue)));\n")
			f.write("    dayGroupButtons.forEach(btn => setButtonState(btn, selectedDayGroups.has(btn.dataset.filterValue)));\n")
			f.write("    timeButtons.forEach(btn => setButtonState(btn, selectedTimes.has(btn.dataset.filterValue)));\n")
			f.write("    slotGroupButtons.forEach(btn => setButtonState(btn, selectedSlotGroups.has(btn.dataset.filterValue)));\n")
			f.write("    const darkToggle = uiButtons.find(btn => btn.dataset.filterValue === 'dark-bg');\n")
			f.write("    if (darkToggle && widget) {\n")
			f.write("      setButtonState(darkToggle, widget.classList.contains('dark-bg'));\n")
			f.write("    }\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function refreshDayGroupButtons() {\n")
			f.write("    dayGroupButtons.forEach(groupBtn => {\n")
			f.write("      setButtonState(groupBtn, selectedDayGroups.has(groupBtn.dataset.filterValue));\n")
			f.write("    });\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function refreshSlotGroupButtons() {\n")
			f.write("    slotGroupButtons.forEach(groupBtn => {\n")
			f.write("      const groupName = groupBtn.dataset.filterValue;\n")
			f.write("      setButtonState(groupBtn, selectedSlotGroups.has(groupName));\n")
			f.write("    });\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  function applyFilters() {\n")
			f.write("    timeButtons.forEach(button => {\n")
			f.write("      const slotGroup = button.dataset.slotGroup;\n")
			f.write("      button.style.display = selectedSlotGroups.has(slotGroup) ? '' : 'none';\n")
			f.write("    });\n")
			f.write("\n")
			f.write("    document.querySelectorAll('.bookings-widget .bookings-table').forEach(table => {\n")
			f.write("      table.querySelectorAll('th.venue-col, td.venue-cell').forEach(cell => {\n")
			f.write("        const venueIdx = cell.dataset.venueIdx;\n")
			f.write("        cell.style.display = selectedVenues.has(venueIdx) ? '' : 'none';\n")
			f.write("      });\n")
			f.write("\n")
			f.write("      table.querySelectorAll('tr[data-time]').forEach(row => {\n")
			f.write("        const timeMatch = selectedTimes.has(row.dataset.time);\n")
			f.write("        const slotGroupMatch = selectedSlotGroups.has(row.dataset.slotGroup);\n")
			f.write("        const hasVisibleVenue = Array.from(row.querySelectorAll('td.venue-cell')).some(cell => cell.style.display !== 'none');\n")
			f.write("        row.style.display = (timeMatch && slotGroupMatch && hasVisibleVenue) ? '' : 'none';\n")
			f.write("      });\n")
			f.write("    });\n")
			f.write("\n")
			f.write("    document.querySelectorAll('.bookings-widget .booking-day').forEach(section => {\n")
			f.write("      const daySelected = selectedDayGroups.has(section.dataset.dayGroup);\n")
			f.write("      const hasVisibleRows = Array.from(section.querySelectorAll('tr[data-time]')).some(row => row.style.display !== 'none');\n")
			f.write("      section.style.display = (daySelected && hasVisibleRows) ? '' : 'none';\n")
			f.write("    });\n")
			f.write("    refreshDayGroupButtons();\n")
			f.write("    refreshSlotGroupButtons();\n")
			f.write("    savePreferences();\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  prefsButtons.forEach(button => {\n")
			f.write("    if (button.dataset.filterValue !== 'remember') {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("    button.addEventListener('click', () => {\n")
			f.write("      persistPrefs = !persistPrefs;\n")
			f.write("      if (persistPrefs) {\n")
			f.write("        if (!writeStorage(PREFS_CONSENT_KEY, 'accepted')) {\n")
			f.write("          persistPrefs = false;\n")
			f.write("        }\n")
			f.write("      } else {\n")
			f.write("        removeStorage(PREFS_CONSENT_KEY);\n")
			f.write("        removeStorage(PREFS_STORAGE_KEY);\n")
			f.write("      }\n")
			f.write("      updateRememberButton();\n")
			f.write("      savePreferences();\n")
			f.write("    });\n")
			f.write("  });\n")
			f.write("\n")
			f.write("  uiButtons.forEach(button => {\n")
			f.write("    if (button.dataset.filterValue !== 'dark-bg') {\n")
			f.write("      return;\n")
			f.write("    }\n")
			f.write("    button.addEventListener('click', () => {\n")
			f.write("      if (!widget) {\n")
			f.write("        return;\n")
			f.write("      }\n")
			f.write("      widget.classList.toggle('dark-bg');\n")
			f.write("      setButtonState(button, widget.classList.contains('dark-bg'));\n")
			f.write("    });\n")
			f.write("  });\n")
			f.write("\n")
			f.write("  slotGroupButtons.forEach(button => {\n")
			f.write("    button.addEventListener('click', () => {\n")
			f.write("      const value = button.dataset.filterValue;\n")
			f.write("      if (selectedSlotGroups.has(value)) {\n")
			f.write("        selectedSlotGroups.delete(value);\n")
			f.write("      } else {\n")
			f.write("        selectedSlotGroups.add(value);\n")
			f.write("      }\n")
			f.write("      setButtonState(button, selectedSlotGroups.has(value));\n")
			f.write("      applyFilters();\n")
			f.write("    });\n")
			f.write("  });\n")
			f.write("\n")
			f.write("  dayGroupButtons.forEach(button => {\n")
			f.write("    button.addEventListener('click', () => {\n")
			f.write("      const value = button.dataset.filterValue;\n")
			f.write("      if (selectedDayGroups.has(value)) {\n")
			f.write("        selectedDayGroups.delete(value);\n")
			f.write("      } else {\n")
			f.write("        selectedDayGroups.add(value);\n")
			f.write("      }\n")
			f.write("      setButtonState(button, selectedDayGroups.has(value));\n")
			f.write("      applyFilters();\n")
			f.write("    });\n")
			f.write("  });\n")
			f.write("\n")
			f.write("  function wireButtons(buttons, selectedSet) {\n")
			f.write("    buttons.forEach(button => {\n")
			f.write("      button.addEventListener('click', () => {\n")
			f.write("        const value = button.dataset.filterValue;\n")
			f.write("        if (selectedSet.has(value)) {\n")
			f.write("          selectedSet.delete(value);\n")
			f.write("        } else {\n")
			f.write("          selectedSet.add(value);\n")
			f.write("        }\n")
			f.write("        setButtonState(button, selectedSet.has(value));\n")
			f.write("        applyFilters();\n")
			f.write("      });\n")
			f.write("    });\n")
			f.write("  }\n")
			f.write("\n")
			f.write("  wireButtons(venueButtons, selectedVenues);\n")
			f.write("  wireButtons(timeButtons, selectedTimes);\n")
			f.write("  persistPrefs = readStorage(PREFS_CONSENT_KEY) === 'accepted';\n")
			f.write("  updateRememberButton();\n")
			f.write("  if (persistPrefs) {\n")
			f.write("    loadPreferences();\n")
			f.write("  }\n")
			f.write("  refreshDayGroupButtons();\n")
			f.write("  refreshSlotGroupButtons();\n")
			f.write("  applyFilters();\n")
			f.write("})();\n")
			f.write("</script>\n")
		f.write("</div>\n")


def main() -> None:
	parser = argparse.ArgumentParser(description="Generate bookings.html from a bookings CSV file.")
	parser.add_argument(
		"--input-csv",
		default=None,
		help="Bookings CSV filename/path to read. Default: newest archived bookings CSV in ./data.",
	)
	parser.add_argument(
		"--html-output",
		default="output/bookings.html",
		help="HTML summary filename/path. Bare filename goes under --output-dir.",
	)
	parser.add_argument(
		"--source-url",
		default="https://cityoflondon.xnlcloud.com/LhWeb/en/Members/Home",
		help="URL shown in the generated HTML as the source link.",
	)
	parser.add_argument(
		"--output-dir",
		default="output",
		help="Default directory for outputs when output args are bare filenames.",
	)
	parser.add_argument(
		"--filters",
		action="store_true",
		help="Enable interactive filter buttons for venues, days, and slot times.",
	)
	args = parser.parse_args()

	if args.input_csv is None:
		input_csv = find_latest_bookings_csv(DATA_DIR)
	else:
		input_csv = Path(resolve_output_path(args.output_dir, args.input_csv))
	html_output = resolve_output_path(args.output_dir, args.html_output)
	os.makedirs(os.path.dirname(html_output) or ".", exist_ok=True)

	all_slots, date_sequence, reference_time = build_report_slots(input_csv)
	write_html_report(
		all_slots,
		date_sequence,
		html_output,
		args.source_url,
		reference_time=reference_time,
		include_filters=args.filters,
	)
	print(f"Loaded slots from CSV: {input_csv}")
	print(f"Saved: {html_output}")


if __name__ == "__main__":
	main()