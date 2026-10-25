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
and `cpih.csv` for the annual comparison, and rebases both series to the
12-month adult season ticket price in the script's hardcoded `START_YEAR`
(currently 2011, with a verified price of £110). All ticket and inflation lines
start in that year. Inflation-equivalent PAYG lines are not plotted:

`Index-equivalent price = baseline ticket price × May index for year / May index for START_YEAR`

Only years with an available May observation are plotted. This is a historical
inflation comparison, not an ONS forecast; proposed ticket prices remain
separately shown.
