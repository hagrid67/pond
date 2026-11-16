"""Scan downloaded City of London committee packs for topics such as budgets and swimming.

Page text is extracted with pypdf (layout mode) and cached under <folder>/text/.
With --ocr, images embedded in each page (e.g. tables pasted as pictures) are also
read with Tesseract or RapidOCR, and the result is cached and searched as well.
Matches are reported per file and page, with the meeting date from index.csv.
"""

import argparse
import csv
import io
import logging
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image
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
OCR_ENGINES = ('tesseract', 'rapidocr')
# Skip icons, logos and rules; tables and charts are larger than this.
MIN_OCR_WIDTH, MIN_OCR_HEIGHT = 300, 60
AGENDA_ITEM = re.compile(r'^\s*(\d{1,2})\.\s+(\*?)\s*([A-Z][A-Z0-9 &,()\'’/.:-]{6,})$')


def write_pages(cache: Path, pages: list[str]) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        '\n'.join(f'=====PAGE {number}=====\n{text}' for number, text in enumerate(pages, start=1)),
        encoding='utf-8',
    )


def read_pages(cache: Path) -> list[str]:
    chunks = PAGE_MARKER.split(cache.read_text(encoding='utf-8'))[1:]
    return chunks[1::2]


def is_stale(cache: Path, pdf: Path) -> bool:
    return not cache.exists() or cache.stat().st_mtime < pdf.stat().st_mtime


def extract_text_pages(pdf: Path) -> list[str]:
    pages = []
    for page in PdfReader(pdf).pages:
        try:
            pages.append(page.extract_text(extraction_mode='layout') or '')
        except Exception as error:  # pypdf can fail on individual malformed pages
            pages.append(f'<<text extraction failed: {error}>>')
    return pages


def ocr_tesseract(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    # psm 6 treats the image as one block; preserving spaces keeps table columns apart.
    result = subprocess.run(
        ['tesseract', 'stdin', 'stdout', '--psm', '6', '-c', 'preserve_interword_spaces=1'],
        input=buffer.getvalue(), capture_output=True, check=True,
    )
    return result.stdout.decode('utf-8')


_rapidocr = None


def ocr_rapidocr(image: Image.Image) -> str:
    """Run RapidOCR and rebuild lines from word boxes, spacing words by their x position."""
    global _rapidocr
    if _rapidocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr = RapidOCR()
    import numpy as np
    result, _ = _rapidocr(np.array(image))
    if not result:
        return ''
    words = []
    for box, text, _score in result:
        xs, ys = [point[0] for point in box], [point[1] for point in box]
        words.append((min(xs), (min(ys) + max(ys)) / 2, max(ys) - min(ys), text))
    height = sorted(word[2] for word in words)[len(words) // 2]
    char_width = height * 0.55
    lines: list[list[tuple]] = []
    for word in sorted(words, key=lambda item: item[1]):
        if lines and abs(word[1] - lines[-1][0][1]) < height / 2:
            lines[-1].append(word)
        else:
            lines.append([word])
    out = []
    for line in lines:
        text = ''
        for x, _y, _h, word in sorted(line):
            column = int(x / char_width)
            text += ' ' * max(1 if text else 0, column - len(text)) + word
        out.append(text)
    return '\n'.join(out)


def ocr_page_images(page, engine: str) -> str:
    texts = []
    for number, embedded in enumerate(page.images, start=1):
        try:
            image = embedded.image
        except Exception:  # unsupported image encodings are skipped
            continue
        if image.width < MIN_OCR_WIDTH or image.height < MIN_OCR_HEIGHT:
            continue
        image = image.convert('RGB')
        text = (ocr_tesseract if engine == 'tesseract' else ocr_rapidocr)(image).strip('\n').rstrip()
        if text.strip():
            texts.append(f'[OCR image {number}, {engine}]\n{text}')
    return '\n\n'.join(texts)


def extract_ocr_pages(pdf: Path, engine: str) -> list[str]:
    pages = []
    for page in PdfReader(pdf).pages:
        try:
            pages.append(ocr_page_images(page, engine))
        except Exception as error:
            pages.append(f'<<OCR failed: {error}>>')
    return pages


def load_pages(pdf: Path, folder: Path, ocr: str | None = None) -> list[str]:
    """Return page texts, with OCR of embedded images appended when an engine is given."""
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    base = folder / 'text' / pdf.relative_to(folder)
    cache = base.with_suffix('.txt')
    if is_stale(cache, pdf):
        write_pages(cache, extract_text_pages(pdf))
    pages = read_pages(cache)
    if ocr is None:
        return pages
    ocr_cache = base.with_suffix(f'.ocr-{ocr}.txt')
    if is_stale(ocr_cache, pdf):
        print(f'   ocr    {pdf.relative_to(folder).as_posix()} ({ocr})', flush=True)
        write_pages(ocr_cache, extract_ocr_pages(pdf, ocr))
    return [f'{text}\n{extra}' if extra.strip() else text for text, extra in zip(pages, read_pages(ocr_cache))]


def normalise(line: str) -> str:
    return re.sub(r'\s+', ' ', line).strip()


def meeting_dates(folder: Path) -> dict[str, str]:
    index = folder / 'index.csv'
    if not index.exists():
        return {}
    with index.open(newline='', encoding='utf-8') as handle:
        return {row['path']: row['meeting_date'] for row in csv.DictReader(handle) if row.get('path')}


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
    parser.add_argument('--glob', default='*/*.pdf',
                        help="PDF glob within the folder, e.g. '2026-07*/*.pdf' or '*/reports-pack.pdf' "
                             "(default: '*/*.pdf')")
    parser.add_argument('--agenda', action='store_true',
                        help='List agenda items, flagging "*" (to follow) items, which are often only in a '
                             'supplementary pack or published as a separate document')
    parser.add_argument('--ocr', nargs='?', const='tesseract', choices=OCR_ENGINES,
                        help='Also OCR images embedded in pages (default engine: tesseract; or rapidocr). '
                             'Slow on first run; results are cached')
    parser.add_argument('--show-pages', action='store_true', help='Print the full text of matching pages')
    parser.add_argument('--max-lines', type=int, default=3, help='Matching lines shown per page (default: 3)')
    parser.add_argument('--csv', type=Path, help='Write all matches to this CSV')
    args = parser.parse_args()
    if args.ocr == 'tesseract' and shutil.which('tesseract') is None:
        parser.error('tesseract not found; install it (sudo apt install tesseract-ocr) or use --ocr rapidocr')

    patterns = {topic: TOPICS[topic] for topic in args.topic}
    patterns.update({f'custom{i}': pattern for i, pattern in enumerate(args.pattern, start=1)})
    compiled = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in patterns.items()}
    dates = meeting_dates(args.folder)
    rows = []
    for pdf in sorted(path for path in args.folder.glob(args.glob) if 'text' not in path.parts):
        name = pdf.relative_to(args.folder).as_posix()
        pages = load_pages(pdf, args.folder, args.ocr)
        print(f'== {name} (meeting {dates.get(name, "?")}, {len(pages)} pages)')
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
                'filename': name, 'meeting_date': dates.get(name, ''), 'page': page_number,
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
