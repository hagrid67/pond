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

### Prompt
Please append this prompt and the response onto the planning-log.  Duplicate the response here in the chat.

I guess we might want different behaviour for git on the dev host jwpc19, in case there are uncommitted changes when we run the deploy: I think it should just fail.  Perhaps it already does this? 

Also, if there are upstream commits not present on the dev host, do we want to ff pull them?  or just fail?  I occasionally commit changes on another host.  Is it safe to ff pull them on the dev host?  Give me your thoughts.  FWIW I am trying to "aggressively" commit small changes wherever they are made so that the local copies do not diverge.

### Response
Short answer:
- Dirty working tree on jwpc19: yes, this should fail, and it already does.
- Upstream commits missing locally: fast-forward pull is usually the right default for your workflow, with one operational caveat.

What the current script already does:
- In deploy mode, before pull, it checks for a dirty worktree via git status --porcelain and fails deploy if anything is uncommitted.
- It requires an upstream tracking branch.
- It then runs git pull --ff-only, so it will only move forward without merge commits.
- If histories diverge, ff-only fails, which is a good safety stop.

So your first concern is already implemented exactly as you described: uncommitted changes block deploy.

Thoughts on ff pull vs fail when upstream is ahead:
- For your stated habit (frequent small commits on whichever host you are on), ff pull on jwpc19 is a good fit.
- It is safe in the Git-history sense: ff-only never rewrites local commits and never creates a merge commit.
- It also reduces host drift, which is exactly what you are trying to prevent.

The caveat:
- Auto-pulling means deployment can advance to commits you did not just review on jwpc19 at that moment.
- That is often fine, but operationally it can feel less explicit.

Practical recommendation:
- Keep current default behavior (clean-tree required + ff-only pull).
- Continue your aggressive small-commit discipline.
- If you want stricter release control later, add an opt-in guard such as:
  - "fail if local HEAD is behind upstream" unless --allow-pull is passed, or
  - a --no-pull mode that requires jwpc19 to already be up to date.

Given your workflow, I would not switch to always-fail-on-behind right now. The current policy is the right balance of safety and low friction.

### Prompt
Please append this prompt and the response onto the planning-log.  Duplicate the response here in the chat.

The first run of  `run-deploy.sh --jwpc12 --check` failed because the run-deploy script does not yet exist on the remote host.  I think it's fair enough that I do a manual git pull for the first time to install it.  However it raises the question of how changes to run-deploy.sh are handled - the local dev version may differ from the remote one.  Should we provide for a double invocation, where the first invoke does some initial checks and the git pull, and then the  second invocation runs the script remotely "for real"?  What initial sanity checks should we run the first time on the remote?

### Response
This is a good catch, and yes, it is worth designing explicitly.

Short recommendation:
- Keep your manual first-time bootstrap as acceptable.
- Add a controller-side bootstrap path so future first-runs are automatic.
- Use a two-phase remote flow, but inside one local command invocation (not requiring the operator to run the command twice).

Why the current failure happens:
- The controller currently assumes scripts/run-deploy.sh already exists remotely.
- On an uninitialized host, ssh can connect, but the remote script path is missing, so execution fails before remote checks can run.

How to handle script drift safely:
- Prefer "remote host self-updates from Git" over copying the local script via scp.
- This keeps all hosts aligned to committed history, and avoids running an uncommitted local variant remotely.
- If local working tree is dirty on jwpc19, deploy already fails before pull, which is the right safety behavior.

Proposed execution model (single command, two phases):
1. Bootstrap phase (controller runs lightweight remote shell block):
   - Verify remote repo directory exists (or fail with clear message).
   - Verify remote git is available.
   - cd to repo and verify branch/upstream basics.
   - Optionally check remote worktree cleanliness (recommended default: require clean).
   - Run git fetch --prune and git pull --ff-only.
   - Confirm scripts/run-deploy.sh now exists and is executable.
2. Execution phase:
   - Invoke remote scripts/run-deploy.sh --local --host-id <host> [--check|deploy].

This gives you the double-invocation behavior logically, while remaining one operator command.

First-time remote sanity checks to include:
- SSH identity:
  - Print hostname, user, and pwd at session start.
- Repo presence:
  - Ensure ~/projects/pond exists and is a git repo.
- Branch/upstream:
  - Print current branch, HEAD, upstream.
  - Fail if upstream missing.
- Cleanliness policy:
  - Fail if git status --porcelain is non-empty.
  - If you later want flexibility, add explicit override flag (for example --allow-dirty-remote) but default should stay fail.
- Fast-forward only:
  - Require git pull --ff-only; fail on divergence.
- Script presence:
  - test -x scripts/run-deploy.sh after pull.
- Basic prerequisites:
  - command -v systemctl, crontab, git.
  - Optional: systemctl --user is-system-running or a benign status probe, mainly to surface user-session issues early.

Policy decision for differing local vs remote run-deploy.sh:
- Best policy: remote always runs the committed version at its current checked-out commit after ff pull.
- Do not run local uncommitted script content on remote hosts.
- This enforces your "aggressive small commits" workflow and keeps behavior reproducible.

Operationally, this means:
- If you edit run-deploy.sh locally, commit and push first.
- Then run deploy; bootstrap phase pulls that commit remotely; execution phase uses that exact committed script.

If you want, next step can be to implement this as a dedicated bootstrap helper in the controller path (for non-jwpc19 targets) so first-run and normal-run share the same command UX.

### Prompt
Can I check what you mean for the first phase: do you mean pass the commands directly in ssh, rather than attempting to run whatever version of the script is present on the remote host?
This is OK; but my experience has been it can be fragile to run too many commands in an ssh.  Would it be better to have a second script, maybe "deploy-bootstrap.sh", present on all the hosts?  The idea being that this script is kept simple and rarely changes, whereas the main run-deploy.sh is where most new behaviour is added.
Or is this too fussy?

Please append the query and response into the planning log.

### Response
Yes, exactly: for phase 1 I meant running a small bootstrap command block over ssh directly, before invoking the main script.

Your concern is valid. A long inline ssh command can become fragile and hard to maintain. A small dedicated bootstrap script is not too fussy here, it is a good design choice.

Recommendation:
- Add a second script at scripts/deploy-bootstrap.sh.
- Keep it intentionally narrow and stable.
- Controller flow becomes:
  1. ssh host and run scripts/deploy-bootstrap.sh (or bootstrap fallback if missing).
  2. then run scripts/run-deploy.sh --local --host-id <host> with check or deploy mode.

Why this is better:
- Less shell quoting complexity in ssh invocations.
- Easier to test bootstrap logic independently.
- Clear separation of concerns:
  - deploy-bootstrap.sh: repo/upstream/cleanliness/ff-pull/script-presence checks.
  - run-deploy.sh: orchestration, unit install/reconcile, reporting.
- Lower churn risk: bootstrap can remain small and rarely changed.

Suggested bootstrap responsibilities:
- Verify repo path exists and is a git repository.
- Verify required commands exist (git, bash).
- Print branch, head, upstream.
- Fail if upstream missing.
- Fail on dirty worktree by default.
- Run git fetch --prune and git pull --ff-only.
- Verify scripts/run-deploy.sh exists after pull.

A pragmatic hybrid is best:
- Primary path: call scripts/deploy-bootstrap.sh remotely.
- First-run fallback: if bootstrap script is absent, run a minimal inline ssh bootstrap that only updates repo enough to obtain deploy-bootstrap.sh, then re-run bootstrap script.

So no, this is not over-engineering in your setup. It is a sensible reliability upgrade for multi-host operations.
