"""Extract page-numbered text from a downloaded fee schedule PDF."""

import argparse
from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return '\n\n'.join(
        f'PAGE {number}\n{page.extract_text(extraction_mode="layout")}'
        for number, page in enumerate(reader.pages, start=1)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path, help='Path to a downloaded PDF')
    parser.add_argument('--output', type=Path, help='Write UTF-8 text to this file')
    args = parser.parse_args()
    text = extract_pdf_text(args.pdf)
    if args.output is None:
        print(text)
    else:
        args.output.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
