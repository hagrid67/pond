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

## Heath staff costs and swimming's share

Hampstead Heath charity staff costs (accounts, £k; average headcount):

| Year | Salaries | NI | Pension | Total | Headcount | Swimming staff | Swimming share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2017/18 | 3,632 | 362 | 644 | 4,639 | 96 | | |
| 2018/19 | 3,718 | 366 | 667 | 4,750 | 99 | | |
| 2019/20 | 3,787 | 372 | 672 | 4,831 | 98 | | |
| 2020/21 | 3,906 | 378 | 660 | 4,944 | 97 | 1,106 | 22.4% |
| 2021/22 | 4,102 | 396 | 685 | 5,182 | 100 | 1,479 | 28.5% |
| 2022/23 | 3,966 | 405 | 639 | 5,010 | 83 | 1,320 | 26.3% |
| 2023/24 | 4,286 | 415 | 703 | 5,404 | 88 | | |
| 2024/25 | 4,214 | 409 | 690 | 5,313 | 78 / 88 | | |
| 2025/26 | 4,540 | 560 | 824 | 5,924 | 93 | | |

Heath staff costs rose 28% from 2017/18 to 2025/26. Most of the rise is in
2025/26 (+11.5% in one year), with NI up 37% after the April 2025 employer NI
increase.

**Rough estimate of later swimming staff costs** (no breakdown published after
2022/23; charted by `city-chart.py --chart staff`):

- **Scaling** the 2022/23 swimming staff cost (1,320) by Heath staff growth gives
  1,423 (2023/24), 1,399 (2024/25) and 1,560 (2025/26).
- **Applying the observed share range** (22.4–28.5%) to 2025/26 gives 1,327–1,688.
- **Upward pressure:** the 2025/26 outturn reports a 266 overspend on seasonal
  lifeguards because of higher usage, which suggests the upper half of that range.
  The Q3 2025/26 Direct Employees projection was 5,750 against a 5,406 budget.
- **Caveats:**
  - only three years of shares;
  - 2020/21 was Covid-affected;
  - 2022/23 swimming totals have the arithmetic error noted in the README;
  - the swimming reviews may define staff costs differently from the accounts
    (e.g. recharged staff).

### Pay levels (what is and isn't published)

- **Committee papers:** no lifeguard or other Heath pay rates, grades or medians.
  The accounts give only:
  - average headcount (above);
  - the number of staff whose pay (excluding employer NI and pension) exceeded
    £60,000: 2 in 2018/19–2020/21, 1 in 2021/22, and none from 2023/24.
- **Average cost per head (accounts, rough; casual staff are counted in an
  unstated way):**
  - 2025/26: £4.54m salaries ÷ 93 staff ≈ £48.8k salary per head (£63.7k with
    NI and pension);
  - 2022/23: £3.97m ÷ 83 ≈ £47.8k (£60.4k).
- **New security posts:** the October 2026 approval of £347k a year for 9 FTE
  (constables, a sergeant, a Health & Safety Manager and an arborist) is about
  £38.6k per FTE, net of offset savings on security contractors.
- **City of London pay (corporate, not Heath-specific):**
  - Real Living Wage employer; London Living Wage £14.80/hour from 22 Oct 2025
    (Pay Policy Statement 2026-27, §3.3.1).
  - 2025/26 grade structure with inner London weighting (£6,920):
    - Grade A/B from about £32.1k (£17.59/hour);
    - Grade C about £38.1k;
    - Grade D about £44.1k;
    - up to Grade J about £103k.

    Source: "main pay and grading structure appendix B", rates from 1 July 2025;
    grade boundaries read approximately from the table.
  - Highest-to-median pay ratio 1:6 (Oct 2025).
  - No lifeguard advert or grade was found online. Casual and seasonal
    lifeguards are probably at or near the bottom grades and the London Living
    Wage, but this is unverified.

### Employer NI and pension

- **April 2025 employer NI change:** from 6 April 2025 the rate rose from 13.8%
  to 15% and the secondary threshold fell from £9,100 to £5,000 per employee.
  Heath employer NI rose from 409 to 560 (+37%) while salaries rose 7.7%. About
  119 a year is attributable to the NI change, i.e. NI above what pay growth
  alone would give.
- **NI as a share of salaries:** 9.7–10.0% from 2017/18 to 2024/25 (10.2% in
  2022/23, when the 1.25-point Health and Social Care Levy applied from April to
  November 2022), then 12.3% in 2025/26.
