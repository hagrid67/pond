# Planning Log

## 2026-07-25

### Prompt
Plan this, do not implement yet.
Can you write this prompt and your response into a file <REPO_HOME>/docs/planning-log.md ?

I want  a script to deploy from dev ie this host, jwpc19.  It should take two args, --jwpc12 and --gcweb1, to indicate whether to deploy to each of those hosts.   I have ssh set up from jwpc19 to each of them.
I suggest that for each host, we ssh onto it, cd into ~/projects/pond, and do a git pull (with some checks).
We should also do a systemd install units.  Can you suggest a mechanism to handle the removal or renaming of systemd units, when necessary?  We could ensure all units include the string "pond" in their name.  Is there a way of grouping units?

I suggest the script could ssh to the remote host and run itself there, to then run the checks and deploy commands.

Can we also have a --check option, which checks what relevant user units are installed, and their state?
So for example
- run-deploy.sh --check --jwpc12 --gcweb1 would run the check on each remote host.
- run-deploy.sh --jwpc12 --gcweb1 would run the deploy on each host.  It should also run the check.  So in effect --check inhibits the script from running the deploy.

We need to maintain an inventory of which units run on which host.  Is there a mainstream name for this?

I want to migrate all ongoing activities from cron onto systemd.  Let's include a check of crontab for the main user (jeremy on jwpc19 and jwpc12, and jdhwatson_gmail_com on gcweb1 ) to confirm whether any crontabs are still active.  Do not attempt to edit crontabs.

We could also have a --jwpc19 or --dev arg, to run any checks or deployment steps on the dev host.  This would in this case not need to ssh. Can you suggest some naming conventions here - we could use an option like --local to just run the deploy locally, depending on which host this is.  Then when I run on jwpc19 run-deploy.sh --local it would redeploy the dev-sync unit to pull data from production.  But when I run --jwpc12 it sshs onto jwpc12 and then runs --local there?  Is that consistent?

Write the plan as above and we will discuss further.

### Response (Plan Only)
Yes, this is a good shape. The design is consistent, and the self-ssh pattern (script runs remotely with --local) is a strong approach for keeping logic centralized.

#### 1. Goal
Create one orchestrator script on jwpc19 that can:
- run checks only, or
- run deploy plus checks,
across selected hosts: jwpc19, jwpc12, gcweb1.

#### 2. Proposed Script Interface
Script name:
- scripts/run-deploy.sh

Primary flags:
- --jwpc19 (or alias --dev): include dev host target
- --jwpc12: include jwpc12 target
- --gcweb1: include gcweb1 target
- --local: execute actions on current host without ssh
- --check: check mode only (no deploy actions)
- --verbose: optional, for expanded logs
- --dry-run: optional later enhancement

Behavior:
- If --check is set: run checks only.
- If --check is not set: run deploy then checks.
- If remote flag is set (--jwpc12/--gcweb1), controller script sshes and invokes itself remotely with --local (plus --check if requested).

Example semantics:
- run-deploy.sh --check --jwpc12 --gcweb1
  - ssh to each host
  - run local checks only there
- run-deploy.sh --jwpc12 --gcweb1
  - ssh to each host
  - run deploy actions there
  - then run checks there
- run-deploy.sh --local
  - execute only on current host (jwpc19 when launched there)

This is consistent and keeps one code path.

#### 3. Mainstream Name for Unit/Host Mapping
Use:
- Host inventory (mainstream term, especially in config management)
- Service inventory or unit inventory (for systemd-focused mapping)

Recommended file:
- deploy/inventory/hosts-units.sh (shell source format), or
- deploy/inventory/hosts-units.yaml (if moving to structured parser later)

For bash-first simplicity, a shell inventory is easiest.

#### 4. Inventory Content (Planned)
Per host, maintain:
- ssh target
- repo path (default ~/projects/pond)
- expected active units
- deprecated units to remove/disable
- install script path

Example conceptual mapping:
- jwpc19:
  - expected: pond-dev-sync.service, pond-dev-sync.timer
  - deprecated: pond-rsync-data.service, pond-rsync-data.timer
- jwpc12:
  - expected: pond-scrape.timer, pond-weather.timer, pond-submit-ingest.service
- gcweb1:
  - expected: pond-pondupdate-api.service, pond-apitest.timer, pond-user-chart.timer

#### 5. Deploy Flow Per Host (Planned)
For each selected host:
1. Pre-check connectivity (for remote)
2. Ensure repo exists at expected path
3. git fetch + safety checks
4. git pull --ff-only
5. run host install script (for units)
6. run unit reconciliation step (deprecated cleanup)
7. run check report (status/timers/crontab)

Safety checks before pull:
- detect dirty working tree and fail with clear message
- print branch and HEAD
- optionally confirm upstream tracking branch exists

#### 6. Handling Unit Renames/Removals
Recommended mechanism:
- keep an explicit deprecated-units list per host in inventory
- reconciliation function does:
  - systemctl --user disable --now <unit> for each deprecated unit (ignore missing)
  - remove stale unit files/symlinks in ~/.config/systemd/user when applicable
  - systemctl --user daemon-reload
  - systemctl --user reset-failed for those units

This is better than broad wildcard removal and avoids accidental removal of unrelated pond units.

#### 7. Grouping Units in systemd
Native unit grouping options:
- target units (best fit for grouping)
  - e.g. pond-jwpc12.target, pond-gcweb1.target
  - units set PartOf=/WantedBy= that target
- naming convention (already good): all unit names start with pond-

Plan recommendation:
- start with inventory-driven grouping (simpler)
- optionally add per-host pond targets later if operationally useful

#### 8. Check Mode Output (Planned)
For each host, report:
- host identity: hostname, user, cwd
- git state:
  - branch
  - HEAD
  - dirty/clean
- systemd user units:
  - expected units: active/enabled status
  - deprecated units: present/absent status
  - list of installed pond-* unit files
- cron audit:
  - crontab -l for current user (jeremy on jwpc19/jwpc12, jdhwatson_gmail_com on gcweb1)
  - if no crontab, report explicitly

No edits to crontab; check only.

#### 9. Suggested Naming Conventions
Flags:
- keep explicit host flags: --jwpc19 --jwpc12 --gcweb1
- keep --local as execution mode
- optional alias: --dev => --jwpc19

Units:
- all managed units prefixed with pond-

Scripts:
- deploy/<host>/install-user-units.sh
- deploy/<host>/remove-old-units.sh (for migrations)

#### 10. Decision Notes / Open Questions
To settle before implementation:
- Should run-deploy.sh default to any host if no host flags are provided, or fail with usage?
  - recommended: fail and require explicit target selection
- Should check mode fail hard on first host error, or continue and summarize?
  - recommended: continue and summarize with nonzero exit at end
- Should git pull be blocked on non-fast-forward only?
  - recommended: yes, use --ff-only for safety

#### 11. Proposed Next Step (Discussion)
After agreement, implement in this order:
1. inventory file
2. run-deploy.sh skeleton with arg parsing and host selection
3. local check function
4. local deploy function
5. remote self-invocation wrapper
6. summary output and exit codes
