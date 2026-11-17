# Hampstead Heath finance charts

[`scripts/city-chart.py`](../scripts/city-chart.py) draws charts from City of London
committee papers. Choose one with `--chart`:

| `--chart` | Chart | Default output |
| --- | --- | --- |
| `sankey` (default) | 2025/26 operating budget Sankey | `charts/hh-budget-sankey-2025-26.png` |
| `income` | Lido/Ponds income: budgets, forecasts and actuals by report | `charts/swimming-income-forecasts.png` |
| `costs` | Lido/Ponds staff, running and one-off costs against income, subsidy shaded | `charts/swimming-costs.png` |
| `per-swim` | Cost and income per swim where swim counts were published | `charts/swimming-per-swim.png` |
| `capital` | Capital project budget, estimate and spend by report date | `charts/swimming-capital.png` |
| `maintenance` | Cyclical works for swimming buildings, 2021/22 deferred/reserve lists vs 2026/27 list | `charts/swimming-maintenance.png` |
| `cwp` | Cyclical Works Programme 2026/27 by site (swimming exploded), with a project pie per site | `charts/cwp-2026-27.png` |
| `staff` | Heath staff costs (salaries, NI, pension) with swimming staff costs, share and estimate | `charts/heath-staff-costs.png` |

`--figsize WIDTH,HEIGHT`, `--output PATH` and `--show` apply to both.

## Budget Sankey (`--chart sankey`)

The Sankey chart draws a multi-level Sankey
diagram (with Matplotlib) of the Hampstead Heath operating budget, using the
2025/26 **projected outturn** column from the Hampstead Heath Operating Budget
table: page 147 of the 3 Feb 2026 HHHWQP Committee reports pack
(`col-pdfs/hhhwqp/2026-0203/reports-pack.pdf`, Finance Progress Report Q3,
Appendix 1).

```bash
./ve312pond/bin/python scripts/city-chart.py                 # depth 3, merge items < 2.5%
./ve312pond/bin/python scripts/city-chart.py --depth 2       # subtotals only
./ve312pond/bin/python scripts/city-chart.py --min-share 0.01 --figsize 20,12
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--depth` | `3` | Breakdown levels each side of the centre |
| `--min-share` | `0.025` | Merge two or more siblings below this share of the total into "Other …" |
| `--no-swimming-estimate` | off | Don't split Employees into swimming (HMPA estimate) and other staff |
| `--figsize` | `18,10` | Figure size in inches |

### Layout

Income flows from the left into a central "Hampstead Heath" node and out to
expenditure on the right. Columns move outward from subtotals to line items. A
node's children are hidden when they add no detail (a single child, or one
child is at least 90% of the parent). Shorter branches continue as plain bands
to the outer column. Labels for Lido, Ponds, City of London funding and Employees
(`SANKEY_HIGHLIGHTS`) are larger and bold. The footnote explains that City of
London funding is the table's Total Net Expenditure.

**HMPA swimming staff estimate.** Employees (£5.79m) is shown as a subtotal node
level with Supplies & services and Support services. It splits into **Swimming
staff (HMPA estimate) £1.83m** and **Other staff £3.96m**. The swimming figure is
the 2025/26 upper estimate from `--chart staff` (`swimming_staff_estimate()`): the
central estimate plus the £266k seasonal lifeguard overspend. On the swimming bar,
the solid part runs to the lower estimate (£1.32m, lowest observed share), with
ticks at all three estimates (£1.32m, central £1.56m and upper £1.83m); a note beside it gives the range. It is
labelled as an HMPA estimate, not a City of London figure, and the footnote
summarises the method. The estimate comes from the accounts' staff costs, so it
is only approximately comparable with the budget table's Employees line.

### How the table is encoded

`income_tree()` and `expenditure_tree()` hold the line items as a hierarchy.
The `published` values are the table's own subtotal and total rows, and the
script checks every group sums to them before drawing:

