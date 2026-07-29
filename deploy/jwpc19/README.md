# jwpc19

Development host notes for Ubuntu 24.04 on WSL2 (Windows 11).

This folder is intended for developer-side helpers and host-specific setup notes.

## User Unit Scripts
- install-user-units.sh: installs and enables pond-dev-sync, pond-dev-web-api, and pond-user-chart user units
- remove-old-units.sh: disables/removes deprecated pond-rsync-data user units during migration
- manage-pond-services.sh: start/stop/restart/status for all jwpc19 pond user units

## Local Dev Web/API Server
- The local API/static host runs as a user service on port 8000 using the shared pond venv:

```bash
~/projects/pond/deploy/jwpc19/manage-pond-services.sh restart
```

- Service ExecStart uses:

```bash
~/projects/pond/ve312pond/bin/python -m uvicorn pond.dev_web_api:app --host 0.0.0.0 --port 8000
```

- Pond update submissions from `/api/pondupdate` are logged to `user-updates/user-updates-yymmdd.jsonl` (daily rolling).

## One-Command Local Service Control

```bash
~/projects/pond/deploy/jwpc19/manage-pond-services.sh status
~/projects/pond/deploy/jwpc19/manage-pond-services.sh start
~/projects/pond/deploy/jwpc19/manage-pond-services.sh stop
~/projects/pond/deploy/jwpc19/manage-pond-services.sh restart
```
