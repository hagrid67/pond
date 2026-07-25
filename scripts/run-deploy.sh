#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INVENTORY_FILE="${REPO_ROOT}/deploy/inventory/hosts-units.sh"

if [[ ! -f "${INVENTORY_FILE}" ]]; then
  echo "Error: missing inventory file: ${INVENTORY_FILE}" >&2
  exit 2
fi

# shellcheck source=/dev/null
source "${INVENTORY_FILE}"

CHECK_ONLY=0
LOCAL_MODE=0
VERBOSE=0
HOST_ID_OVERRIDE=""

TARGET_JWPC19=0
TARGET_JWPC12=0
TARGET_GCWEB1=0

FAIL_COUNT=0
CHECK_FAIL_COUNT=0
DEPLOY_FAIL_COUNT=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run-deploy.sh [--check] [--jwpc19|--dev] [--jwpc12] [--gcweb1]
  scripts/run-deploy.sh [--check] --local [--host-id HOST]

Options:
  --check      Run checks only (skip deploy actions).
  --jwpc19     Target jwpc19 host.
  --dev        Alias for --jwpc19.
  --jwpc12     Target jwpc12 host.
  --gcweb1     Target gcweb1 host.
  --local      Run on current host without ssh.
  --host-id    Internal override for local host identity (jwpc19|jwpc12|gcweb1).
  --verbose    Print additional progress messages.
  -h, --help   Show this help.

Notes:
  - Without --local, at least one host flag is required.
  - In deploy mode (default), deploy actions are run first, then checks.
  - In check mode (--check), deploy actions are skipped.
EOF
}

log() {
  echo "[run-deploy] $*"
}

vlog() {
  if [[ ${VERBOSE} -eq 1 ]]; then
    echo "[run-deploy][verbose] $*"
  fi
}

record_failure() {
  local category="$1"
  local host_id="$2"
  local msg="$3"
  echo "[run-deploy][${category}] ${host_id}: ${msg}" >&2
  FAIL_COUNT=$((FAIL_COUNT + 1))
  if [[ "${category}" == "check" ]]; then
    CHECK_FAIL_COUNT=$((CHECK_FAIL_COUNT + 1))
  elif [[ "${category}" == "deploy" ]]; then
    DEPLOY_FAIL_COUNT=$((DEPLOY_FAIL_COUNT + 1))
  fi
}

require_host_id_valid() {
  local host_id="$1"
  case "${host_id}" in
    jwpc19|jwpc12|gcweb1) return 0 ;;
    *) return 1 ;;
  esac
}

infer_local_host_id() {
  local short
  short="$(hostname -s 2>/dev/null || hostname)"
  case "${short}" in
    jwpc19) echo "jwpc19" ;;
    jwpc12) echo "jwpc12" ;;
    gcweb1) echo "gcweb1" ;;
    *) return 1 ;;
  esac
}

parse_args() {
  while (($#)); do
    case "$1" in
      --check)
        CHECK_ONLY=1
        ;;
      --local)
        LOCAL_MODE=1
        ;;
      --jwpc19|--dev)
        TARGET_JWPC19=1
        ;;
      --jwpc12)
        TARGET_JWPC12=1
        ;;
      --gcweb1)
        TARGET_GCWEB1=1
        ;;
      --host-id)
        shift
        if (($# == 0)); then
          echo "Error: --host-id requires a value." >&2
          exit 2
        fi
        HOST_ID_OVERRIDE="$1"
        ;;
      --verbose)
        VERBOSE=1
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "Error: unknown option: $1" >&2
        usage >&2
        exit 2
        ;;
    esac
    shift
  done
}

host_targets_csv() {
  local targets=()
  [[ ${TARGET_JWPC19} -eq 1 ]] && targets+=("jwpc19")
  [[ ${TARGET_JWPC12} -eq 1 ]] && targets+=("jwpc12")
  [[ ${TARGET_GCWEB1} -eq 1 ]] && targets+=("gcweb1")
  (IFS=","; echo "${targets[*]}")
}

ensure_clean_worktree() {
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is not clean; refusing deploy pull." >&2
    return 1
  fi
  return 0
}

git_state_report() {
  local branch head upstream
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  head="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "(none)")"
  echo "branch=${branch} head=${head} upstream=${upstream}"
}