- **Pension:** employer pension also rose, from 16.4% of salaries in 2024/25 to
  18.2% in 2025/26.
- **Central funding:** the 2025/26 outturn shows only 40 of central contingency
  funding for "July 2024 pay award and increases in employer national insurance
  contributions".
- **Swimming's part:** at a 26% share, roughly a quarter of the ≈119 attributable to the NI
  change (≈30 a year) falls on swimming staff.

### Lifeguard overspend and the estimate band

- **The overspend:** the 2025/26 outturn reports a 266 overspend on seasonal
  lifeguards. The chart adds it to the 2025/26 central estimate (1,560 → ~1,826)
  and raises the band's upper edge to match.
- **Possible double-counting:** the overspend is already inside the Heath total
  that the central estimate is scaled from. Adding it in full treats it as wholly
  extra to swimming, so it's an upper bound.
- **2026/27 forecast:** Heath Direct Employees is forecast to overspend by 198
  (5,736 against 5,538) because "increase in summer visitors at the LIDO has
  resulted in more lifeguards and stewards needed", offset by gardener and
  property technician vacancies.

### Summer 2026: Lido security

- **The incidents:** a large fight at Parliament Hill Lido on 25 May 2026 (staff
  injured, one arrest, one person hospitalised with a bottle injury), and another
  fight on 28 May in the queue.
- **Measures:** ID checks; no under-16s without a responsible adult; random bag
  searches; and extra security hired when it is 25°C or above. Two Parkguard
  security officers were appointed from 22 May to early September 2026.
- **Cost:**
  - estimated at £15,000–£20,000 for 2026/27 (July 2026 Assistant Director's
    report, p7);
  - reported in October as c. £24,000 of "additional out-of-budget cost" for
    22 May – 6 September (p8);
  - 92 prohibited items were seized, including 70 glass containers.
- **Not staff costs:** these are contracted security, so they appear neither in
  staff costs nor in the staff chart. They are recorded in `swimming-costs.csv`.
- **Longer term:** the October 2026 finance report notes 810 (347 a year, from
  1 December 2026) approved from the City's Estate Security Reserve for 9 FTE
  security and safety-related posts across North London Open Spaces (6 constables,
  a sergeant, a Health & Safety Manager and an arborist). It also notes plans to
  review the swimming staffing model and "regularise casual working".

## Endowment and investment income

The Hampstead Heath Trust Fund was endowed with £15m in 1989. Its income
contributes to the Heath's running costs, up to a maximum set by the transfer
order. Figures in £k (`endowment.csv`):

| Year | Endowment at year end | Investment gains | Income received | Contribution to running costs | Budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021/22 | | | 2,025 | | |
| 2022/23 | | | 1,544 | 1,376 | |
| 2023/24 | 36,853 | 2,051 | 1,361 | 1,175 | 2,256 |
| 2024/25 | 39,353 (restated 40,459) | 2,704 | 1,599 | 1,395 | 2,493 (outturn proj. 1,505) |
| 2025/26 (draft) | 44,213 | 3,553 | 1,898 | 1,467 | 1,459 |
| 2026/27 | | | | | 1,503 |

- **The endowment has nearly trebled in value**, from £15m to £44.2m at 31 March
  2026, but the Heath receives only a capped annual contribution, about £1.4–1.5m
  (about 3.3% of the endowment). The 2025/26 investment gains (£3.55m) were more
  than twice the contribution.
- **Surplus income stays in the endowment:** £916k of income accumulated above
  the permitted contribution in earlier years was reclassified from general funds
  to endowment in 2025/26 on legal advice. Another £231k surplus was added that
  year.
- **Budgets overstated income:** the 2023/24 and 2024/25 budgets (£2.26m, £2.49m)
  were well above what was received. 2024/25 was projected £988k short. The
  2025/26 budget was cut by £1.034m to £1.459m "in line with actual income returns".
- **Comparison with swimming:** the annual Trust contribution (about £1.47m) is
  similar to the estimated swimming staff cost (£1.3–1.8m) and to Ponds or Lido
  income alone. Total swimming income (about £2.4m) is larger.
- **Funding model:** in February 2025 the City replaced the "deficit funding"
  model with a grant funding model for its Natural Environment charities, which
  can carry forward accumulated grant. The City's revenue and capital grants to
  the Heath were £8.25m in 2025/26 (£6.23m in 2024/25).

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
(about 6% compliance). The planned repair lists total £184k (2021/22 deferred and reserve lists, not funded that year) and
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
