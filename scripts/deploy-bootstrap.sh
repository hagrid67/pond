#!/usr/bin/env bash
set -euo pipefail

HOST_ID=""
REPO_SUBPATH="projects/pond"

COLOR_RED=""
COLOR_GREEN=""
COLOR_BLUE=""
COLOR_RESET=""

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy-bootstrap.sh [--host-id HOST] [--repo-subpath PATH]

Options:
  --host-id       Optional host identifier for logging.
  --repo-subpath  Repo path under $HOME. Default: projects/pond
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

init_colors() {
  if [[ -n "${NO_COLOR:-}" ]]; then
    return 0
  fi

  if [[ -n "${FORCE_COLOR:-}" || -t 1 || -n "${SSH_CONNECTION:-}" ]]; then
    COLOR_RED=$'\033[31m'
    COLOR_GREEN=$'\033[32m'
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
  git pull --ff-only

  if [[ ! -f scripts/run-deploy.sh ]]; then
    status_error "missing scripts/run-deploy.sh after pull"
    exit 1
  fi

  log "Git state after pull: $(git_state_report)"
  status_ok "bootstrap checks and pull completed"
  return 0
}

main "$@"