run_git_pull_with_checks() {
  log "Git state before pull: $(git_state_report)"

  if ! ensure_clean_worktree; then
    return 1
  fi

  if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
    echo "No upstream tracking branch configured for current branch." >&2
    return 1
  fi

  git fetch --prune
  git pull --ff-only
  log "Git state after pull: $(git_state_report)"
  return 0
}

reconcile_deprecated_units() {
  local host_id="$1"
  local deprecated_raw
  deprecated_raw="$(host_deprecated_units "${host_id}" || true)"
  if [[ -z "${deprecated_raw}" ]]; then
    vlog "No deprecated units listed for ${host_id}."
    return 0
  fi

  local unit
  for unit in ${deprecated_raw}; do
    vlog "Reconciling deprecated unit ${unit}"
    systemctl --user stop "${unit}" >/dev/null 2>&1 || true
    systemctl --user disable "${unit}" >/dev/null 2>&1 || true
    systemctl --user reset-failed "${unit}" >/dev/null 2>&1 || true

    rm -f "${HOME}/.config/systemd/user/${unit}" || true
    rm -f "${HOME}/.config/systemd/user/timers.target.wants/${unit}" || true
    rm -f "${HOME}/.config/systemd/user/default.target.wants/${unit}" || true
  done

  systemctl --user daemon-reload
  return 0
}

run_local_deploy() {
  local host_id="$1"
  local install_script remove_script

  install_script="$(host_install_script "${host_id}")"
  remove_script="$(host_remove_script "${host_id}")"

  log "Starting deploy on ${host_id}"

  if ! run_git_pull_with_checks; then
    record_failure "deploy" "${host_id}" "git pull checks failed"
    return 1
  fi

  if [[ -n "${remove_script}" && -x "${remove_script}" ]]; then
    log "Running migration cleanup script: ${remove_script}"
    if ! "${remove_script}"; then
      record_failure "deploy" "${host_id}" "migration cleanup failed"
    fi
  fi

  if ! reconcile_deprecated_units "${host_id}"; then
    record_failure "deploy" "${host_id}" "deprecated unit reconciliation failed"
  fi

  if [[ ! -x "${install_script}" ]]; then
    record_failure "deploy" "${host_id}" "missing or non-executable install script: ${install_script}"
    return 1
  fi

  if ! "${install_script}"; then
    record_failure "deploy" "${host_id}" "install-user-units script failed"
    return 1
  fi

  log "Deploy completed on ${host_id}"
  return 0
}

run_crontab_check() {
  echo "--- crontab -l (${USER}) ---"
  if crontab -l 2>/tmp/pond-crontab.err; then
    :
  else
    local err
    err="$(cat /tmp/pond-crontab.err 2>/dev/null || true)"
    if [[ "${err}" == *"no crontab for"* ]]; then
      echo "(no crontab for ${USER})"
    else
      echo "(error reading crontab) ${err}" >&2
      rm -f /tmp/pond-crontab.err
      return 1
    fi
  fi
  rm -f /tmp/pond-crontab.err
  return 0
}

read_unit_state() {
  local mode="$1"
  local unit="$2"
  local out
  out="$(systemctl --user "${mode}" "${unit}" 2>/dev/null || true)"
  out="${out%%$'\n'*}"
  if [[ -z "${out}" ]]; then
    echo "unknown"
  else
    echo "${out}"
  fi
}

run_local_checks() {
  local host_id="$1"
  local expected_raw deprecated_raw unit active enabled

  log "Starting checks on ${host_id}"
  echo "=== host identity ==="
  echo "host_id=${host_id} hostname=$(hostname -s 2>/dev/null || hostname) user=${USER} cwd=$(pwd)"

  echo "=== git state ==="
  echo "$(git_state_report)"
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "worktree=dirty"
  else
    echo "worktree=clean"
  fi

  echo "=== expected units ==="
  expected_raw="$(host_expected_units "${host_id}")"
  for unit in ${expected_raw}; do
    active="$(read_unit_state is-active "${unit}")"
    enabled="$(read_unit_state is-enabled "${unit}")"
    echo "${unit}: active=${active} enabled=${enabled}"
    if [[ "${active}" == "unknown" || "${enabled}" == "unknown" ]]; then
      record_failure "check" "${host_id}" "unable to resolve unit state for ${unit}"
    fi
  done

  echo "=== deprecated units ==="
  deprecated_raw="$(host_deprecated_units "${host_id}" || true)"
  if [[ -z "${deprecated_raw}" ]]; then
    echo "(none)"
  else
    for unit in ${deprecated_raw}; do
      if systemctl --user list-unit-files "${unit}" --no-legend 2>/dev/null | grep -q "${unit}"; then
        echo "${unit}: present"
      else
        echo "${unit}: absent"
      fi
    done
  fi

  echo "=== installed pond-* unit files ==="
  systemctl --user list-unit-files --no-legend | grep -E '^pond-.*\.(service|timer|target)\s' || echo "(none)"

  echo "=== cron audit ==="
  if ! run_crontab_check; then
    record_failure "check" "${host_id}" "crontab check failed"
  fi

  log "Checks completed on ${host_id}"
  return 0
}

