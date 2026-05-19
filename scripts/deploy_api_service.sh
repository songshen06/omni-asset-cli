#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICE_VENV="${SERVICE_VENV:-${REPO_ROOT}/.venv-api}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_EXTRAS="${INSTALL_EXTRAS:-api}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.omni-asset-service}"
STORAGE_ROOT="${OMNI_SERVICE_STORAGE_ROOT:-${REPO_ROOT}/out/omni-asset-service}"
API_KEYS="${OMNI_SERVICE_API_KEYS:-dev-secret:tenant_a:project_a}"
ISAAC_CONTAINERS="${ISAAC_CONTAINERS:-isaac-sim}"
DOCKER_WORKSPACE="${DOCKER_WORKSPACE:-/workspace/omni-asset-cli}"
DOCKER_PYTHON="${DOCKER_PYTHON:-/isaac-sim/python.sh}"
JOB_TIMEOUT_SECONDS="${OMNI_SERVICE_JOB_TIMEOUT_SECONDS:-7200}"
WRITE_ENV=0
VERIFY_ONLY=0

log() {
  printf '[omni-asset-service] %s\n' "$*"
}

die() {
  printf '[omni-asset-service] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_api_service.sh [options]

Options:
  --venv PATH             Virtualenv path. Default: .venv-api
  --python PATH           Python used to create the venv. Default: python3
  --extras EXTRAS         Package extras to install. Default: api
                          Use api,validator if this host also runs validator flows.
  --write-env             Write an env file with service defaults.
  --env-file PATH         Env file path for --write-env. Default: .env.omni-asset-service
  --verify-only           Do not install; only verify imports and entry point.
  -h, --help              Show this help.

Environment overrides:
  SERVICE_VENV, PYTHON_BIN, INSTALL_EXTRAS, ENV_FILE,
  OMNI_SERVICE_STORAGE_ROOT, OMNI_SERVICE_API_KEYS,
  ISAAC_CONTAINERS, DOCKER_WORKSPACE, DOCKER_PYTHON,
  OMNI_SERVICE_JOB_TIMEOUT_SECONDS.

Typical deployment:
  scripts/deploy_api_service.sh --write-env
  source .env.omni-asset-service
  .venv-api/bin/omni-asset-service --host 0.0.0.0 --port 8000
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      SERVICE_VENV="${2:?missing value for --venv}"
      shift
      ;;
    --python)
      PYTHON_BIN="${2:?missing value for --python}"
      shift
      ;;
    --extras)
      INSTALL_EXTRAS="${2:?missing value for --extras}"
      shift
      ;;
    --write-env)
      WRITE_ENV=1
      ;;
    --env-file)
      ENV_FILE="${2:?missing value for --env-file}"
      shift
      ;;
    --verify-only)
      VERIFY_ONLY=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

write_env_file() {
  log "writing ${ENV_FILE}"
  cat >"${ENV_FILE}" <<EOF
export OMNI_SERVICE_STORAGE_ROOT="${STORAGE_ROOT}"
export OMNI_SERVICE_API_KEYS="${API_KEYS}"
export ISAAC_CONTAINERS="${ISAAC_CONTAINERS}"
export DOCKER_WORKSPACE="${DOCKER_WORKSPACE}"
export DOCKER_PYTHON="${DOCKER_PYTHON}"
export OMNI_SERVICE_JOB_TIMEOUT_SECONDS="${JOB_TIMEOUT_SECONDS}"
export OMNI_SERVICE_START_WORKER=1
EOF
}

install_service() {
  require_command "${PYTHON_BIN}"
  if [[ ! -x "${SERVICE_VENV}/bin/python" ]]; then
    log "creating virtualenv at ${SERVICE_VENV}"
    "${PYTHON_BIN}" -m venv "${SERVICE_VENV}"
  fi

  log "upgrading pip tooling"
  "${SERVICE_VENV}/bin/python" -m pip install --upgrade pip setuptools wheel

  log "installing omni-asset-cli service extras: .[${INSTALL_EXTRAS}]"
  "${SERVICE_VENV}/bin/python" -m pip install --no-build-isolation -e "${REPO_ROOT}[${INSTALL_EXTRAS}]"
}

verify_service() {
  [[ -x "${SERVICE_VENV}/bin/python" ]] || die "Virtualenv Python not found: ${SERVICE_VENV}/bin/python"
  "${SERVICE_VENV}/bin/python" - <<'PY'
import importlib.util
import sys

required = ["fastapi", "uvicorn", "multipart", "pydantic", "omni_asset_service"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    print("missing imports:", ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
print("api dependencies: ok")
PY
  "${SERVICE_VENV}/bin/omni-asset-service" --help >/dev/null
  log "entry point: ok"
}

if [[ "${VERIFY_ONLY}" -eq 0 ]]; then
  install_service
fi

if [[ "${WRITE_ENV}" -eq 1 ]]; then
  write_env_file
fi

verify_service

log "ready"
