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

The percentage heatmap uses estimated lido capacities of 800 morning, 800
afternoon, and 300 evening tickets. These are assumptions, not measured total
capacities: snapshots record remaining tickets, which already reflect sales.
Override the estimates and output path with:

```bash
python -m pond.season-plot --lido-capacities 800 800 300 --percentage-output www-root/season-percentage.png
```

These estimates affect only the new percentage heatmap, not the original pond
heatmap or the existing daily/weekly chart (which still assumes 650 per lido
session). Red indicates actual sell-out, darkening with the time sold out in
advance; other colours indicate percentage occupancy. Grey indicates no session
or no observation, not necessarily a closure.
