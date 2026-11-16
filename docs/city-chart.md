# Hampstead Heath finance charts

[`scripts/city-chart.py`](../scripts/city-chart.py) draws charts from City of London
committee papers. Choose one with `--chart`:

| `--chart` | Chart | Default output |
| --- | --- | --- |
| `sankey` (default) | 2025/26 operating budget Sankey | `charts/hh-budget-sankey-2025-26.png` |
| `income` | Lido/Ponds income: budgets, forecasts and actuals by report | `charts/swimming-income-forecasts.png` |

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
| `--figsize` | `18,10` | Figure size in inches |

### Layout

Income flows from the left into a central "Hampstead Heath" node and out to
expenditure on the right. Columns move outward from subtotals to line items. A
node's children are hidden when they add no detail (a single child, or one
child is at least 90% of the parent). Shorter branches continue as plain bands
to the outer column.

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
