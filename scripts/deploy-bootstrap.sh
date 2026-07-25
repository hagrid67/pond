#!/usr/bin/env bash
set -euo pipefail

HOST_ID=""
REPO_SUBPATH="projects/pond"

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
  echo "[deploy-bootstrap] $*"
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

  local repo_dir
  repo_dir="${HOME}/${REPO_SUBPATH}"

  log "host_id=${HOST_ID:-unknown} hostname=$(hostname -s 2>/dev/null || hostname) user=${USER}"

  if ! command -v git >/dev/null 2>&1; then
    echo "Error: missing required command: git" >&2
    exit 1
  fi

  if ! command -v bash >/dev/null 2>&1; then
    echo "Error: missing required command: bash" >&2
    exit 1
  fi

  if [[ ! -d "${repo_dir}" ]]; then
    echo "Error: missing repo directory: ${repo_dir}" >&2
    exit 1
  fi

  cd "${repo_dir}"

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: ${repo_dir} is not a git repository" >&2
    exit 1
  fi

  log "Git state before pull: $(git_state_report)"

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: working tree is not clean; refusing bootstrap pull." >&2
    exit 1
  fi

  if ! git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
    echo "Error: no upstream tracking branch configured for current branch." >&2
    exit 1
  fi

  git fetch --prune
  git pull --ff-only

  if [[ ! -f scripts/run-deploy.sh ]]; then
    echo "Error: missing scripts/run-deploy.sh after pull." >&2
    exit 1
  fi

  log "Git state after pull: $(git_state_report)"
  return 0
}

main "$@"
