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
- publish to gcweb1 runs via --rsync in the scrape job

## Current Scheduled Jobs (jwpc19)
- pond-rsync-data job
  - Pulls bookings/weather data from jwpc12 to keep the jwpc19 dev environment up to date.
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

## One-Command Host Deployment Scripts
These scripts perform all install/reload/enable/verify steps and are safe to re-run (idempotent):
- deploy/jwpc12/install-user-units.sh
- deploy/jwpc19/install-user-units.sh

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
- deploy/jwpc12/systemd/pond-weather.service
- deploy/jwpc12/systemd/pond-weather.timer
- deploy/jwpc19/systemd/pond-rsync-data.service
- deploy/jwpc19/systemd/pond-rsync-data.timer

## Deploy on jwpc12 (systemctl --user)
1. Run:
   - ~/projects/pond/deploy/jwpc12/install-user-units.sh
2. Optional manual verification:
   - systemctl --user list-timers | grep pond-
   - systemctl --user status pond-scrape.timer pond-weather.timer

## Deploy on jwpc19 (systemctl --user)
1. Run:
   - ~/projects/pond/deploy/jwpc19/install-user-units.sh
2. Optional manual verification:
   - systemctl --user list-timers | grep pond-rsync-data
   - systemctl --user status pond-rsync-data.timer pond-rsync-data.service

## Script Entrypoints
- scrape + publish: scripts/run_scrape_xnl.sh --scrape --headless --filters --rsync
- weather: scripts/fetch-weather.sh
- publish helper (called by scrape runner): scripts/pond-rsync.sh
- jwpc19 data pull: scripts/pond-rsync-data.sh
