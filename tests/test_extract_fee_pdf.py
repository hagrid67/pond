import subprocess
import sys
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure


def test_extract_fee_pdf_stdout_and_output_file(tmp_path: Path) -> None:
    pdf_path = tmp_path / 'fees.pdf'
    with PdfPages(pdf_path) as pdf:
        for text in ('Ponds 12 Month Season Ticket', 'Adult 125.00'):
            figure = Figure()
            figure.text(0.1, 0.5, text)
            pdf.savefig(figure)

    script = Path(__file__).resolve().parents[1] / 'scripts' / 'extract-fee-pdf.py'
    result = subprocess.run(
        [sys.executable, str(script), str(pdf_path)],
        check=True, capture_output=True, text=True,
    )
    assert 'PAGE 1\n' in result.stdout
    assert 'Ponds 12 Month Season Ticket' in result.stdout
    assert 'PAGE 2\n' in result.stdout
    assert 'Adult 125.00' in result.stdout

    output_path = tmp_path / 'fees.txt'
    result_file = subprocess.run(
        [sys.executable, str(script), str(pdf_path), '--output', str(output_path)],
        check=True, capture_output=True, text=True,
    )
    assert not result_file.stdout
    assert output_path.read_text(encoding='utf-8') == result.stdout.rstrip('\n')
