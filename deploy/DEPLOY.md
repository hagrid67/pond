# Deployment Notes

## Host Layout
- deploy/jwpc19/: development host notes and helper docs
- deploy/jwpc12/: operational host files (systemd units/timers)
- deploy/gcweb1/: web host notes (nginx/static serving)

Using hostname subfolders keeps machine-specific settings separate and makes it clearer which files belong on which host.

## Environment Topology
- jwpc19
  - Ubuntu 24.04 in WSL2 on Windows 11
  - Primary development machine
- jwpc12
  - Native Ubuntu 24.04
  - Runs scheduled jobs for scrape, weather fetch, and publish
- gcweb1
  - Debian 12 on Google Cloud
  - Serves static site via nginx

## Current Scheduled Jobs (jwpc12)
- bookings scrape job
- weather fetch job
- publish generated bookings artefacts to gcweb1 runs via --rsync in the scrape job
- submission ingest API service for anonymous user input

## Current Scheduled Jobs (jwpc19)
- pond-dev-sync job
  - Pulls external data (bookings/weather inputs) from jwpc12 to keep the jwpc19 dev environment up to date.
  - Regenerates booking report and booking plots locally on jwpc19 after sync.
  - Runs every 5 minutes with no jitter.

## systemd Timer Approach
Use systemd timers instead of cron for scheduling, logging, and jitter support.

Random delay is configured with RandomizedDelaySec. For scrape, this is set to 3 minutes.

## User Units and Linger (No sudo Runtime)
Use user-level systemd units so daily operations do not require sudo.

User units live under ~/.config/systemd/user/ and are managed with systemctl --user.

To allow timers to run when jeremy is not logged in, enable linger for jeremy once:
- sudo loginctl enable-linger jeremy

Check linger status:
- loginctl show-user jeremy -p Linger

Note: enabling linger is typically a one-time admin action. After that, all timer lifecycle commands below can be run without sudo.

## Python Environment Convention

Use one shared pond venv per host (not per service), with Python minor in the name:
- `ve312pond` on Python 3.12 hosts
- `ve311pond` on Python 3.11 hosts

Install dependencies from the pinned repo spec:
- `python -m pip install -r requirements.txt`

Avoid service-specific ad hoc venvs (for example `.venv-submit-ingest`) once host venvs are in place.

## Anonymous Submission Architecture
Planned shape for anonymous pond-status submissions:

1. Browser on the public site sends POST requests to gcweb1 at /api/submit.
2. nginx on gcweb1 proxies /api/submit to a local Python API on 127.0.0.1:9000.
3. The gcweb1 edge API validates the payload, writes a short-lived local queue entry, and tries to forward the submission immediately to jwpc12.
4. nginx on jwpc12 exposes an internal-only ingest path and proxies it to a local Python API on 127.0.0.1:9100.
5. The jwpc12 ingest API stores the canonical record in the primary datastore.
6. If jwpc12 is temporarily unreachable, gcweb1 keeps the queued entry and a retry timer forwards it later.

Recommended initial storage:
- gcweb1: short-lived SQLite or JSONL queue used only for retry resilience
- jwpc12: primary SQLite database table for reporting and later sharing

Recommended minimal payload:
- submission type, for example slot-enforced
- value, for example yes/no/unsure or a small numeric score
- optional free-text note
- optional nickname if enabled later
- server-generated receipt timestamp
- submission UUID for deduplication between gcweb1 and jwpc12

Recommended Python services:
- gcweb1 edge submit API: pond.submit_edge_api:app via uvicorn on 127.0.0.1:9000
- gcweb1 forwarder worker: pond.submit_forwarder via a oneshot retry service
- jwpc12 ingest API: pond.submit_ingest_api:app via uvicorn on 127.0.0.1:9100

Current repo status:
- implemented: jwpc12 ingest API entrypoint pond.submit_ingest_api:app
- not yet implemented: gcweb1 edge API/forwarder entrypoints

## One-Command Host Deployment Scripts
These scripts perform all install/reload/enable/verify steps and are safe to re-run (idempotent):
- deploy/jwpc12/install-user-units.sh
- deploy/jwpc19/install-user-units.sh

