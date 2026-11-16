# Scanning committee packs

[`scripts/city-scan.py`](../scripts/city-scan.py) searches the PDFs downloaded
by [`city-download.py`](city-download.md) for topics using regular expressions.
It doesn't call the website or an LLM, so results are repeatable.

```bash
# Budget tables and swimming-related money figures in all HHHWQP packs
./ve312pond/bin/python scripts/city-scan.py

# Agenda items (flagging "*" to-follow items) plus outturn mentions, main packs only
./ve312pond/bin/python scripts/city-scan.py --agenda --topic outturn --glob '*reports-pack.pdf'

# Custom regex, full page text of matches, and a CSV of every matching line
./ve312pond/bin/python scripts/city-scan.py --topic swimming --pattern 'sauna' --show-pages --csv /tmp/hits.csv
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--folder` | `col-pdfs/hhhwqp` | Folder of PDFs (and `index.csv` for meeting dates) |
| `--topic` | `budget swimming-money` | Presets: `budget`, `outturn`, `swimming`, `swimming-money`, `staffing`, `capital` |
| `--pattern` | — | Extra case-insensitive regex (repeatable) |
| `--glob` | `*.pdf` | Which PDFs to scan |
| `--agenda` | off | List agenda items from the first pages, flagging `*` items |
| `--show-pages` | off | Print the full text of each matching page |
| `--max-lines` | `3` | Matching lines shown per page |
| `--csv` | — | Write every match (file, meeting date, page, topic, line) |

Page text is extracted once with pypdf's layout mode and cached in
`<folder>/text/<pdf-stem>.txt` (git-ignored). The cache is rebuilt when the PDF
is newer than the cached text. The first run over the 2026 packs takes about 30 s.
Layout mode keeps table columns aligned, e.g. page 147 of
`2026-0203-reports-pack.pdf`. Whitespace is collapsed before matching.

## Limits

- **Agenda `*` items:** these are "to follow" reports. They may appear only in a
  supplementary pack, or only as a separate document on the meeting page, which
  `city-download.py` doesn't currently fetch.
- **Text-free pages:** scanned images and charts have no extractable text, so
  they can't match. About 5–30% of pages in the 2026 packs are like this.
- **What regex can't do:** it finds where something is mentioned. Pulling
  figures out of a table across years in different layouts, or summarising
  narrative, needs format-specific parsing or an LLM step.

## Findings: 2025/26 actual (outturn) for swimming income (2026 packs)

- **3 Feb 2026, p147–148:** the Q3 projected outturn is the latest table with a
  Lido/Ponds split: Lido £1.26m, Ponds £1.14m, and a note says combined income
  is "on a trajectory" for £2.4m. Page 160 (2026/27 budget) mentions a
  "£185k increase in Swimming and sporting income".
- **12 May 2026, p97:** "430,610 swims at the Bathing Ponds during the year
  2025/26". The pack contains no budget tables.
- **14 Jul 2026, item 10 "*Hampstead Heath 2025/26 Outturn":** not in the
  main or supplementary pack. The minutes (in the 27 Oct pack, p13) only say
  the Committee "noted the report".
- **27 Oct 2026, items 11–12:** Finance Progress Report 2026/27 and Draft
  Annual & Financial Statements 2025/26 are both `*` items and not in the pack.
