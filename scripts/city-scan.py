"""Scan downloaded City of London committee packs for topics such as budgets and swimming.

Page text is extracted with pypdf (layout mode) and cached under <folder>/text/.
Matches are reported per file and page, with the meeting date from index.csv.
"""

import argparse
import csv
import logging
import re
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOLDER = REPO_ROOT / 'col-pdfs' / 'hhhwqp'
PAGE_MARKER = re.compile(r'^=====PAGE (\d+)=====$', re.MULTILINE)
MONEY = r'(?:£\s?\d[\d,.]*\s?(?:m|k|million)?\b|\(?\d{1,3}(?:,\d{3})+\)?)'
TOPICS = {
    'budget': r'total net expenditure|actual to date|projected outturn|forecast outturn|latest budget'
              r'|original budget|revenue budget|budget movements|statement of financial activit',
    'outturn': r'outturn',
    'swimming': r'\blido\b|\bponds?\b|swimm|bathing|\bsauna\b',
    'swimming-money': rf'(?:\blido\b|\bponds?\b|swimm|bathing|\bsauna\b).*{MONEY}'
                      rf'|{MONEY}.*(?:\blido\b|\bponds?\b|swimm|bathing|\bsauna\b)',
    'staffing': r'lifeguard|\bstaff(?:ing)?\b|vacanc|\bFTE\b|recruit',
    'capital': r'capital (?:budget|programme|project|works)|cyclical works|\bCWP\b|project list',
}
AGENDA_ITEM = re.compile(r'^\s*(\d{1,2})\.\s+(\*?)\s*([A-Z][A-Z0-9 &,()\'’/.:-]{6,})$')


def load_pages(pdf: Path, cache_dir: Path) -> list[str]:
    cache = cache_dir / f'{pdf.stem}.txt'
    if not cache.exists() or cache.stat().st_mtime < pdf.stat().st_mtime:
        logging.getLogger('pypdf').setLevel(logging.ERROR)
        parts = []
        for number, page in enumerate(PdfReader(pdf).pages, start=1):
            try:
                text = page.extract_text(extraction_mode='layout') or ''
            except Exception as error:  # pypdf can fail on individual malformed pages
                text = f'<<text extraction failed: {error}>>'
            parts.append(f'=====PAGE {number}=====\n{text}')
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text('\n'.join(parts), encoding='utf-8')
    chunks = PAGE_MARKER.split(cache.read_text(encoding='utf-8'))[1:]
    return chunks[1::2]


def normalise(line: str) -> str:
    return re.sub(r'\s+', ' ', line).strip()


def meeting_dates(folder: Path) -> dict[str, str]:
    index = folder / 'index.csv'
    if not index.exists():
        return {}
    with index.open(newline='', encoding='utf-8') as handle:
        return {row['filename']: row['meeting_date'] for row in csv.DictReader(handle)}


def agenda_items(pages: list[str], max_pages: int = 6) -> list[tuple[int, bool, str]]:
    """Return (number, to_follow, title) from the agenda; '*' marks items to follow after the pack."""
    items: dict[int, tuple[int, bool, str]] = {}
    for text in pages[:max_pages]:
        for line in text.splitlines():
            match = AGENDA_ITEM.match(normalise(line))
            if match and int(match.group(1)) not in items:
                number = int(match.group(1))
                items[number] = (number, bool(match.group(2)), match.group(3).strip())
    return sorted(items.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=DEFAULT_FOLDER)
    parser.add_argument('--topic', nargs='+', choices=sorted(TOPICS), default=['budget', 'swimming-money'],
                        help='Topic regex presets to search for (default: budget swimming-money)')
    parser.add_argument('--pattern', action='append', default=[], help='Extra case-insensitive regex')
    parser.add_argument('--glob', default='*.pdf', help='PDF file glob within the folder')
    parser.add_argument('--agenda', action='store_true',
                        help='List agenda items, flagging "*" (to follow) items, which are often only in a '
                             'supplementary pack or published as a separate document')
    parser.add_argument('--show-pages', action='store_true', help='Print the full text of matching pages')
    parser.add_argument('--max-lines', type=int, default=3, help='Matching lines shown per page (default: 3)')
    parser.add_argument('--csv', type=Path, help='Write all matches to this CSV')
    args = parser.parse_args()

    patterns = {topic: TOPICS[topic] for topic in args.topic}
    patterns.update({f'custom{i}': pattern for i, pattern in enumerate(args.pattern, start=1)})
    compiled = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in patterns.items()}
    dates = meeting_dates(args.folder)
    rows = []
    for pdf in sorted(args.folder.glob(args.glob)):
        pages = load_pages(pdf, args.folder / 'text')
        print(f'== {pdf.name} (meeting {dates.get(pdf.name, "?")}, {len(pages)} pages)')
        if args.agenda:
            for number, to_follow, title in agenda_items(pages):
                print(f'   agenda {number:>2}. {title}{"  [* to follow]" if to_follow else ""}')
        for page_number, text in enumerate(pages, start=1):
            lines = [normalise(line) for line in text.splitlines() if line.strip()]
            matches = [(name, line) for line in lines for name, regex in compiled.items() if regex.search(line)]
            if not matches:
                continue
            topics = sorted({name for name, _ in matches})
            print(f'   p{page_number:<4} [{", ".join(topics)}] {len(matches)} lines')
            for _, line in matches[:args.max_lines]:
                print(f'          {line[:150]}')
            if args.show_pages:
                print(text)
            rows.extend({
                'filename': pdf.name, 'meeting_date': dates.get(pdf.name, ''), 'page': page_number,
                'topic': name, 'line': line,
            } for name, line in matches)
    if args.csv:
        with args.csv.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['filename', 'meeting_date', 'page', 'topic', 'line'])
            writer.writeheader()
            writer.writerows(rows)
        print(f'Wrote {len(rows)} matches to {args.csv}')


if __name__ == '__main__':
    main()
