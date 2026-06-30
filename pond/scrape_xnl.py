
import argparse
import csv
from datetime import datetime
import html as html_lib
import os
import re
import shutil
from bs4 import BeautifulSoup
from collections import defaultdict
from playwright.sync_api import sync_playwright

def format_date_nice(day_name, date_text):
    """Format date as 'Tue, 24th Jun'"""
    # day_name: "Thursday", "Today", "Tomorrow" etc.
    # Handle special day names
    if day_name.lower() == "today":
        day_abbr = "Today"
    elif day_name.lower() == "tomorrow":
        day_abbr = "Tomorrow"
    else:
        # Take first 3 characters for day name
        day_abbr = day_name[:3]
    
    return f"{day_abbr}, {date_text}"

def calculate_end_time(start_time_str, duration_str):
    """Calculate end time given start time and duration.
    start_time_str: "10:30"
    duration_str: "1 hour" or "3 hours"
    Returns: "11:30" or "13:30"
    """
    time_match = re.match(r'(\d+):(\d+)', start_time_str)
    duration_match = re.search(r'(\d+)\s*hour', duration_str)
    
    if time_match and duration_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        add_hours = int(duration_match.group(1))
        
        end_hours = hours + add_hours
        if end_hours >= 24:
            end_hours -= 24
        
        return f"{end_hours:02d}:{minutes:02d}"
    return None

def extract_day_number(date_str):
    """Extract day number from formatted date string for sorting.
    Examples: "Today, 23rd Jun" -> 23, "Fri, 26th Jun" -> 26
    """
    match = re.search(r'(\d+)', date_str)
    return int(match.group(1)) if match else 99

def extract_ticket_count(availability_str):
    """Extract number of tickets from availability string.
    Examples: "56 Tickets" -> 56, "Fully Booked" -> 0, "1 Ticket" -> 1
    """
    if availability_str.lower() == "fully booked":
        return 0
    match = re.search(r'(\d+)', availability_str)
    return int(match.group(1)) if match else 0


def resolve_output_path(output_dir, file_arg):
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
        table[s["date"]][s["time"]][s["location"]] = s["availability"]

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
                    avail = table[date][t].get(v)
                    if avail is None:
                        f.write('<td class="empty">—</td>')
                    elif avail.lower() == "fully booked":
                        f.write('<td class="fully-booked">Fully Booked</td>')
                    else:
                        max_capacity = 650 if v == "Lido" else 120
                        ticket_count = extract_ticket_count(avail)
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

