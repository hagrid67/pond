# Hampstead Heath budget Sankey chart

[`scripts/city-chart.py`](../scripts/city-chart.py) draws a multi-level Sankey
diagram (with Matplotlib) of the Hampstead Heath operating budget, using the
2025/26 **projected outturn** column from the Hampstead Heath Operating Budget
table: page 147 of the 3 Feb 2026 HHHWQP Committee reports pack
(`col-pdfs/hhhwqp/2026-0203-reports-pack.pdf`, Finance Progress Report Q3,
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
| `--output` | `charts/hh-budget-sankey-2025-26.png` | Output PNG |
| `--show` | off | Open an interactive window |

## Layout

Income flows from the left into a central "Hampstead Heath" node and out to
expenditure on the right. Columns move outward from subtotals to line items. A
node's children are hidden when they add no detail (a single child, or one
child is at least 90% of the parent). Shorter branches continue as plain bands
to the outer column.

## How the table is encoded

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