Migration helper scripts:
- deploy/jwpc19/remove-old-units.sh
  - removes deprecated pond-rsync-data user units from ~/.config/systemd/user and disables them

What each script does:
- creates ~/.config/systemd/user if needed
- installs unit files from this repo into the user unit directory
- runs systemctl --user daemon-reload
- enables and starts required timers
- runs verification commands (list-timers and status)
- prints recent journal logs
- checks linger and reminds how to enable it if missing

### Installed Unit Files (in repo)
- deploy/jwpc12/systemd/pond-scrape.service
- deploy/jwpc12/systemd/pond-scrape.timer
- deploy/jwpc12/systemd/pond-submit-ingest.service
- deploy/jwpc12/systemd/pond-weather.service
- deploy/jwpc12/systemd/pond-weather.timer
- deploy/gcweb1/systemd/pond-pondupdate-api.service
- deploy/jwpc19/systemd/pond-dev-sync.service
- deploy/jwpc19/systemd/pond-dev-sync.timer
- deploy/jwpc19/systemd/pond-web-api.service
- deploy/jwpc19/systemd/pond-user-chart.service
- deploy/jwpc19/systemd/pond-user-chart.timer

Deprecated (kept in repo for migration reference):
- deploy/jwpc19/systemd/pond-rsync-data.service
- deploy/jwpc19/systemd/pond-rsync-data.timer

### nginx Config Files (in repo)
- deploy/gcweb1/nginx/http-pond-submit-rate-limit.conf
- deploy/gcweb1/nginx/site-pond-submit-api.conf
- deploy/gcweb1/nginx/site-pond-pondupdate-api.conf
- deploy/jwpc12/nginx/site-pond-submit-ingest.conf

## Deploy on jwpc12 (systemctl --user)
1. Run:
   - ~/projects/pond/deploy/jwpc12/install-user-units.sh
2. Optional manual verification:
   - systemctl --user list-timers | grep pond-
  - systemctl --user status pond-scrape.timer pond-weather.timer pond-submit-ingest.service
3. Install nginx config manually as root:
  - copy deploy/jwpc12/nginx/site-pond-submit-ingest.conf into the nginx site/include location used on jwpc12
  - set the allowed gcweb1 IP or CIDR in the config
  - test and reload nginx:
  - sudo nginx -t
  - sudo systemctl reload nginx

## Deploy on gcweb1 (systemctl --user)
1. Run:
  - ~/projects/pond/deploy/gcweb1/install-user-units.sh
2. Optional manual verification:
  - systemctl --user status pond-pondupdate-api.service
3. Install nginx config manually as root:
  - add deploy/gcweb1/nginx/http-pond-submit-rate-limit.conf in the nginx http block include path
  - add deploy/gcweb1/nginx/site-pond-pondupdate-api.conf in the server/site include path for the pond site
  - test and reload nginx:
  - sudo nginx -t
  - sudo systemctl reload nginx

## Deploy on jwpc19 (systemctl --user)
1. Run:
  - ~/projects/pond/deploy/jwpc19/remove-old-units.sh
2. Run:
   - ~/projects/pond/deploy/jwpc19/install-user-units.sh
3. Optional manual verification:
  - systemctl --user list-timers | grep pond-dev-sync
  - systemctl --user status pond-dev-sync.timer pond-dev-sync.service pond-web-api.service pond-user-chart.timer pond-user-chart.service
4. Simple local management command (no ssh):
  - ~/projects/pond/deploy/jwpc19/manage-pond-services.sh [start|stop|restart|status]

## Script Entrypoints
- scrape + publish: scripts/run_scrape_xnl.sh --scrape --headless --filters --rsync
- weather: scripts/fetch-weather.sh
- publish helper (called by scrape runner): scripts/pond-rsync.sh
  - syncs generated artefacts only: bookings.html, bookings-meta.json, booking-plot-*.png
- jwpc19 dev sync: scripts/pond-dev-sync.sh

## Planned Submission Service Ports
- gcweb1 edge API: 127.0.0.1:9000
- jwpc12 ingest API: 127.0.0.1:9100
