"""Extract Cyclical Works Programme (CWP) project lists for Hampstead Heath to finance/cwp.csv.

Reads the cached page text from city-scan.py (col-pdfs/hhhwqp/text/...) for each list below.
Long entries wrap onto following lines; a wrapped cell is assigned to the property (left
column) or the project title by its horizontal position. Section totals are checked against
the published totals.
"""

import argparse
import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = REPO_ROOT / 'col-pdfs' / 'hhhwqp' / 'text'
DEFAULT_OUTPUT = REPO_ROOT / 'finance' / 'cwp.csv'
# (fiscal year, list name, committee date, source PDF relative to col-pdfs/hhhwqp, published totals by list)
LISTS = (
    ('2020/21', 'actual_list', '2019-09-11',
     '2019-0911/12-s120746-appendix-a-hampstead-heath-management-committee.pdf', {'actual_list': 778_200}),
    ('2021/22', 'deferred_list', '2021-02-24',
     '2021-0224/11-s148032-appendix-a-hampstead-heath-highgate-wood-and-queens-park-com.pdf',
     {'deferred_list': 187_300, 'reserve_list': 2_008_000}),
    ('2026/27', 'project_list', '2026-02-03',
     '2026-0203/12-s228675-appendix-3-hh-cwp-2627-project-list.pdf', {'project_list': 1_510_000}),
)
COST = re.compile(r'^£?(\d{1,3}(?:,\d{3})*|0)$')
SKIP_FIRST_CELLS = {'Property', 'Building', 'Project Name'}
# Wrapped cells starting left of this column belong to the property name.
PROPERTY_COLUMN_END = 16


def cells_with_positions(line: str) -> list[tuple[int, str]]:
    return [(match.start(), match.group().strip(' |'))
            for match in re.finditer(r'\S+(?: \S+)*', line) if match.group().strip(' |')]


def parse_list(year: str, list_name: str, report_date: str, source: str) -> list[dict]:
    text = (TEXT_DIR / source).with_suffix('.txt').read_text(encoding='utf-8')
    chunks = re.split(r'=====PAGE (\d+)=====\n', text)[1:]
    rows: list[dict] = []
    current = None
    section = list_name
    for page, body in zip(chunks[::2], chunks[1::2]):
        for raw in body.splitlines():
            if not raw.strip():
                continue
            if raw.strip().startswith('Reserve List'):
                section, current = 'reserve_list', None
                continue
            # The 2026/27 list sometimes runs the cost into the title.
            line = re.sub(r'([A-Z)])(\d{1,3},\d{3})\s*$', r'\1  \2', raw)
            cells = cells_with_positions(line)
            values = [value for _, value in cells]
            if (values[0] in SKIP_FIRST_CELLS or 'Total' in values or 'Appendix' in line
                    or line.strip().startswith('CWP ') or values[0].startswith('£')):
                current = None
                continue
            if len(values) >= 2 and COST.match(values[-1]):
                current = {'parts': values[:-1], 'value': int(values[-1].strip('£').replace(',', '')),
                           'page': page, 'list': section}
                rows.append(current)
            elif current is not None and len(values) <= 2:
                for position, value in cells:
                    index = 0 if position < PROPERTY_COLUMN_END and len(current['parts']) > 1 else -1
                    current['parts'][index] += ' ' + value
            else:
                current = None
    return [{
        'fiscal_year': year, 'list': row['list'], 'item': ' - '.join(row['parts']), 'value_gbp': row['value'],
        'report_date': report_date, 'source': source, 'page': row['page'],
    } for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = []
    for year, list_name, report_date, source, totals in LISTS:
        parsed = parse_list(year, list_name, report_date, source)
        for name, expected in totals.items():
            actual = sum(row['value_gbp'] for row in parsed if row['list'] == name)
            if actual != expected:
                raise SystemExit(f'{year} {name}: parsed £{actual:,} but the list totals £{expected:,}')
        rows += parsed
        print(f'{year}: {len(parsed)} items, totals match {totals}')
    with args.output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote {len(rows)} rows to {args.output}')


if __name__ == '__main__':
    main()
