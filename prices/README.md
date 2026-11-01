# Bathing ponds and Lido fee data

- `pond-fees.csv` stores the adult and concession PAYG and 12-month season-ticket
  prices used by `scripts/price-chart.py`. Each year is the April price/index
  comparison point; the 2027 and 2028 rows are proposed, not an observed tariff.
- `lido-fees.csv` stores the Parliament Hill Lido adult and concession off-peak
  PAYG, peak PAYG, 1-month / rolling monthly season, 6-month season, and
  12-month season ticket prices from 2005 to 2028 with official City of London
  schedule URLs and approval provenance.
- `proposals-2026.csv` extracts the summary table of current (2026/27) and
  proposed (2027–28) charges across Lido, Ponds, and Combined passes from page 5
  of `../col-pdfs/Swim-Forum-slides-2026.pdf`.

## Verification and provenance

The `status` column describes the evidence for each row:

- `official_verified`: all four prices checked against City of London fee
  schedules. `source_url` links to the PDF and page containing the tariff.
  `effective_from` is the official effective date (typically 1 April).
- `historical_assumption`: for 2005-2010, the earliest verified (2011) prices
  are extended backwards: GBP 110 adult / GBP 55 concession for annual tickets,
  and GBP 2 / GBP 1 for PAYG. The 2019 row retains the supplied 2018/19 prices.
  Neither extrapolation is independently verified.
- `historical`: later values supplied for the original chart, not independently
  audited against official schedules in this research.
- `proposed`: supplied future prices, not an enacted tariff.

Official schedules checked on 25 October 2026 establish:

| Effective from | Adult PAYG | Concession PAYG | Adult 12 months | Concession 12 months |
| --- | ---: | ---: | ---: | ---: |
| 1 April 2011 | GBP 2.00 | GBP 1.00 | GBP 110.00 | GBP 55.00 |
| 1 April 2012 | GBP 2.00 | GBP 1.00 | GBP 115.00 | GBP 60.00 |
| 1 April 2013 | GBP 2.00 | GBP 1.00 | GBP 118.50 | GBP 62.00 |
| 1 April 2014 | GBP 2.00 | GBP 1.00 | GBP 121.50 | GBP 63.50 |
| 1 April 2015-2018 (each year) | GBP 2.00 | GBP 1.00 | GBP 125.00 | GBP 66.00 |

The records distinguish **Natural Ponds** annual/12-month tickets from the
Lido, combined-facility passes, and six-month tickets:

- [2013/14 schedule, page 3](https://democracy.cityoflondon.gov.uk/documents/s12879/Appendix%201.pdf#page=3):
  the 2011 and 2012 columns are marked approved.
- [2015/16 schedule, page 3](https://democracy.cityoflondon.gov.uk/documents/s43964/Appendix%201%20Fees%20and%20charges%202014-2015%20FINAL.pdf#page=3):
  the 2013 and 2014 columns are marked approved. Despite the filename, the
  proposed column is explicitly for 1 April 2015.
- [2018/19 schedule, pages 4-5](https://democracy.cityoflondon.gov.uk/documents/s86980/Appendix%201%20Fees%20and%20charges%202018-2019%20HH-HW-QP.pdf#page=5):
  approved columns for 2015, 2016, and 2017, with proposed 2018 prices.
  Adult PAYG is on page 4; the other prices and column headings are on page 5.
  The [15 November 2017 committee minutes, item 5](https://democracy.cityoflondon.gov.uk/mgAi.aspx?ID=66661)
  record approval of the proposed 2018/19 charges; this is recorded in
  `approval_url` for 2018.

Blank provenance fields mean no official source has yet been recorded, not
that the price has been verified elsewhere. In particular, **the 2005
season-ticket price remains unverified**. The chart's default `START_YEAR`
is currently 2011, so those earlier assumptions are not plotted by default. Both
season-ticket inflation lines are rebased to the verified price in the chosen
base year, using its April indices.

Copies of the research PDFs are preserved in [`../col-pdfs/`](../col-pdfs/).
Its [`index.csv`](../col-pdfs/index.csv) maps local filenames to original URLs.
Save future CoL PDF downloads there too, retaining the CoL document ID in the
filename and adding an index entry.

## Reproducing PDF extraction

The shared environment includes `pypdf`, pinned in `requirements.txt`.
Download a source PDF and extract page-numbered layout text from the repository
root:

```bash
./ve312pond/bin/python scripts/extract-fee-pdf.py col-pdfs/2013-14-fees-appendix-s12879.pdf --output /tmp/pond-fees-2013.txt
```

Omit `--output` to print the text. Extraction does not interpret tariff columns
or update the CSV automatically: check the year headings and annual-ticket
rows against the PDF before entering prices.

## Comparison month

City of London fee schedules take effect at the start of the Corporation's
financial year in April (`1 April` in the 2011–2025 schedules, and `8 April
2026` in the 2026/27 Report of Action Taken). The annual chart therefore aligns
each year's prices and inflation index baseline with April.
