import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'city-scan.py'
spec = importlib.util.spec_from_file_location('city_scan', SCRIPT)
city_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(city_scan)


def test_agenda_items_flag_to_follow_items() -> None:
    page = '\n'.join([
        '   9.     ASSISTANT DIRECTOR\'S REPORT',
        '          Report of the Executive Director',
        '  10.     *HAMPSTEAD HEATH 2025/26 OUTTURN',
        '  11.     For Decision',
    ])
    assert city_scan.agenda_items([page]) == [
        (9, False, "ASSISTANT DIRECTOR'S REPORT"),
        (10, True, 'HAMPSTEAD HEATH 2025/26 OUTTURN'),
    ]


def test_load_pages_appends_ocr_of_embedded_images(tmp_path, monkeypatch) -> None:
    from PIL import Image

    folder = tmp_path / 'committee'
    pdf = folder / '2026-1027' / 'report.pdf'
    pdf.parent.mkdir(parents=True)
    Image.new('RGB', (400, 100), 'white').save(pdf)
    monkeypatch.setattr(city_scan, 'ocr_tesseract', lambda image: '  Charges for use of facilities  3,983,234\n')

    pages = city_scan.load_pages(pdf, folder, 'tesseract')

    assert len(pages) == 1
    assert '[OCR image 1, tesseract]\n  Charges for use of facilities  3,983,234' in pages[0]
    assert 'OCR' not in city_scan.load_pages(pdf, folder)[0]


def test_csv_rows_record_file_and_meeting_date(tmp_path, monkeypatch) -> None:
    import csv
    import sys

    from PIL import Image

    folder = tmp_path / 'committee'
    pdf = folder / '2026-1027' / 'report.pdf'
    pdf.parent.mkdir(parents=True)
    Image.new('RGB', (400, 100), 'white').save(pdf)
    (folder / 'index.csv').write_text('path,meeting_date\n2026-1027/report.pdf,2026-10-27\n', encoding='utf-8')
    monkeypatch.setattr(city_scan, 'ocr_tesseract', lambda image: 'Lido income £1,260,000')
    monkeypatch.setattr(city_scan.shutil, 'which', lambda name: '/usr/bin/tesseract')
    output = tmp_path / 'hits.csv'
    monkeypatch.setattr(sys, 'argv', ['city-scan', '--folder', str(folder), '--ocr', '--topic',
                                      'swimming-money', '--csv', str(output)])

    city_scan.main()

    with output.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    assert [(row['filename'], row['meeting_date'], row['topic']) for row in rows] == [
        ('2026-1027/report.pdf', '2026-10-27', 'swimming-money'),
    ]
