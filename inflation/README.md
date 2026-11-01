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
`rpi.csv` and `cpih.csv`, anchored to May of the chosen base year (since each
season year starts in May). When `--rpi` and/or `--cpih` are passed on the
command line, the script plots a monthly inflation-adjusted line at 50% alpha
and 50% colour saturation for each ticket price series in the matching line
style:

`Index-equivalent price = base-year ticket price × monthly index / May index for base year`

CLI options control the chart start year and inflation display:
- `--lido`: plot Parliament Hill Lido fees (`prices/lido-fees.csv`) instead of
  Bathing Ponds fees (`prices/pond-fees.csv`), using three stacked sub-plots by
  default (12-Month Season tickets, Daily Peak PAYG tickets, and Daily Off-Peak
  PAYG tickets).
- `--start-year YEAR`: chart start year (default `2011`).
- `--geometric` / `--geometric-2027`: replace the linearly interpolated 2027
  prices with geometric interpolation between 2026 and 2028 ($r_2 = p_{28}/p_{26} - 1$,
  $r_1 = \sqrt{r_2 + 1} - 1$, $p_{27} = \text{round}(p_{26}(1 + r_1), 2)$).
- `--rpi`: show RPI-adjusted lines for all four ticket series.
- `--cpih`: show CPIH-adjusted lines for all four ticket series.
- `--base-year YEAR`: year from which the inflation lines start (May of `YEAR`)
  and pass through the ticket prices (defaults to `--start-year`).
  `--rpi-base-year` and `--cpih-base-year` can also override the base year per
  index.
- `-o`, `--filename`, `--output`: output PNG filename or path. When omitted, a
  filename is constructed in `charts/` from the active CLI options (for example,
  `bathing_ponds_fee_trajectory_from_2011.png` or
  `bathing_ponds_fee_trajectory_from_2011_rpi_2020_cpih_2020.png`).

Monthly observations are plotted as historical curves up to the latest ONS
observation (September 2026). From September 2026 through May 2029, the script
plots a dotted forecast line extending each index at the constant annual rate
observed over the latest 12 months in the dataset (September 2025 to September
2026: +3.9%/yr for RPI and +3.7%/yr for CPIH).
