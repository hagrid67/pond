"""Download City of London committee reports packs from the ModernGov archive.

Defaults to the Hampstead Heath, Highgate Wood and Queen's Park Committee
(CommitteeId 250) and saves packs as col-pdfs/hhhwqp/YYYY-MMDD-reports-pack.pdf.
Existing files are not downloaded again. An index.csv is kept alongside them.
"""

import argparse
import csv
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://democracy.cityoflondon.gov.uk/'
DEFAULT_COMMITTEE_ID = 250
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOLDER = REPO_ROOT / 'col-pdfs' / 'hhhwqp'
INDEX_FIELDS = [
    'meeting_date', 'meeting_id', 'pack_type', 'filename', 'size_bytes', 'url', 'meeting_url',
]
PACK_TYPES = {
    'reports pack': 'reports-pack',
    'supplementary agenda pack': 'supplementary-pack',
}
REQUEST_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class Meeting:
    meeting_id: int
    meeting_date: date
    url: str


@dataclass(frozen=True)
class Pack:
    meeting: Meeting
    pack_type: str
    url: str
    filename: str


def fetch(session: requests.Session, url: str) -> requests.Response:
    response = session.get(url, timeout=120)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return response


def list_meetings(session: requests.Session, committee_id: int, year: int) -> list[Meeting]:
    # ModernGov listing pages for a year also include neighbouring years, so callers filter by date.
    url = urljoin(BASE_URL, f'ieListMeetings.aspx?CommitteeId={committee_id}&Year={year}')
    soup = BeautifulSoup(fetch(session, url).text, 'html.parser')
    meetings = {}
    for link in soup.find_all('a', href=re.compile(r'ieListDocuments\.aspx\?.*MId=\d+')):
        match = re.search(r'MId=(\d+)', link['href'])
        date_match = re.match(r'\s*(\d{1,2} \w{3} \d{4})', link.get_text(' ', strip=True))
        if not match or not date_match:
            continue
        meeting_id = int(match.group(1))
        meetings[meeting_id] = Meeting(
            meeting_id=meeting_id,
            meeting_date=datetime.strptime(date_match.group(1), '%d %b %Y').date(),
            url=urljoin(BASE_URL, unescape(link['href'])),
        )
    return sorted(meetings.values(), key=lambda meeting: meeting.meeting_date)


def classify_pack(name: str) -> str | None:
    text = name.lower()
    if 'supplementary' in text and 'pack' in text:
        return PACK_TYPES['supplementary agenda pack']
    if 'reports pack' in text:
        return PACK_TYPES['reports pack']
    return None


def find_packs(session: requests.Session, meeting: Meeting, include_supplementary: bool) -> list[Pack]:
    # Some meetings only link the pack from the chooser page, others only from the meeting page.
    chooser_url = urljoin(BASE_URL, f'mgChooseDocPack.aspx?ID={meeting.meeting_id}')
    packs = []
    counts: dict[str, int] = {}
    seen_paths = set()
    for page_url in (chooser_url, meeting.url):
        soup = BeautifulSoup(fetch(session, page_url).text, 'html.parser')
        for link in soup.find_all('a', href=re.compile(r'\.pdf', re.IGNORECASE)):
            pack_url = urljoin(BASE_URL, link['href'])
            path = unquote(urlsplit(pack_url).path)
            pack_type = classify_pack(Path(path).name) or classify_pack(link.get_text(' ', strip=True))
            if pack_type is None or (pack_type != 'reports-pack' and not include_supplementary):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            counts[pack_type] = counts.get(pack_type, 0) + 1
            suffix = '' if counts[pack_type] == 1 else f'-{counts[pack_type]}'
            filename = f'{meeting.meeting_date:%Y-%m%d}-{pack_type}{suffix}.pdf'
            packs.append(Pack(meeting=meeting, pack_type=pack_type, url=pack_url, filename=filename))
    return packs


def download(session: requests.Session, pack: Pack, folder: Path) -> Path:
    target = folder / pack.filename
    if target.exists() and target.stat().st_size > 0:
        print(f'exists   {target.relative_to(REPO_ROOT)}')
        return target
    response = fetch(session, pack.url)
    if not response.content.startswith(b'%PDF'):
        raise ValueError(f'{pack.url} did not return a PDF')
    partial = target.with_suffix('.pdf.part')
    partial.write_bytes(response.content)
    partial.replace(target)
    print(f'saved    {target.relative_to(REPO_ROOT)} ({len(response.content) / 1e6:.1f} MB)')
    return target


def update_index(folder: Path, rows: list[dict[str, str]]) -> Path:
    index_path = folder / 'index.csv'
    existing: dict[str, dict[str, str]] = {}
    if index_path.exists():
        with index_path.open(newline='', encoding='utf-8') as handle:
            existing = {row['filename']: row for row in csv.DictReader(handle)}
    existing.update({row['filename']: row for row in rows})
    with index_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda row: row['filename']))
    return index_path


def parse_years(values: list[str]) -> list[int]:
    years: set[int] = set()
    for value in values:
        if '-' in value:
            start, end = (int(part) for part in value.split('-', 1))
            years.update(range(start, end + 1))
        else:
            years.add(int(value))
    return sorted(years)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--years', nargs='+', default=[str(date.today().year)],
        help='Meeting years to fetch, e.g. 2026 or 2019-2026 (default: current year)',
    )
    parser.add_argument('--committee-id', type=int, default=DEFAULT_COMMITTEE_ID)
    parser.add_argument('--folder', type=Path, default=DEFAULT_FOLDER)
    parser.add_argument(
        '--supplementary', action='store_true',
        help='Also download supplementary agenda packs',
    )
    parser.add_argument('--dry-run', action='store_true', help='List packs without downloading')
    args = parser.parse_args()

    years = parse_years(args.years)
    args.folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'pond-col-downloader/1.0 (+https://github.com/hagrid67/pond)'

    meetings: dict[int, Meeting] = {}
    for year in years:
        for meeting in list_meetings(session, args.committee_id, year):
            if meeting.meeting_date.year in years and meeting.meeting_date <= date.today():
                meetings[meeting.meeting_id] = meeting

    rows = []
    for meeting in sorted(meetings.values(), key=lambda item: item.meeting_date):
        packs = find_packs(session, meeting, args.supplementary)
        if not packs:
            print(f'no pack  {meeting.meeting_date} ({meeting.url})')
            continue
        for pack in packs:
            if args.dry_run:
                print(f'would    {pack.filename} <- {pack.url}')
                continue
            path = download(session, pack, args.folder)
            rows.append({
                'meeting_date': meeting.meeting_date.isoformat(),
                'meeting_id': str(meeting.meeting_id),
                'pack_type': pack.pack_type,
                'filename': pack.filename,
                'size_bytes': str(path.stat().st_size),
                'url': pack.url,
                'meeting_url': meeting.url,
            })
    if rows:
        print(f'index    {update_index(args.folder, rows).relative_to(REPO_ROOT)}')


if __name__ == '__main__':
    main()
