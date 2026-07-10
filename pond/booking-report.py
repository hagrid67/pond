from __future__ import annotations

import argparse
import csv
import html as html_lib
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


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


def write_html_report(all_slots, date_sequence, html_output, source_url):
	venues = ["Men's", "Ladies", "Mixed", "Lido"]
	table = defaultdict(lambda: defaultdict(dict))
	for s in all_slots:
		date_label = s.get("date_display") or s.get("date", "")
		table[date_label][s["time"]][s["location"]] = s["availability"]

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
		f.write("</style>\n")
		f.write("<div class='bookings-widget'>\n")
		f.write("<h2>Hampstead Heath Swimming Bookings</h2>\n")
		f.write(
			f"<p class='meta'>Last updated: {html_lib.escape(updated_at)} | "
			f"<a href='{html_lib.escape(source_url)}' target='_blank' rel='noopener noreferrer'>"
			"Open City of London bookings page</a></p>\n"
		)

		for date in dates:
			f.write(f"<h3>{html_lib.escape(date)}</h3>\n")
			f.write("<table>\n<tr><th>Time</th>")
			for v in venues:
				f.write(f"<th>{html_lib.escape(v)}</th>")
			f.write("</tr>\n")
			for t in all_times:
				if t not in table[date]:
					continue
				f.write(f"<tr><td><b>{html_lib.escape(t)}</b></td>")
				for v in venues:
					avail_raw = table[date][t].get(v)
					if avail_raw is None:
						f.write('<td class="empty">—</td>')
						continue

					avail = availability_to_display(avail_raw)
					ticket_count = availability_to_count(avail_raw)

					if ticket_count <= 0:
						f.write('<td class="fully-booked">0</td>')
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
							f'<td class="available" style="position: relative; padding: 0; '
							f'background: {cell_bg_color};">'
						)
						f.write(
							f'<div style="position: absolute; left: 0; top: 0; bottom: 0; '
							f'width: {bar_width}%; background: {bar_color}; pointer-events: none;"></div>'
						)
						f.write(
							f'<div style="position: relative; padding: 6px 12px;">{html_lib.escape(avail)}</div>'
						)
						f.write("</td>")
				f.write("</tr>\n")
			f.write("</table>\n")
		f.write("</div>\n")


def main() -> None:
	parser = argparse.ArgumentParser(description="Generate bookings.html from a bookings CSV file.")
	parser.add_argument("--input-csv", default="output/bookings.csv", help="Bookings CSV filename/path to read.")
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
	args = parser.parse_args()

	input_csv = resolve_output_path(args.output_dir, args.input_csv)
	html_output = resolve_output_path(args.output_dir, args.html_output)
	os.makedirs(os.path.dirname(html_output) or ".", exist_ok=True)

	all_slots, date_sequence = load_slots_from_csv(input_csv)
	write_html_report(all_slots, date_sequence, html_output, args.source_url)
	print(f"Loaded slots from CSV: {input_csv}")
	print(f"Saved: {html_output}")


if __name__ == "__main__":
	main()