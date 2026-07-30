# gcweb1

Web host notes for Debian 12 on Google Cloud.

This folder is intended for nginx/static serving notes and host-specific deployment details.

Current pond update role:
- public ingress host for browser POSTs to /api/pondupdate
- handles user auth/register routes under /api/auth/*
- reverse proxy from nginx to local uvicorn on 127.0.0.1:9000
- local API service via `pond.pond_web_api` (updates + auth)
- local JSONL logging (`user-updates/user-updates-yymmdd.jsonl`, daily rolling)

See also:
- deploy/gcweb1/systemd/
- deploy/gcweb1/nginx/
- deploy/DEPLOY.md