run_local_mode() {
  local host_id="${HOST_ID_OVERRIDE}"

  if [[ -z "${host_id}" ]]; then
    if ! host_id="$(infer_local_host_id)"; then
      echo "Error: unable to infer host id from hostname; use --host-id." >&2
      return 2
    fi
  fi

  if ! require_host_id_valid "${host_id}"; then
    echo "Error: invalid --host-id value: ${host_id}" >&2
    return 2
  fi

  local repo_subpath
  repo_subpath="$(host_repo_subpath "${host_id}")"
  cd "${HOME}/${repo_subpath}"

  if [[ ${CHECK_ONLY} -eq 0 ]]; then
    run_local_deploy "${host_id}" || true
  fi
  run_local_checks "${host_id}" || true

  return 0
}

run_remote_host() {
  local host_id="$1"
  local ssh_target cmd
  ssh_target="$(host_ssh_target "${host_id}")"

  cmd="cd ~/projects/pond && bash scripts/run-deploy.sh --local --host-id ${host_id}"
  if [[ ${CHECK_ONLY} -eq 1 ]]; then
    cmd+=" --check"
  fi
  if [[ ${VERBOSE} -eq 1 ]]; then
    cmd+=" --verbose"
  fi

  log "Remote ${host_id}: ssh ${ssh_target}"
  if ! ssh "${ssh_target}" "${cmd}"; then
    local mode
    mode="deploy"
    [[ ${CHECK_ONLY} -eq 1 ]] && mode="check"
    record_failure "${mode}" "${host_id}" "remote execution failed"
  fi
}

run_controller_mode() {
  local selected=()
  [[ ${TARGET_JWPC19} -eq 1 ]] && selected+=("jwpc19")
  [[ ${TARGET_JWPC12} -eq 1 ]] && selected+=("jwpc12")
  [[ ${TARGET_GCWEB1} -eq 1 ]] && selected+=("gcweb1")

  if [[ ${#selected[@]} -eq 0 ]]; then
    echo "Error: no host targets selected. Provide --jwpc19/--jwpc12/--gcweb1." >&2
    usage >&2
    return 2
  fi

  log "Selected targets: ${selected[*]}"
  log "Mode: $([[ ${CHECK_ONLY} -eq 1 ]] && echo check-only || echo deploy+check)"

  local host_id
  for host_id in "${selected[@]}"; do
    if [[ "${host_id}" == "jwpc19" ]]; then
      bash "${SCRIPT_DIR}/run-deploy.sh" --local --host-id jwpc19 $([[ ${CHECK_ONLY} -eq 1 ]] && echo --check) $([[ ${VERBOSE} -eq 1 ]] && echo --verbose) || {
        local mode
        mode="deploy"
        [[ ${CHECK_ONLY} -eq 1 ]] && mode="check"
        record_failure "${mode}" "${host_id}" "local execution failed"
      }
    else
      run_remote_host "${host_id}"
    fi
  done

  return 0
}

print_summary() {
  echo
  echo "=== deploy summary ==="
  echo "check_only=${CHECK_ONLY} local_mode=${LOCAL_MODE}"
  echo "total_failures=${FAIL_COUNT} deploy_failures=${DEPLOY_FAIL_COUNT} check_failures=${CHECK_FAIL_COUNT}"
}

main() {
  parse_args "$@"

  if [[ ${LOCAL_MODE} -eq 1 ]]; then
    run_local_mode || {
      print_summary
      exit 2
    }
  else
    run_controller_mode || {
      print_summary
      exit 2
    }
  fi

  print_summary
  if [[ ${FAIL_COUNT} -gt 0 ]]; then
    exit 1
  fi
  exit 0
}

main "$@"
