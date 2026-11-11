# pond

Initial repository setup.

## Development install

Use one shared pond venv per host, including Python minor in the venv name.

Examples:
- Ubuntu 24.04 hosts (Python 3.12): `ve312pond`
- Debian 12 hosts (Python 3.11): `ve311pond`

Create or activate your venv, then install from pinned requirements:

```bash
python3 -m venv ve312pond
source ve312pond/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Dependency refresh workflow

Pinned versions are tracked in `requirements.txt`.

When you want to refresh periodically:

```bash
source ve312pond/bin/activate
python -m pip install --upgrade fastapi uvicorn pydantic
python -m pip freeze | rg "fastapi|uvicorn|pydantic"
```

Then update `requirements.txt`, test deploy/check flows, and commit.

## Dev web + API server (single port)

To serve static files from `www-root/` and the pond update API from the same port:

```bash
pip install fastapi uvicorn
python -m uvicorn pond.pond_web_api:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /` serves `www-root/index.html`
- `POST /api/pondupdate` accepts pond update JSON payloads
- `GET /api/health` simple health check

Submitted updates are appended to `user-updates/user-updates-yymmdd.jsonl` (daily rolling file names).

## Benchmark spreadsheet

Read the main venue table from the first sheet of the "Benchmarking - October 2026"
Google Sheet (ID hardwired in the script) and make two scatter plots, with adult
price on the x-axis and concession price on the y-axis:

- One-off prices: `charts/benchmark1.png` (`-o PATH` to change).
- Annual membership/season-ticket prices: `charts/benchmark2.png`
  (`--annual-output PATH` to change).

Markers are orange for heated and blue for unheated venues (from the
`Water Temperature` column).
Each marker is labelled with its venue name(s); venues with identical prices share a
marker, labels for venues within 2p of each other are merged with their adult prices,
and `adjustText` keeps labels apart. Venues without a concession price are listed in
the footnote instead of plotted. The annual chart uses the spreadsheet's adult and
concession annual columns directly, omitting venues missing either price. Both
charts have labelled dashed reference lines for concessions at 100%, 50% and 25%
of the adult price. Annual x-axis ticks are spaced at £100 (one-off ticks at £1).

Proposed 2027 and 2028 Heath prices are drawn as hollow diamonds, joined by dashed
arrows from today's pond and Parliament Hill Lido markers. They are read from
`prices/pond-fees.csv` (PAYG) and `prices/lido-fees.csv` (peak PAYG) through
`load_prices` in `scripts/price-chart.py`. The 2027 values default to the linear mean of
2026 and 2028; add `--geometric` to use the geometric mean, or `--no-proposed` to omit
them. The annual chart uses the `adult_season_12m_gbp` and
`concession_season_12m_gbp` columns from both price CSVs, with the same interpolation
options.

```bash
./ve312pond/bin/python scripts/benchmark-chart.py
```

The table starts at the first row with at least three filled cells and ends at the
next blank row; the `Average` row is kept separate from the venue data. Add
`--columns N` to also print the first `N` columns of the table.

List the ten most recently modified Google Sheets accessible to your Google
account, including their containing folder paths, modification times, URLs and IDs:

```bash
./ve312pond/bin/python scripts/benchmark-chart.py --list-sheets
```

The script uses `secrets/token-google.pkl` relative to the repository root, or
`--token PATH`. This must be a **trusted** pickle containing Google OAuth
credentials with the `drive.metadata.readonly` and `spreadsheets.readonly` scopes.
Never load a token pickle from an untrusted source. Expired credentials are
refreshed and saved back to the same token file; no Drive files are changed.

To create or replace the token (e.g. after `invalid_grant` or missing scopes),
sign in via the browser using the `perfin` OAuth client
(`../personal-finance/google/credentials.json`, override with `--credentials`):

```bash
./ve312pond/bin/python scripts/benchmark-chart.py --reauth --no-browser
```

Open the printed URL; the callback listens on `localhost:8765` (`--port`).
Folders that cannot be read are marked explicitly, with a warning on stderr.

## Seasonal booking charts

Generate the original pond demand heatmap, daily/weekly occupancy chart, and a
separate percentage heatmap including the lido:

```bash
python -m pond.season-plot
```

The additional outputs are `www-root/season-percentage.png` and
`www-root/lido-availability.csv`. The CSV has one row per observed lido session,
with weekday, Monday week start, first/maximum/final pre-start availability, and
the lead time of the first observation. Missing sessions are not treated as zero.

`www-root/season-occupancy-colour.png` is an additional colour version of the
daily/weekly occupancy chart. Monday-Sunday bars use 80% alpha and a shared
0-100% yellow-orange-red scale (red at 100%) for weekly occupancy, without booking-ahead scores. The
daily curves are drawn in front of the bars; dashed incomplete weeks and closure shading are retained.
Use `--colour-occupancy-output PATH` to change its output path.

The percentage heatmap uses estimated lido capacities of 800 morning, 800
afternoon, and 300 evening tickets. These are assumptions, not measured total
capacities: snapshots record remaining tickets, which already reflect sales.
Override the estimates and output path with:

```bash
python -m pond.season-plot --lido-capacities 800 800 300 --percentage-output www-root/season-percentage.png
```

These estimates affect only the new percentage heatmap, not the original pond
heatmap or the existing daily/weekly chart (which still assumes 650 per lido
session). In `season-percentage.png`, red means the session reached actual
sell-out (zero remaining tickets) at least once before or at its start. Its
darkness measures the elapsed days from the **first observed sell-out** to the
session start, capped at seven days. Later cancellations and rebookings do not
reset this clock or remove the red colouring, even if tickets remain at the
start. This represents demand reached, not continuous sell-out or final sales;
it does not establish why tickets became available again. Snapshot frequency
limits how precisely the first sell-out time is known.

Sessions never observed at zero use their last pre-start percentage occupancy;
nearly sold-out sessions are not treated as fully sold out. Grey indicates no
session or no observation, not necessarily a closure. The original pond-only
`season-plot.png` is unchanged: it uses a fewer-than-five-tickets threshold and
requires the final pre-start availability to remain below that threshold.
Daily/weekly occupancy charts still use last pre-start ticket counts, without
booking-ahead weighting.
