# jwpc19

Development host notes for Ubuntu 24.04 on WSL2 (Windows 11).

This folder is intended for developer-side helpers and host-specific setup notes.

## User Unit Scripts
- install-user-units.sh: installs and enables pond-dev-sync user units
- remove-old-units.sh: disables/removes deprecated pond-rsync-data user units during migration

## Local Dev Web/API Server
- Run one local Python process that serves both static pages and API on one port:

```bash
cd ~/projects/pond
python -m uvicorn pond.dev_web_api:app --host 0.0.0.0 --port 8000
```

- Pond update submissions from `/api/pondupdate` are logged to `user-updates/user-updates-yymmdd.jsonl` (daily rolling).
