# Commentary on swimming finances (working notes)

Working notes on the figures in this folder, written when the CSVs were first
compiled (Nov 2026). They record interpretations and hypotheses to revisit while
refining the charts. Figures are in £k unless stated; sources are in the CSVs.

## Income summary

| Year | Ponds | Lido | Combined | Notes |
| --- | ---: | ---: | ---: | --- |
| 2018/19 | 67 | 377 | 444 | Swimming Review 2020 position paper |
| 2019/20 | – | – | – | Not found |
| 2020/21 | 368 | 173 | 541 | Covid closures |
| 2021/22 | 677 | 455 | 1,132 | Annual review |
| 2022/23 | 823 / 176 | 685 / 1,341 | 1,508 / 1,517 | Annual review / later revenue-report actual |
| 2023/24 | 738 | 1,089 | 1,827 | Actual |
| 2024/25 | 215 | 1,113 | 1,328 | Actual; projected 2,045 in Feb 2025 |
| 2025/26 | 1,140 | 1,260 | 2,400 → ~2,427 | Q3 projection → derived outturn |
| 2026/27 | – | – | 2,400 | Forecast, combined only |

Forecast evolution for 2024/25 (combined): budget 1,660 → P5 projection 1,790 →
Q3 projection 2,045 → actual 1,328.

## Contradictions and hypotheses

- **2022/23 split:** the annual review gives Ponds 823 / Lido 685; the later revenue
  reports give Ponds 176 / Lido 1,341. The totals agree within £10k. The Ponds
  "actual" equals the P9 (Apr–Dec) actual-to-date. The P9 report says some Lido
  income "could relate to Ponds".
  *Hypothesis:* pond income was booked to the Lido line in the ledger.
- **2024/25 Ponds:** the Apr–Dec actual-to-date was 786, but the full-year actual
  is 215. The same year "Facilities" income was 721 against a 287 budget (Feb 2026
  appendix, prior-year column).
  *Hypothesis (unconfirmed):* pond income was reallocated to Facilities.
- **2023/24 Ponds:** the actual-to-date was unchanged at 149.5 between P6 and P9,
  which also suggests a posting issue.
- **2025/26 Lido budget:** the budget estimates (Feb 2025) add 100 to the 850
  2024/25 budget, but the 2025/26 budget is 1,104. The Ponds +200 (810 → 1,010) is
  consistent.
- **2024/25 budget:** the Nov 2023 budget report projects "£760k additional income
  from the Ponds and Lido". The 2023/24 budgets (667 + 725 = 1,392) plus 760 would
  give 2,152, not the 1,660 later shown as the 2024/25 budget.
- **Format change:** after Q3 2025/26 the reports give only a combined Lido + Ponds
  figure. From 2026/27, swimming sits inside "Trading" in the charity SOFA format.
  The 2026/27 budget adds 185 for "swimming and sporting income".

## Costs

Per-facility staff and running costs appear only in the annual reviews
(2018/19 total only; 2020/21–2022/23 in full). In 2022/23:

- **Ponds:** staff 752, running costs 37, plus a 351 one-off payment to the access
  project; subsidy 317.
- **Lido:** staff 567, running costs 216; subsidy 99.

The 2022/23 Ponds expenditure (1,140) includes the 351 "one off payment to
support access project at ponds", a contribution to the capital project, counted
as operating expenditure in the annual review table. Excluding it, Ponds running
costs were 789 against income of 823: a surplus of 34, not a subsidy of 317. The
2022/23 revenue outturn separately records 257 of local-risk funding used to
part-fund the capital project, so these two figures may overlap.

Later years report only variances, e.g. 266 on seasonal lifeguards and 50 on Lido
water in 2025/26.

## Capital: Swimming Facilities – Safety, Access & Security Improvements

- **May 2021:** 755 funding awarded.
- **Feb 2022 (Gateway 2):** estimated cost 697, or 755 including risk.
- **Jun 2022 (Gateway 3/4):** 691 / 755.
- **Jan 2023:** every tender came in above the 490 pre-tender estimate.
- **Dec 2022 – Feb 2023:** estimated cost 776, approved budget 191.
- **Oct 2025:** approved 1,011, from OCR of an image table.
- **Oct 2026:** about 994 spent.
- The approval of the increase from 776 to 1,011 isn't in these committee papers;
  it was perhaps approved by a Projects Sub-Committee.
- In 2022/23 the Heath's local risk budget contributed 257, and Supplementary
  Revenue Project funding of 68 (2022/23) and 2 (2023/24) also appears.

The Lido photovoltaic panels project grew from 294 (Oct 2025) to 454 (Oct 2026).

## Per-swim figures

| Year | Facility | Swims | Cost/swim | Income/swim |
| --- | --- | ---: | ---: | ---: |
| 2018/19 | Ponds | 655,000 (est.) | £1.14 | £0.10 |
| 2020/21 | Combined | 160,172 (Jul–Jan) | £8.86 | £3.38 |
| 2021/22 | Ponds | 335,005 | £2.37 | £2.02 |
| 2021/22 | Lido | 160,749 | £5.33 | £2.83 |
| 2022/23 | Ponds | 368,678 | £3.09 (£2.14 excl. one-off) | £2.23 |
| 2022/23 | Lido | 234,099 | £3.35 | £2.92 |
| 2025/26 | Ponds | 430,610 | – | £2.65 (projection) |

The 2018/19 Ponds income of 10p per swim reflects the voluntary-payment era
(about 6% compliance). The planned repair lists total £184k (2021/22 bids) and
£597k (2026/27), of which the Lido accounts for £75k and £510k.

## Planned chart set

1. **Income forecasts vs outcomes** (implemented: `city-chart.py --chart income`; see
   [docs/city-chart.md](../docs/city-chart.md)).
   Three panels: Lido, Ponds, combined. For each fiscal year the chart shows the
   budget, successive projections shaded by report date, and the final actual.
   Restatements that disagree are flagged.
2. **Costs vs income** (implemented: `--chart costs`; cost and income per swim: `--chart per-swim`): stacked staff, running and one-off costs per facility-year,
   with income overlaid and the subsidy shaded. Covers 2018/19 and 2020/21–2022/23,
   with later years marked "no longer published".
3. **Capital project timeline** (implemented: `--chart capital`): step lines of estimated cost and approved budget
   against report date, with spent-to-date and labelled milestones. The 2023–2025
   gap is dashed.
4. **Repair lists 2021 vs 2026** (implemented: `--chart maintenance`): horizontal bars by building, e.g. the Lido
   rewire at 30 in the 2021/22 list and 180 in the 2026/27 list.
