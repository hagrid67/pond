# Scanning committee packs

[`scripts/city-scan.py`](../scripts/city-scan.py) searches the PDFs downloaded
by [`city-download.py`](city-download.md) for topics using regular expressions.
It doesn't call the website or an LLM, so results are repeatable.

```bash
# Budget tables and swimming-related money figures in all HHHWQP packs
./ve312pond/bin/python scripts/city-scan.py

# Agenda items (flagging "*" to-follow items) plus outturn mentions, main packs only
./ve312pond/bin/python scripts/city-scan.py --agenda --topic outturn --glob '*/reports-pack.pdf'

# Only the July 2026 outturn report and appendices
./ve312pond/bin/python scripts/city-scan.py --glob '2026-0714/10-*.pdf' --show-pages

# Include text read by OCR from images embedded in pages (tables pasted as pictures)
./ve312pond/bin/python scripts/city-scan.py --ocr --glob '2026-1027/12-*.pdf' --pattern 'charges for use of facilities'

# Custom regex, full page text of matches, and a CSV of every matching line
./ve312pond/bin/python scripts/city-scan.py --topic swimming --pattern 'sauna' --show-pages --csv /tmp/hits.csv
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--folder` | `col-pdfs/hhhwqp` | Folder of PDFs (and `index.csv` for meeting dates) |
| `--topic` | `budget swimming-money` | Presets: `budget`, `outturn`, `swimming`, `swimming-money`, `staffing`, `capital` |
| `--pattern` | — | Extra case-insensitive regex (repeatable) |
| `--glob` | `*/*.pdf` | Which PDFs to scan, relative to the folder (one sub-folder per meeting) |
| `--agenda` | off | List agenda items from the first pages, flagging `*` items |
| `--ocr [ENGINE]` | off | Also OCR embedded images; `tesseract` (default) or `rapidocr` |
| `--show-pages` | off | Print the full text of each matching page |
| `--max-lines` | `3` | Matching lines shown per page |
| `--csv` | — | Write every match (file, meeting date, page, topic, line) |

Page text is extracted once with pypdf's layout mode and cached in
`<folder>/text/<meeting>/<pdf-stem>.txt` (git-ignored). The cache is rebuilt when the PDF
is newer than the cached text. The first run over the 2026 packs takes about 30 s.
Layout mode keeps table columns aligned, e.g. page 147 of
`2026-0203/reports-pack.pdf`. Whitespace is collapsed before matching.

## OCR of image tables

Some reports paste tables in as images, e.g. the notes to the accounts in the
draft annual report (`2026-1027/12-s238631-…pdf`, p39). `--ocr` reads every
image embedded in a page that is at least 300×60 px (skipping icons and rules)
and appends the text to that page, under a `[OCR image N, engine]` heading. It
runs only on the images, not the whole rendered page. OCR results are cached
separately in `<folder>/text/<meeting>/<pdf-stem>.ocr-<engine>.txt`.

| Engine | Install | Notes |
| --- | --- | --- |
| `tesseract` (default) | `sudo apt install tesseract-ocr`; called as a command, no Python package | Fast (50-page report in ~8 s). Keeps `£` and `–` and lays out columns itself (`--psm 6`, `preserve_interword_spaces`). |
| `rapidocr` | `rapidocr-onnxruntime` (in `requirements.txt`) | No system install; ~4× slower. Reads `£` as `f` and drops `–`; lines are rebuilt from word boxes. |

On the p39 "Income from charitable activities" table, both engines read all 18
figures correctly; every column sums to its printed total. Some tables are not images but vector drawings (Windows metafiles pasted from
Excel, stored as PDF Form XObjects), e.g. the staff-cost notes in the annual
accounts. `--ocr` also renders every page that contains Form XObjects at 300 dpi
with `pypdfium2`, OCRs it, and appends the result under `[OCR page render, engine]`.
This is slower than reading images, so the first `--ocr` run over large packs
takes longer.

## Limits

- **Agenda `*` items:** these are "to follow" reports. They may appear only in a
  supplementary pack or as a separate document. `city-download.py` now fetches the
  separate documents too, so scan `*/*.pdf` rather than just the packs.
- **Text-free pages:** scanned images and charts have no extractable text and
  only match with `--ocr`. About 5–30% of pages in the 2026 packs are like
  this; photos, maps and charts give noisy OCR text.
- **What regex can't do:** it finds where something is mentioned. Pulling
  figures out of a table across years in different layouts, or summarising
  narrative, needs format-specific parsing or an LLM step.

## Findings: 2025/26 actual (outturn) for swimming income (2026 meetings)

- **3 Feb 2026, reports pack p147–148:** the Q3 projected outturn is the last
  table with a Lido/Ponds split: Lido £1.26m, Ponds £1.14m, and a note says
  combined income is "on a trajectory" for £2.4m. Budget: Lido £1.104m,
  Ponds £1.010m.
- **12 May 2026, p97:** "430,610 swims at the Bathing Ponds during the year
  2025/26". The pack contains no budget tables.
- **14 Jul 2026, item 10, Revenue Outturn 2025/26 (separate documents
  `s235511`–`s235513`):**
  - Totals only: local-risk gross income £4.243m against a budget of £3.627m.
  - Appendix 2 note 2: "(£313k) additional income in combined Lido and Ponds
    income due to an exceptional summer".
  - The final gross-income budget equals the original, so the swimming budget
    was still £2.114m, implying combined actual swimming income of about
    **£2.43m** (inferred, not stated).
  - On costs: "£266k additional recruitment costs of seasonal lifeguards".
  - Overall net expenditure was £8.246m, £93k over the final budget.
  - From 2026/27, reports use a charity-style (SOFA) format.
- **27 Oct 2026, item 11, Finance Progress Report 2026/27:** "£100k additional
  income in combined Lido and Ponds income is on a trajectory that indicates
  £2.4m income". Again there is no Lido/Ponds split.
- **27 Oct 2026, item 12, Draft Annual Report 2025/26, p21:** income from fees
  charged £4,205,726 (2024/25: £3,591,317). The note-3 income table on p39 has
  no extractable text.
