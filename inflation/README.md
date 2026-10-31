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

`scripts/price-chart.py` uses pandas to select May observations from `rpi.csv`
and `cpih.csv` for the annual comparison. When `--rpi` and/or `--cpih` are
passed on the command line (or `SHOW_RPI` / `SHOW_CPIH` are set to `True`), the
script plots an inflation-adjusted line at 50% alpha for each of the four
ticket price series (Adult 12M Season, Concession 12M Season, Adult PAYG, and
Concession PAYG) in the matching colour and line style:

`Index-equivalent price = base-year ticket price × May index for year / May index for base year`

CLI options control the chart start year and inflation display:
- `--start-year YEAR`: chart start year (default `2011`).
- `--rpi`: show RPI-adjusted lines for all four ticket series.
- `--cpih`: show CPIH-adjusted lines for all four ticket series.
- `--base-year YEAR`: year at which the inflation lines pass through the ticket
  prices (defaults to `--start-year`). `--rpi-base-year` and `--cpih-base-year`
  can also override the base year per index.

Only years with an available May observation are plotted. This is a historical
inflation comparison, not an ONS forecast; proposed ticket prices remain
separately shown.
