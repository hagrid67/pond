"""Download City of London committee reports packs from the ModernGov archive.

Defaults to the Hampstead Heath, Highgate Wood and Queen's Park Committee
(CommitteeId 250). Each meeting gets a folder such as col-pdfs/hhhwqp/2026-0203/
holding reports-pack.pdf, supplementary-pack.pdf and the individual agenda
documents. Existing files are not downloaded again. An index.csv is kept in the
committee folder.
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
REPO_ROOT = Path(__file__).resolve().parents[1]
PDF_ROOT = REPO_ROOT / 'col-pdfs'
COMMITTEES = {
    'hhhwqp': 250,
    'hhcc': 261,
    'finance': 145,
    'ras': 396,
}
INDEX_FIELDS = [
    'meeting_date', 'meeting_id', 'item', 'item_title', 'doc_type', 'title', 'path', 'size_bytes',
    'url', 'meeting_url',
]
REQUEST_DELAY_SECONDS = 1.0
RETRY_DELAYS_SECONDS = (10, 30, 90)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Meeting:
    meeting_id: int
    meeting_date: date
    url: str

    @property
    def folder_name(self) -> str:
        return f'{self.meeting_date:%Y-%m%d}'


@dataclass(frozen=True)
class Document:
    meeting: Meeting
    doc_type: str
    url: str
    path: str
    title: str = ''
    item: str = ''
    item_title: str = ''


def display(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def fetch(session: requests.Session, url: str) -> requests.Response:
    """GET with a polite delay, retrying timeouts and transient server errors with back-off."""
    for attempt, retry_delay in enumerate((*RETRY_DELAYS_SECONDS, None), start=1):
        try:
            response = session.get(url, timeout=120)
            if response.status_code not in RETRY_STATUS_CODES or retry_delay is None:
                response.raise_for_status()
                time.sleep(REQUEST_DELAY_SECONDS)
                return response
            reason = f'HTTP {response.status_code}'
        except (requests.ConnectionError, requests.Timeout) as error:
            if retry_delay is None:
                raise
            reason = type(error).__name__
        print(f'retry    {reason} (attempt {attempt}), waiting {retry_delay}s: {url}', flush=True)
        time.sleep(retry_delay)
    raise AssertionError('unreachable')


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
    """Classify meeting-level files (packs, frontsheet, minutes); agenda documents return None."""
    text = name.lower()
    if 'supplementary' in text and 'pack' in text:
        return 'supplementary-pack'
    for phrase, doc_type in (
        ('reports pack', 'reports-pack'),
        ('information pack', 'information-pack'),
        ('agenda frontsheet', 'agenda-frontsheet'),
        ('printed minutes', 'printed-minutes'),
    ):
        if phrase in text:
            return doc_type
    return None


def slugify(text: str, max_length: int = 60) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug[:max_length].rstrip('-') or 'document'


def link_title(link) -> str:
    match = re.search(r"Link to document '(.+)' pdf file", unescape(link.get('title', '')))
    if match:
        return match.group(1)
    return Path(unquote(urlsplit(link['href']).path)).stem


def agenda_items_by_document(soup: BeautifulSoup) -> dict[str, tuple[str, str]]:
    """Map document URL paths to (agenda item number, agenda item title)."""
    items = {}
    for row in soup.find_all('tr'):
        number_cell = row.find('td', class_='mgItemNumberCell')
        if number_cell is None:
            continue
        number = number_cell.get_text(strip=True).rstrip('.')
        title_link = row.find('a', class_='mgAiTitleLnk')
        title_para = row.find_all('p', class_='mgAiTitleTxt')
        if title_link is not None:
            title = link_title(title_link)
        else:
            title = title_para[-1].get_text(' ', strip=True) if title_para else ''
        for link in row.find_all('a', href=re.compile(r'\.pdf', re.IGNORECASE)):
            items.setdefault(unquote(urlsplit(urljoin(BASE_URL, link['href'])).path), (number, title))
    return items


def document_filename(doc_type: str, url_path: str, title: str, item: str, counts: dict[str, int]) -> str:
    if doc_type != 'document':
        counts[doc_type] = counts.get(doc_type, 0) + 1
        suffix = '' if counts[doc_type] == 1 else f'-{counts[doc_type]}'
        return f'{doc_type}{suffix}.pdf'
    document_id = Path(url_path).parent.name
    match = re.match(r'(\d+)(.*)', item)
    prefix = f'{int(match.group(1)):02d}{match.group(2)}-' if match else (f'{item}-' if item else '')
    return f'{prefix}{document_id}-{slugify(title)}.pdf'


def find_documents(
    session: requests.Session, meeting: Meeting, include_supplementary: bool, include_documents: bool,
) -> list[Document]:
    # Some meetings only link the pack from the chooser page, others only from the meeting page.
    chooser_url = urljoin(BASE_URL, f'mgChooseDocPack.aspx?ID={meeting.meeting_id}')
    documents = []
    counts: dict[str, int] = {}
    seen_paths = set()
    for page_url in (chooser_url, meeting.url):
        try:
            html = fetch(session, page_url).text
        except requests.HTTPError as error:
            print(f'warning  {page_url}: {error}')
            continue
        soup = BeautifulSoup(html, 'html.parser')
        items = agenda_items_by_document(soup)
        for link in soup.find_all('a', href=re.compile(r'\.pdf', re.IGNORECASE)):
            url = urljoin(BASE_URL, link['href'])
            url_path = unquote(urlsplit(url).path)
            if url_path in seen_paths:
                continue
            title = link_title(link)
            doc_type = classify_pack(Path(url_path).name) or classify_pack(title) or 'document'
            if (doc_type == 'supplementary-pack' and not include_supplementary) or (
                    doc_type not in ('reports-pack', 'supplementary-pack') and not include_documents):
                continue
            seen_paths.add(url_path)
            item, item_title = items.get(url_path, ('', ''))
            filename = document_filename(doc_type, url_path, title, item, counts)
            documents.append(Document(
                meeting=meeting, doc_type=doc_type, url=url, path=f'{meeting.folder_name}/{filename}',
                title=title, item=item, item_title=item_title,
            ))
    return documents


def download(session: requests.Session, document: Document, folder: Path) -> Path:
    target = folder / document.path
    if target.exists() and target.stat().st_size > 0:
        print(f'exists   {display(target)}')
        return target
    response = fetch(session, document.url)
    if not response.content.startswith(b'%PDF'):
        raise ValueError(f'{document.url} did not return a PDF')
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.pdf.part')
    partial.write_bytes(response.content)
    partial.replace(target)
    print(f'saved    {display(target)} ({len(response.content) / 1e6:.1f} MB)')
    return target


def update_index(folder: Path, rows: list[dict[str, str]]) -> Path:
    index_path = folder / 'index.csv'
    existing: dict[str, dict[str, str]] = {}
    if index_path.exists():
        with index_path.open(newline='', encoding='utf-8') as handle:
            existing = {row['path']: row for row in csv.DictReader(handle) if row.get('path')}
    existing.update({row['path']: row for row in rows})
    with index_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(existing.values(), key=lambda row: row['path']))
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
    parser.add_argument(
        '--committee', choices=sorted(COMMITTEES), default='hhhwqp',
        help='Committee preset; sets the committee ID and col-pdfs/<name> folder (default: hhhwqp)',
    )
    parser.add_argument('--committee-id', type=int, help='Override the preset ModernGov committee ID')
    parser.add_argument('--folder', type=Path, help='Override the output folder')
    parser.add_argument(
        '--no-supplementary', dest='supplementary', action='store_false',
        help='Skip supplementary agenda packs (downloaded by default)',
    )
    parser.add_argument(
        '--no-documents', dest='documents', action='store_false',
        help='Skip the individual agenda documents (downloaded by default)',
    )
    parser.add_argument('--dry-run', action='store_true', help='List documents without downloading')
    args = parser.parse_args()

    years = parse_years(args.years)
    committee_id = args.committee_id or COMMITTEES[args.committee]
    folder = (args.folder or PDF_ROOT / args.committee).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'pond-col-downloader/1.0 (+https://github.com/hagrid67/pond)'

    meetings: dict[int, Meeting] = {}
    for year in years:
        for meeting in list_meetings(session, committee_id, year):
            if meeting.meeting_date.year in years and meeting.meeting_date <= date.today():
                meetings[meeting.meeting_id] = meeting

    rows = []
    failures = []
    for meeting in sorted(meetings.values(), key=lambda item: item.meeting_date):
        documents = find_documents(session, meeting, args.supplementary, args.documents)
        if not any(document.doc_type == 'reports-pack' for document in documents):
            print(f'no pack  {meeting.meeting_date} ({meeting.url})')
        for document in documents:
            if args.dry_run:
                print(f'would    {document.path} <- {document.url}')
                continue
            try:
                path = download(session, document, folder)
            except (requests.RequestException, ValueError) as error:
                print(f'FAILED   {document.path}: {error}', flush=True)
                failures.append(document.path)
                continue
            rows.append({
                'meeting_date': meeting.meeting_date.isoformat(),
                'meeting_id': str(meeting.meeting_id),
                'item': document.item,
                'item_title': document.item_title,
                'doc_type': document.doc_type,
                'title': document.title,
                'path': document.path,
                'size_bytes': str(path.stat().st_size),
                'url': document.url,
                'meeting_url': meeting.url,
            })
    if rows:
        print(f'index    {display(update_index(folder, rows))}')
    if failures:
        raise SystemExit(f'{len(failures)} download(s) failed; re-run to retry: {", ".join(failures)}')


if __name__ == '__main__':
    main()