def scrape_bookings(
    days=7,
    user_data_dir="./browser_session",
    headless=False,
    login_url="https://cityoflondon.xnlcloud.com/lhweb/identity/login?signin=f5fa04e53a4777926a3895b7dd3d16ec",
    source_url="https://cityoflondon.xnlcloud.com/LhWeb/en/Members/Home",
    slots_output="slots.html",
    csv_output="bookings.csv",
    html_output="bookings.html",
    archive_data_dir="data",
):
    with sync_playwright() as p:
        # 'headless=False' keeps the browser visible
        # 'user_data_dir' saves your cookies/session so you stay logged in
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
        )

        page = browser_context.pages[0]
        page.goto(login_url)

        # Wait for page to load
        page.wait_for_load_state("networkidle")

        # --- Click "Book a swim" button ---
        page.get_by_text("Book a swim", exact=False).first.click()
        page.wait_for_load_state("networkidle")
        print("Clicked 'Book a swim'")

        # Wait for page to load and day selector to appear
        page.wait_for_load_state("networkidle")

        # Map full location names to short column headings
        venue_map = {
            "Parliament Hill Lido": "Lido",
            "Kenwood Ladies Pond": "Ladies",
            "Highgate Men's Pond": "Men's",
            "Hampstead Mixed Pond": "Mixed",
        }
        venues = ["Men's", "Ladies", "Mixed", "Lido"]

        # Collect slots for the requested number of days
        all_slots = []
        date_sequence = []
        html_strings = []

        for _ in range(days):
            day_name = page.locator(".day.selected .name").inner_text().strip()
            selected_date = page.locator(".day.selected .date").inner_html()
            soup_date = BeautifulSoup(selected_date, "html.parser")
            date_text = soup_date.get_text().strip()
            formatted_date = format_date_nice(day_name, date_text)
            if formatted_date not in date_sequence:
                date_sequence.append(formatted_date)
            print(f"Processing: {formatted_date}")

            try:
                page.wait_for_selector(".xn-bookings-grid li", timeout=10000)
            except Exception:
                print("  No booking cards available, skipping")
                page.locator(".next-week").click()
                page.wait_for_load_state("networkidle")
                continue

            grid = page.locator(".xn-bookings-grid")
            cards = grid.locator(":scope > li")
            count = cards.count()

            if count == 0:
                print("  No booking cards found, skipping")
                page.locator(".next-week").click()
                page.wait_for_load_state("networkidle")
                continue

            print(f"  Found {count} booking cards")
            html_strings = []

            for i in range(count):
                html_strings.append(cards.nth(i).inner_html())

            for html in html_strings:
                soup = BeautifulSoup(html, "html.parser")
                spaces_div = soup.find(class_="xn-booking-spaces")
                if spaces_div is None:
                    continue
                location_raw = (soup.find(class_="xn-booking-location") or soup.new_tag("x")).get_text(strip=True)
                location = venue_map.get(location_raw, location_raw)
                availability = spaces_div.get_text(strip=True)
                time_start = (soup.find(class_="xn-booking-starttime") or soup.new_tag("x")).get_text(strip=True)
                duration = (soup.find(class_="xn-booking-duration") or soup.new_tag("x")).get_text(strip=True)
                time_end = calculate_end_time(time_start, duration) or "??:??"
                all_slots.append(
                    {
                        "date": formatted_date,
                        "time": f"{time_start}-{time_end}",
                        "location": location,
                        "duration": duration,
                        "availability": availability,
                    }
                )

            page.locator(".next-week").click()
            page.wait_for_load_state("networkidle")

        with open(slots_output, "w", encoding="utf-8") as f:
            f.write("\n".join(html_strings))

        with open(csv_output, "w", newline="", encoding="utf-8") as f:
            date_index = {d: i for i, d in enumerate(date_sequence)}
            writer = csv.DictWriter(f, fieldnames=["date", "time", "location", "duration", "availability"])
            writer.writeheader()
            writer.writerows(
                sorted(
                    all_slots,
                    key=lambda s: (date_index.get(s["date"], 999), s["time"], s["location"]),
                )
            )

        write_html_report(all_slots, date_sequence, html_output, source_url)

        os.makedirs(archive_data_dir, exist_ok=True)
        archive_stamp = datetime.now().strftime("%Y-%m%d-%H%M")
        archive_csv = os.path.join(archive_data_dir, f"bookings-{archive_stamp}.csv")
        shutil.copyfile(csv_output, archive_csv)

        print(f"\nTotal slots parsed: {len(all_slots)}")
        available_count = sum(1 for s in all_slots if s["availability"].lower() != "fully booked")
        print(f"Available slots: {available_count}")
        print(f"Saved: {csv_output}, {html_output}")
        print(f"Archived CSV: {archive_csv}")

        browser_context.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Hampstead Heath swim bookings and generate CSV/HTML outputs.")
    parser.add_argument("--days", type=int, default=7, help="Number of days to scrape starting from current selected day.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode.")
    parser.add_argument("--user-data-dir", default="./browser_session", help="Path to Playwright persistent user data directory.")
    parser.add_argument("--login-url", default="https://cityoflondon.xnlcloud.com/lhweb/identity/login?signin=f5fa04e53a4777926a3895b7dd3d16ec", help="Initial URL to open before clicking 'Book a swim'.")
    parser.add_argument("--source-url", default="https://cityoflondon.xnlcloud.com/LhWeb/en/Members/Home", help="URL shown in generated HTML as source link.")
    parser.add_argument("--output-dir", default="output", help="Default directory for outputs when output args are bare filenames.")
    parser.add_argument("--data-dir", default="data", help="Directory for timestamped CSV archive copies.")
    parser.add_argument("--slots-output", default="slots.html", help="Raw slot-card HTML filename/path. Bare filename goes under --output-dir.")
    parser.add_argument("--csv-output", default="bookings.csv", help="CSV summary filename/path. Bare filename goes under --output-dir.")
    parser.add_argument("--html-output", default="bookings.html", help="HTML summary filename/path. Bare filename goes under --output-dir.")
    parser.add_argument("--input-csv", default=None, help="Read bookings from CSV and generate HTML without scraping the website.")
    args = parser.parse_args()

    slots_output = resolve_output_path(args.output_dir, args.slots_output)
    csv_output = resolve_output_path(args.output_dir, args.csv_output)
    html_output = resolve_output_path(args.output_dir, args.html_output)

    os.makedirs(os.path.dirname(slots_output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(csv_output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(html_output) or ".", exist_ok=True)
    os.makedirs(args.data_dir, exist_ok=True)

    if args.input_csv:
        all_slots, date_sequence = load_slots_from_csv(args.input_csv)
        write_html_report(all_slots, date_sequence, html_output, args.source_url)
        print(f"Loaded slots from CSV: {args.input_csv}")
        print(f"Saved: {html_output}")
        return

    scrape_bookings(
        days=args.days,
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        login_url=args.login_url,
        source_url=args.source_url,
        slots_output=slots_output,
        csv_output=csv_output,
        html_output=html_output,
        archive_data_dir=args.data_dir,
    )


if __name__ == "__main__":
    main()
