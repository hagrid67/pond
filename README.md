# pond

Initial repository setup.

## Development install

Create or activate your virtual environment, then install in editable mode:

```bash
pip install -e .
```

## Dev web + API server (single port)

To serve static files from `www-root/` and the pond update API from the same port:

```bash
pip install fastapi uvicorn
python -m uvicorn pond.dev_web_api:app --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET /` serves `www-root/index.html`
- `POST /api/pondupdate` accepts pond update JSON payloads
- `GET /api/health` simple health check

Submitted updates are appended to `user-updates/user-updates-yymmdd.jsonl` (daily rolling file names).
