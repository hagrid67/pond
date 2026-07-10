
import argparse
import csv
from datetime import datetime
import os
import re
import shutil
from bs4 import BeautifulSoup
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


def format_date_machine(date_text, reference_dt=None):
    """Format date as yyyy-mmdd for CSV output.

    Example: "30th Jun" -> "2026-0630"
    """
    reference_dt = reference_dt or datetime.now()
    match = re.search(r"(\d+)(?:st|nd|rd|th)?\s+([A-Za-z]+)", date_text)
    if not match:
        return date_text

    day = int(match.group(1))
    month_text = match.group(2)[:3].title()
    parsed = datetime.strptime(f"{day:02d} {month_text}", "%d %b")
    candidate = parsed.replace(year=reference_dt.year)

    # Handle year rollover when scraping dates around New Year.
    if candidate.month == 1 and reference_dt.month == 12:
        candidate = candidate.replace(year=reference_dt.year + 1)
    elif candidate.month == 12 and reference_dt.month == 1:
        candidate = candidate.replace(year=reference_dt.year - 1)

    return candidate.strftime("%Y-%m%d")

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
    return availability_to_count(availability_str)


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

    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def availability_to_display(availability_value):
    """Convert availability into a plain numeric string for HTML display."""
    text = "" if availability_value is None else str(availability_value).strip()
    if re.fullmatch(r"\d+", text):
        return text
    return str(availability_to_count(availability_value))


def resolve_output_path(output_dir, file_arg):
    """Resolve output path.
    Bare filenames are placed under output_dir.
    Explicit paths (with directory component) are used as-is.
    """
    if os.path.dirname(file_arg):
        return file_arg
    return os.path.join(output_dir, file_arg)


def scrape_bookings(
    days=7,
    user_data_dir="./browser_session",
    headless=False,
    login_url="https://cityoflondon.xnlcloud.com/lhweb/identity/login?signin=f5fa04e53a4777926a3895b7dd3d16ec",
    slots_output="slots.html",
    csv_output="bookings.csv",
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
            machine_date = format_date_machine(date_text)
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
                        "date": machine_date,
                        "date_display": formatted_date,
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
            fieldnames = ["date", "time", "location", "duration", "availability"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(
                {
                    "date": s.get("date", ""),
                    "time": s.get("time", ""),
                    "location": s.get("location", ""),
                    "duration": s.get("duration", ""),
                    "availability": availability_to_count(s.get("availability", "")),
                }
                for s in sorted(
                    all_slots,
                    key=lambda s: (s.get("date", ""), s.get("time", ""), s.get("location", "")),
                )
            )

        os.makedirs(archive_data_dir, exist_ok=True)
        archive_stamp = datetime.now().strftime("%Y-%m%d-%H%M")
        archive_csv = os.path.join(archive_data_dir, f"bookings-{archive_stamp}.csv")
        shutil.copyfile(csv_output, archive_csv)

        print(f"\nTotal slots parsed: {len(all_slots)}")
        available_count = sum(1 for s in all_slots if availability_to_count(s.get("availability")) > 0)
        print(f"Available slots: {available_count}")
        print(f"Saved: {csv_output}")
        print(f"Archived CSV: {archive_csv}")

        browser_context.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape Hampstead Heath swim bookings and generate CSV output.")
    parser.add_argument("--days", type=int, default=7, help="Number of days to scrape starting from current selected day.")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode.")
    parser.add_argument("--user-data-dir", default="./browser_session", help="Path to Playwright persistent user data directory.")
    parser.add_argument("--login-url", default="https://cityoflondon.xnlcloud.com/lhweb/identity/login?signin=f5fa04e53a4777926a3895b7dd3d16ec", help="Initial URL to open before clicking 'Book a swim'.")
    parser.add_argument("--output-dir", default="output", help="Default directory for outputs when output args are bare filenames.")
    parser.add_argument("--data-dir", default="data", help="Directory for timestamped CSV archive copies.")
    parser.add_argument("--slots-output", default="slots.html", help="Raw slot-card HTML filename/path. Bare filename goes under --output-dir.")
    parser.add_argument("--csv-output", default="bookings.csv", help="CSV summary filename/path. Bare filename goes under --output-dir.")
    args = parser.parse_args()

    slots_output = resolve_output_path(args.output_dir, args.slots_output)
    csv_output = resolve_output_path(args.output_dir, args.csv_output)

    os.makedirs(os.path.dirname(slots_output) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(csv_output) or ".", exist_ok=True)
    os.makedirs(args.data_dir, exist_ok=True)

    scrape_bookings(
        days=args.days,
        user_data_dir=args.user_data_dir,
        headless=args.headless,
        login_url=args.login_url,
        slots_output=slots_output,
        csv_output=csv_output,
        archive_data_dir=args.data_dir,
    )


if __name__ == "__main__":
    main()
