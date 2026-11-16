# Swimming finance data (Hampstead Heath Ponds and Lido)

Figures transcribed from Hampstead Heath, Highgate Wood and Queen's Park Committee
papers, 2019–2026. The PDFs are downloaded with
[`city-download.py`](../docs/city-download.md) and searched with
[`city-scan.py`](../docs/city-scan.md). Every row cites its source PDF (`source`,
relative to `col-pdfs/hhhwqp/`; `index.csv` there gives the URL) and page. Values
are whole pounds and positive (income is not shown in brackets). Fiscal years run
April–March.

| File | Contents |
| --- | --- |
| `swimming-income.csv` | Lido and Ponds income: budgets, actual to date, projected outturns, actuals, and annual review figures, one row per figure per report |
| `swimming-costs.csv` | Per-facility employee, operational and total costs and subsidy (annual reviews 2018/19–2022/23), plus later cost variances |
| `swimming-capital.csv` | Capital projects: Swimming Facilities Safety, Access & Security Improvements, and Lido photovoltaic panels |
| `swimming-maintenance.csv` | Cyclical Works Programme (CWP) items for Lido and bathing pond buildings, and maintenance cited in outturn reports |

[commentary.md](commentary.md) has working notes: summary tables, hypotheses
about the contradictions, and the planned set of charts.

## `swimming-income.csv` figures

| `figure` | Meaning |
| --- | --- |
| `latest_budget` | Latest approved budget in a quarterly revenue report |
| `actual_to_date` | Year-to-date actual at that report (period given in `note`) |
| `projected_outturn` | Year-end forecast at that report |
| `actual` | Prior-year actual, as restated in a later revenue report |
| `annual_review_actual` | Income in the annual Bathing Ponds and Lido review, net of booking fees and VAT |
| `outturn_derived` | Calculated from a stated budget and variance, not stated directly |
| `budget_change` | Stated change to next year's budget |

`facility` is `lido`, `ponds` or `ponds+lido` (combined figure only).

## Known contradictions and gaps

- **2022/23 split:** the annual review gives Ponds £823,352 and Lido £684,548.
  The later revenue reports give actuals of Ponds £176,043 and Lido £1,341,174.
  The totals agree within £10k, but the split doesn't. The Ponds "actual" equals the
  P9 actual-to-date, and the P9 report notes that some Lido income "could relate to
  Ponds".
- **2024/25 Ponds:** the April–December actual to date was £786,353, but the
  restated full-year actual is £214,726. This again suggests income was reallocated
  between lines.
- **2025/26 Lido budget:** the budget estimates add £100k to the £850k 2024/25 budget,
  but the 2025/26 budget is £1,104,000.
- **Format change:** after Q3 2025/26 (Feb 2026), reports give only a combined
  Lido + Ponds figure. From 2026/27, swimming sits inside "Trading" in the charity
  (SOFA) format.
- **Missing years:** no per-facility income or costs were found for 2019/20. The
  annual reviews with staff and running costs stop after 2022/23.
- **Capital project:** budget figures between Feb 2023 (£775,705 estimated cost)
  and Oct 2025 (£1,010,654) weren't found in these committee papers. The increase
  was presumably approved elsewhere (for example a Projects Sub-Committee).
  The 2025 and 2026 capital figures come from OCR of image tables.
