# gcweb1

Web host notes for Debian 12 on Google Cloud.

This folder is intended for nginx/static serving notes and host-specific deployment details.

Planned anonymous submission role:
- public ingress host for browser POSTs to /api/submit
- short-lived local queue if jwpc12 is unreachable
- immediate forwarder to jwpc12 when available

See also:
- deploy/gcweb1/systemd/
- deploy/gcweb1/nginx/
- deploy/DEPLOY.md
