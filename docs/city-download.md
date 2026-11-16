# City of London committee papers downloader

[`scripts/city-download.py`](../scripts/city-download.py) downloads committee
papers from the City of London Corporation's ModernGov archive at
<https://democracy.cityoflondon.gov.uk/>. For each meeting it downloads:

- the **reports pack**: one PDF containing the agenda and all public reports and
  appendices published with it (the February budget pack is ~10 MB / ~270 pages);
- any **supplementary** and **information packs**;
- the **individual agenda documents**, including reports marked `*` ("to
  follow"), which are often published only as separate documents and never
  appear in a pack (e.g. the July 2026 "Hampstead Heath 2025/26 Outturn").

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
| `--no-documents` | off | Only fetch the reports and supplementary packs |
| `--dry-run` | off | List documents without downloading |

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
   links, because some meetings only link the pack from one of them. If the
   chooser page returns an error (it 404s for some meetings), a warning is
   printed and only the meeting page is used. Links are de-duplicated by path,
   ignoring the `?T=` query.
3. On the meeting page each agenda row (`td.mgItemNumberCell`) gives the item
   number and title for the documents linked within it.
4. Files are saved in a folder per meeting, e.g. `col-pdfs/hhhwqp/2026-0714/`:

   | File | Source |
   | --- | --- |
   | `reports-pack.pdf`, `supplementary-pack.pdf`, `information-pack.pdf` | Packs (`-2`, `-3` suffix if repeated) |
   | `agenda-frontsheet.pdf`, `printed-minutes.pdf` | Meeting-level documents |
   | `10-s235511-hampstead-heath-2025-26-outturn.pdf` | Agenda item `10`, document `s235511`, slug of its title |
   | `03a-s235500-…pdf` | Sub-items keep their letter/roman suffix |

   Existing non-empty files are not downloaded again. Downloads are written to a
   `.part` file, renamed when complete, and must start with the `%PDF` signature.
5. `index.csv` in the committee folder is merged (keyed by `path`) with the rows
   from this run, so running different years accumulates a single index.

Requests are made sequentially with a one-second pause to be polite to the server.
The server sometimes returns gateway errors (502/504). Timeouts, connection errors and
HTTP 429/500/502/503/504 are retried after 10, 30 and 90 seconds. A document that
still fails is reported as `FAILED` and skipped. The index is still written, and the
script exits non-zero listing the failures; re-running fetches only the missing files.

## Index columns

| Column | Meaning |
| --- | --- |
| `meeting_date` | ISO meeting date |
| `meeting_id` | ModernGov `MId` |
| `item` | Agenda item number (blank for packs and meeting-level files) |
| `item_title` | Agenda item title (a leading `*` means "to follow") |
| `doc_type` | `reports-pack`, `supplementary-pack`, `information-pack`, `agenda-frontsheet`, `printed-minutes` or `document` |
| `title` | Document title from the link |
| `path` | Path relative to the committee folder, e.g. `2026-0714/reports-pack.pdf` |
| `size_bytes` | Local file size |
| `url` | Source PDF URL |
| `meeting_url` | Meeting page listing the individual documents |

## Notes

- The PDFs are not committed to git (`col-pdfs/*/**/*.pdf` is ignored). The 2026
  HHHWQP meetings come to 165 files, 188 MB. `index.csv` is committed so the
  archive can be re-created.
- Individual documents duplicate most of the pack contents, but are easier to cite
  and include the "to follow" reports the packs lack.
- Search the downloaded files with [`city-scan.py`](city-scan.md).
