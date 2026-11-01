# UK inflation index data

These CSV files are official ONS time-series downloads from dataset MM23. They
include the ONS metadata and annual, quarterly, and monthly observations.

| File | ONS series | Description | Source |
| --- | --- | --- | --- |
| `rpi.csv` | CHAW | RPI All Items Index: Jan 1987=100 | [ONS time series](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/chaw/mm23) |
| `cpi.csv` | D7BT | CPI Index 00: All Items 2015=100 | [ONS time series](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7bt/mm23) |
| `cpih.csv` | L522 | CPIH Index 00: All Items 2015=100 | [ONS time series](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/l522/mm23) |

The downloads in this folder were retrieved on 25 October 2026; each CSV
records the ONS release date in its metadata.

`scripts/price-chart.py` uses pandas to load the monthly observations from
`rpi.csv` and `cpih.csv`, anchored to April of the chosen base year (since new
fees take effect in April at the start of the City of London financial year).
When `--rpi` and/or `--cpih` are passed on the command line, the script plots a
monthly inflation-adjusted line at 50% alpha and 50% colour saturation for each
ticket price series in the matching line style:

`Index-equivalent price = base-year ticket price × monthly index / April index for base year`

CLI options control the chart start year and inflation display:
- `--ponds`: plot Bathing Ponds fees (`prices/pond-fees.csv`), which is the
  default when `--lido` is not specified.
- `--lido`: plot Parliament Hill Lido fees (`prices/lido-fees.csv`) instead of
  Bathing Ponds fees (`prices/pond-fees.csv`), using three stacked sub-plots by
  default (12-Month Season tickets, Daily Peak PAYG tickets, and Daily Off-Peak
  PAYG tickets). Passing both `--ponds` and `--lido` generates both charts.
- `--start-year YEAR`: chart start year (default `2011`).
- `--geometric` / `--geometric-2027`: replace the linearly interpolated 2027
  prices with geometric interpolation between 2026 and 2028 ($r_2 = p_{28}/p_{26} - 1$,
  $r_1 = \sqrt{r_2 + 1} - 1$, $p_{27} = \text{round}(p_{26}(1 + r_1), 2)$).
- `--monthly`: plot the annual equivalent (`12×`) cost of the new rolling monthly
  tickets from April 2027, pinned to 20% above the equivalent 12-month season
  ticket, with stepped lines and upward vertical `+20%` arrows at April 2027 and
  April 2028 on the 12-month season plot.
- `--rpi`: show RPI-adjusted lines for all four ticket series.
- `--cpih`: show CPIH-adjusted lines for all four ticket series.
- `--base-year YEAR`: year from which the inflation lines start (April of `YEAR`)
  and pass through the ticket prices (defaults to `--start-year`).
  `--rpi-base-year` and `--cpih-base-year` can also override the base year per
  index.
- `--core`: generate the four core chart files in `charts/` (with `--monthly`
  enabled):
  - `ponds_fees_from_2011_rpi_2020.png`
  - `lido_fees_from_2011_rpi_2020.png`
  - `ponds_fees_from_2011_geometric_rpi_2020.png`
  - `lido_fees_from_2011_geometric_rpi_2020.png`
- `--upload`: upload the newly generated chart(s) to Google Drive
  (`SwimForum-2026/charts`).
- `-o`, `--filename`, `--output`: output PNG filename or path. When omitted, a
  filename is constructed in `charts/` from the active CLI options (for example,
  `ponds_fees_from_2011.png`, `lido_fees_from_2011.png`, or
  `ponds_fees_from_2011_rpi_2020_cpih_2020.png`).

Monthly observations are plotted as historical curves up to the latest ONS
observation (September 2026). From September 2026 through April 2029, the script
plots a dotted forecast line extending each index at the constant annual rate
observed over the latest 12 months in the dataset (September 2025 to September
2026: +3.9%/yr for RPI and +3.7%/yr for CPIH).
