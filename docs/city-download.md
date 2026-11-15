# City of London committee papers downloader

[`scripts/city-download.py`](../scripts/city-download.py) downloads the agenda
"reports packs" for a City of London committee from the Corporation's ModernGov
archive at <https://democracy.cityoflondon.gov.uk/>. A reports pack is a single
PDF containing the agenda and all public reports and appendices for a meeting
concatenated together (the February budget meeting pack is ~10 MB / ~270 pages).

The default committee is the **Hampstead Heath, Highgate Wood and Queen's Park
Committee** (ModernGov `CommitteeId=250`, abbreviated HHHWQP).

## Usage

```bash
# All 2026 HHHWQP meetings (default: current year)
./ve312pond/bin/python scripts/city-download.py --years 2026

# A range of years for the Finance Committee, into col-pdfs/finance
./ve312pond/bin/python scripts/city-download.py --committee finance --years 2023-2026

# Show what would be fetched without downloading
./ve312pond/bin/python scripts/city-download.py --years 2025 --dry-run
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--years` | current year | One or more years or `START-END` ranges |
| `--committee` | `hhhwqp` | Committee preset (sets ID and `col-pdfs/<name>` folder) |
| `--committee-id` | from preset | Override the ModernGov committee ID |
| `--folder` | `col-pdfs/<committee>` | Override the output folder |
| `--no-supplementary` | off | Skip supplementary agenda packs (fetched by default) |
| `--dry-run` | off | List packs without downloading |

| Preset | ID | Committee |
| --- | --- | --- |
| `hhhwqp` | 250 | Hampstead Heath, Highgate Wood and Queen's Park Committee |
| `hhcc` | 261 | Hampstead Heath Consultative Committee |
| `finance` | 145 | Finance Committee |
| `ras` | 396 | Resource Allocation Sub (Policy and Resources) Committee |

Other IDs are shown in the `mgCommitteeDetails.aspx?ID=...` links on the
[committee list](https://democracy.cityoflondon.gov.uk/mgListCommittees.aspx).

## How it works

1. `ieListMeetings.aspx?CommitteeId=250&Year=YYYY` lists meetings. Each year's
   page also shows neighbouring years, so meetings are filtered by date and
   de-duplicated by meeting ID (`MId`). Future meetings are skipped.
2. `mgChooseDocPack.aspx?ID=<MId>` and the meeting page are both scanned for PDF
   links, because some meetings only link the pack from one of them. A PDF whose
   file name (or link text) contains "reports pack" is the main pack; one
   containing "supplementary" and "pack" is a supplementary pack. Links are
   de-duplicated by path, ignoring the `?T=` query. If the chooser page returns an
   error (it 404s for some meetings), a warning is printed and only the meeting
   page is used.
3. Each pack is saved as `YYYY-MMDD-reports-pack.pdf` or
   `YYYY-MMDD-supplementary-pack.pdf` (a `-2`, `-3` suffix is added if a meeting
   has several of the same type). Existing non-empty files are not downloaded
   again; downloads are written to a `.part` file and renamed once complete, and
   must start with the `%PDF` signature.
4. `index.csv` in the output folder is merged (keyed by filename) with the rows
   from this run, so running different years accumulates a single index.

Requests are made sequentially with a one-second pause to be polite to the server.

## Index columns

| Column | Meaning |
| --- | --- |
| `meeting_date` | ISO meeting date |
| `meeting_id` | ModernGov `MId` |
| `pack_type` | `reports-pack` or `supplementary-pack` |
| `filename` | Local file name in the output folder |
| `size_bytes` | Local file size |
| `url` | Source PDF URL |
| `meeting_url` | Meeting page listing the individual documents |

## Notes

- The packs are large and are not committed to git (`col-pdfs/*/*.pdf` is
  ignored); `index.csv` is committed so the archive can be re-created.
- Individual reports are also available separately from the meeting page
  (`documents/s<id>/...pdf`); only the concatenated packs are downloaded.
- Page text can be extracted with pypdf, e.g.
  `PdfReader(path).pages[146].extract_text(extraction_mode='layout')` gives a
  well-aligned copy of the Hampstead Heath operating budget table on page 147 of
  `2026-0203-reports-pack.pdf`.