| Table rows (subtotals in bold) | Chart grouping |
| --- | --- |
| Lido, Ponds | Swimming → Operating income (Local Risk) |
| Parking, Facilities, Film, Licences, Rents, Other, Grants, Sales | Operating income (Local Risk) |
| **Total Income (Local Risk)** £4.24m | Operating income (Local Risk) |
| Investment Income (= **Total Income (Central Risk)**) | Investment income (Central Risk) |
| Recharges Within Fund (Corporate and Democratic Core) | Recharge income |
| **Total Net Expenditure** £7.058m | City of London funding (the shortfall) |
| Employees, **Premises**, **Transport**, **Supplies and Services** | Operating costs (Local Risk), **Total Expenditure (Local Risk)** £7.32m |
| Capital Charges | Capital charges (Central Risk) |
| **Total Support Services**, Natural Environment Directorate and Structural Maintenance recharges | Recharges, **Total Expenditure (Recharges)** £1.81m |
| Cyclical Works Programme, **City Surveyor's Facilities Management** | City Surveyor's works |

Both sides total £12.917m. Total expenditure is Local Risk £7.321m + Central
Risk £0.408m + Recharges £1.809m + City Surveyor £3.379m. Total income is
£4.240m + £1.459m + £0.160m, plus £7.058m net expenditure.

"Local Risk" and "Central Risk" are City of London budget categories, not
funding sources. Local Risk budgets are controlled by the service's own
managers (day-to-day staff, premises and supplies, and income such as swimming
and parking). Central Risk budgets are managed centrally (here capital charges
and investment income). The City's contribution is the **Total Net Expenditure**
line, shown as "City of London funding".

## Swimming income forecasts (`--chart income`)

This chart shows how each year's Lido and Ponds income figure changed from report
to report, and flags where later reports contradict earlier ones. Data comes from
[`finance/swimming-income.csv`](../finance/README.md); see also the working notes in
[`finance/commentary.md`](../finance/commentary.md).

```bash
./ve312pond/bin/python scripts/city-chart.py --chart income
./ve312pond/bin/python scripts/city-chart.py --chart income --facilities combined --no-ytd --figsize 12,6
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--data` | `finance/swimming-income.csv` | Income CSV |
| `--facilities` | `lido ponds combined` | Panels to draw, top to bottom |
| `--no-ytd` | off | Hide part-year actual-to-date points (they are still used to flag contradictions) |
| `--figsize` | `14,13` | Figure size in inches |

**Encoding:**

- Each fiscal year is a column. Its points are spread left to right in report-date
  order, and colour also shows the report date (colour bar).
- Grey lines join budget → projections → actuals, so a projection that moves is
  visible.
- Marker shapes:
  - hollow square: budget
  - triangle: actual to date (part year)
  - circle: projected outturn
  - diamond: actual (annual swimming review or later revenue report)
  - plus: outturn derived from budget + stated variance
- Actuals are labelled with their value. When a year has no actual yet, its latest
  projection is labelled instead. Years with no figures are marked.

**How the combined panel is built:** it uses directly stated combined figures (the
CSV facility `ponds+lido`). It also sums Lido and Ponds figures of the same type
from the same report.

**Contradictions (red ×)** are detected automatically within each facility and year:

- a final figure (actual, annual review, derived outturn) differs by more than 5%
  from an earlier final figure; or
- a final figure is more than 5% below an earlier actual-to-date.

Identical figures restated in later reports are drawn and checked once.

## Swimming costs, per swim, capital and maintenance

These charts read the CSVs in [`finance/`](../finance/README.md); see
[`finance/commentary.md`](../finance/commentary.md) for interpretation. They take
only the shared `--figsize`, `--output` and `--show` options (`costs` and
`per-swim` also use `--data` for income).

```bash
./ve312pond/bin/python scripts/city-chart.py --chart costs
./ve312pond/bin/python scripts/city-chart.py --chart per-swim
./ve312pond/bin/python scripts/city-chart.py --chart capital
./ve312pond/bin/python scripts/city-chart.py --chart maintenance
./ve312pond/bin/python scripts/city-chart.py --chart staff
```

### Costs against income (`--chart costs`)

- **Panels:** one for the Ponds and one for the Lido, with one stacked bar per year
  (staff, running costs, and the 2022/23 one-off access payment). 2018/19 has only
  a grey total.
- **Income markers:**
  - black diamond: annual swimming review;
  - white diamond: revenue-report actual. It is shown only when there is no
    review figure or the two disagree; disagreements are red and joined by a
    dashed line.
  - white circle: latest projection.
