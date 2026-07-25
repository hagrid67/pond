#!/usr/bin/env bash
set -euo pipefail

HOST_ID=""
REPO_SUBPATH="projects/pond"
NO_PULL=0

COLOR_RED=""
COLOR_GREEN=""
COLOR_YELLOW=""
COLOR_BLUE=""
COLOR_RESET=""

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy-bootstrap.sh [--host-id HOST] [--repo-subpath PATH] [--no-pull]

Options:
  --host-id       Optional host identifier for logging.
  --repo-subpath  Repo path under $HOME. Default: projects/pond
  --no-pull       Run bootstrap checks but skip git pull.
  -h, --help      Show this help.
EOF
}

log() {
  echo "${COLOR_BLUE}[deploy-bootstrap]${COLOR_RESET} $*"
}

status_ok() {
  echo "${COLOR_GREEN}[OK]${COLOR_RESET} $*"
}

status_error() {
  echo "${COLOR_RED}[ERROR]${COLOR_RESET} $*" >&2
}

status_warn() {
  echo "${COLOR_YELLOW}[WARN]${COLOR_RESET} $*"
}

init_colors() {
  if [[ -n "${NO_COLOR:-}" ]]; then
    return 0
  fi

  if [[ -n "${FORCE_COLOR:-}" || -t 1 || -n "${SSH_CONNECTION:-}" ]]; then
    COLOR_RED=$'\033[31m'
    COLOR_GREEN=$'\033[32m'
    COLOR_YELLOW=$'\033[33m'
    COLOR_BLUE=$'\033[36m'
    COLOR_RESET=$'\033[0m'
  fi
}

parse_args() {
  while (($#)); do
    case "$1" in
      --host-id)
        shift
        if (($# == 0)); then
          echo "Error: --host-id requires a value." >&2
          exit 2
        fi
        HOST_ID="$1"
        ;;
      --repo-subpath)
        shift
        if (($# == 0)); then
          echo "Error: --repo-subpath requires a value." >&2
          exit 2
        fi
        REPO_SUBPATH="$1"
        ;;
      --no-pull)
        NO_PULL=1
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

git_state_report() {
  local branch head upstream
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  head="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "(none)")"
  echo "branch=${branch} head=${head} upstream=${upstream}"
}

main() {
  parse_args "$@"
  init_colors

  local repo_dir
  repo_dir="${HOME}/${REPO_SUBPATH}"

  log "host_id=${HOST_ID:-unknown} hostname=$(hostname -s 2>/dev/null || hostname) user=${USER}"
  if [[ ${NO_PULL} -eq 1 ]]; then
    status_warn "--no-pull enabled: bootstrap will not run git pull"
  fi

  if ! command -v git >/dev/null 2>&1; then
    status_error "missing required command: git"
    exit 1
  fi

  if ! command -v bash >/dev/null 2>&1; then
    status_error "missing required command: bash"
    exit 1
  fi

  if [[ ! -d "${repo_dir}" ]]; then
    status_error "missing repo directory: ${repo_dir}"
    exit 1
  fi

  cd "${repo_dir}"

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    status_error "${repo_dir} is not a git repository"
    exit 1
  fi

  log "Git state before pull: $(git_state_report)"

  if [[ -n "$(git status --porcelain)" ]]; then
    status_error "working tree is not clean; refusing bootstrap pull"
    exit 1
  fi

  if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
    status_error "no upstream tracking branch configured for current branch"
    exit 1
  fi

  git fetch --prune
  if [[ ${NO_PULL} -eq 1 ]]; then
    local divergence ahead behind
    divergence="$(git rev-list --left-right --count HEAD...@{u} 2>/dev/null || echo "0 0")"
    read -r ahead behind <<<"${divergence}"
    if [[ "${behind}" =~ ^[0-9]+$ ]] && [[ ${behind} -gt 0 ]]; then
      status_warn "local copy is behind upstream by ${behind} commit(s)"
    else
      status_ok "local copy is not behind upstream (ahead=${ahead} behind=${behind})"
    fi
  else
    git pull --ff-only
  fi

  if [[ ! -f scripts/run-deploy.sh ]]; then
    status_error "missing scripts/run-deploy.sh after pull"
    exit 1
  fi

  log "Git state after pull: $(git_state_report)"
  if [[ ${NO_PULL} -eq 1 ]]; then
    status_ok "bootstrap checks completed (pull skipped)"
  else
    status_ok "bootstrap checks and pull completed"
  fi
  return 0
}

main "$@"
