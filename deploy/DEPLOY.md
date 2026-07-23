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

### Installed Unit Files (in repo)
- deploy/jwpc12/systemd/pond-scrape.service
- deploy/jwpc12/systemd/pond-scrape.timer
- deploy/jwpc12/systemd/pond-weather.service
- deploy/jwpc12/systemd/pond-weather.timer
- deploy/jwpc19/systemd/pond-rsync-data.service
- deploy/jwpc19/systemd/pond-rsync-data.timer

## Suggested Install Steps on jwpc12
1. Copy unit files to /etc/systemd/system/.
2. Reload systemd:
   - sudo systemctl daemon-reload
3. Enable and start timers:
   - sudo systemctl enable --now pond-scrape.timer
   - sudo systemctl enable --now pond-weather.timer
4. Verify:
   - systemctl list-timers | grep pond-
  - systemctl status pond-scrape.timer pond-weather.timer

## Suggested Install Steps on jwpc19
1. Copy unit files to /etc/systemd/system/.
2. Reload systemd:
  - sudo systemctl daemon-reload
3. Enable and start timer:
  - sudo systemctl enable --now pond-rsync-data.timer
4. Verify:
  - systemctl list-timers | grep pond-rsync-data
  - systemctl status pond-rsync-data.timer pond-rsync-data.service

## Script Entrypoints
- scrape + publish: scripts/run_scrape_xnl.sh --scrape --headless --filters --rsync
- weather: scripts/fetch-weather.sh
- publish helper (called by scrape runner): scripts/pond-rsync.sh
- jwpc19 data pull: scripts/pond-rsync-data.sh