- **Subsidy:** the hatched area between income and cost, labelled with £ and % of
  cost (from the annual reviews).
- **Capital in operating costs:** the 2022/23 Ponds bar includes the £351k one-off
  contribution to the access capital project, which the annual review counts as
  operating expenditure. A callout labels it and gives the result without it
  (a £34k surplus instead of a £317k subsidy).
- **2023/24 onwards:** marked "cost breakdown no longer published", but income is
  still shown.

### Cost and income per swim (`--chart per-swim`)

- **Data:** joins `swim-counts.csv` with total costs and income for years with
  published swim counts.
- **Bars:** cost per swim, with the one-off access payment shown separately.
- **Markers:** income per swim. When no review income exists the latest projection
  is used (2025/26).
- **Subsidy:** hatched.
- **Caveats:** marked `*` on the swim counts: 2018/19 swims are estimated, and
  2020/21 swims cover July–January only.

### Capital timeline (`--chart capital`)

- **Main panel:** the Swimming Facilities – Safety, Access & Security project.
  - Step lines for the total estimated cost and the approved budget.
  - Spend to date (including committed at gateways) as a filled area.
  - Pre-tender estimate (×), the £755k funding award (★ and dotted line), and
    milestone labels.
- **Gaps:** segments more than 450 days apart with no reports are dashed or faint,
  and the period with no updates in this committee's papers is shaded.
- **Lower panel:** the Lido photovoltaic panels.

### Planned maintenance (`--chart maintenance`)

- **Data:** sums the `planned_cwp` items in `swimming-maintenance.csv` by building
  (Lido, Men's, Ladies', Mixed, all-ponds infrastructure).
- **Comparison:** paired bars for the 2021/22 deferred and reserve lists (projects not funded in
  2021/22) and the 2026/27 project list,
  labelled with £ and item counts.
- **Not shown:** maintenance cited in outturn reports (for example the 2024/25
  Men's Pond jetty).

### Heath staff costs and swimming share (`--chart staff`)

- **Bars:** Hampstead Heath charity staff costs by year from the accounts
  (`heath-costs.csv`), stacked as salaries, employer NI and employer pension, and
  labelled with the total and average headcount. Restated values from later
  accounts are used.
- **Swimming staff:** the solid red line is swimming staff costs (Ponds + Lido
  employee costs from the annual swimming reviews, 2020/21–2022/23). The dotted line
  on the right axis is their share of Heath staff costs.
- **Estimate for later years:**
  - dashed line: the last published swimming staff cost scaled with Heath staff
    cost growth;
  - shaded band: the range given by the lowest and highest observed share. Its
    upper edge is raised to the central estimate plus any swimming-specific
    overspend in `swimming-costs.csv` (`seasonal_lifeguards_overspend`, e.g. £266k
    in 2025/26), drawn as a dark red arrow. This is an upper bound, because the
    overspend is already part of the Heath total the estimate is scaled from.
- **NI callout:** for years in `NI_CHANGES` (currently 2025/26) a callout describes
  the employer NI change. It quantifies the change from the accounts: the NI
  increase compared with salary growth, and the part not explained by pay growth.
- **Coverage:** see [finance/README.md](../finance/README.md#what-the-staff-cost-figures-include)
  for what the staff costs include (casual lifeguards: yes; contracted security:
  no).

### Cyclical Works Programme (`--chart cwp`)

- **Data:** reads `finance/cwp.csv` (regenerate with
  `./ve312pond/bin/python scripts/extract-cwp.py`).
- **Main pie:** the 2026/27 project list by site; swimming sites (Lido and the three
  ponds) are pulled out and labelled in bold.
- **Small pies:** one per site, breaking it down into projects. Small items are
  grouped as "n other items"; swimming sites list more of their items.
- **Sites:** assigned from the item names by keyword (`CWP_SITES`); anything not
  matched goes to Misc.
- **Other years:** `--cwp-year 2020/21` charts the 2020/21 actual list. The 2021/22
  lists are deferred/reserve lists, so they aren't charted.
- **Notes:** see [finance/cwp.md](../finance/cwp.md).
