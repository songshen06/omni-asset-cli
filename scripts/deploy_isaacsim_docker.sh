#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ISAAC_IMAGE="${ISAAC_IMAGE:-nvcr.io/nvidia/isaac-sim:5.1.0}"
CONTAINER_NAME="${CONTAINER_NAME:-isaac-sim}"
DOCKER_WORKSPACE="${DOCKER_WORKSPACE:-/workspace/omni-asset-cli}"
DOCKER_PYTHON="${DOCKER_PYTHON:-/isaac-sim/python.sh}"
HOST_ROOT="${HOST_ROOT:-${HOME}}"
INSPECTOR_ROOT="${INSPECTOR_ROOT:-${HOME}/usd-simready-inspector}"
ISAAC_CACHE_ROOT="${ISAAC_CACHE_ROOT:-${HOME}/docker/isaac-sim}"
MODE="check"
PULL_IMAGE=0
START_CONTAINER=0
PROBE_IMAGE=0
PROBE_CONTAINER=0
RUN_FLYWHEEL_PROBE=0
FLYWHEEL_ASSET="${FLYWHEEL_ASSET:-${HOME}/new_3D/cup.usd}"
FLYWHEEL_OUT="${FLYWHEEL_OUT:-${REPO_ROOT}/out/cup_flywheel_deploy_probe}"

log() {
  printf '[isaacsim-docker] %s\n' "$*"
}

die() {
  printf '[isaacsim-docker] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_isaacsim_docker.sh [options]

Modes:
  --check                 Run local prerequisite checks only. Default.
  --prepare               Create Isaac Sim cache/config/data/log directories.
  --pull                  Pull the Isaac Sim Docker image.
  --start                 Start/reuse a long-running Isaac Sim container.
  --probe-image           Probe Isaac Sim via docker run --rm using the image.
  --probe-container       Probe Isaac Sim via docker exec using the container.
  --flywheel-probe        Run a short simready-flywheel probe against cup.usd.
  --all                   prepare + pull + start + probe-container.

Options:
  --image IMAGE           Isaac Sim image. Default: nvcr.io/nvidia/isaac-sim:5.1.0
  --name NAME             Container name. Default: isaac-sim
  --workspace PATH        Repo mount inside container. Default: /workspace/omni-asset-cli
  --docker-python PATH    Isaac Sim Python inside container. Default: /isaac-sim/python.sh
  --inspector-root PATH   Host usd-simready-inspector path. Default: ~/usd-simready-inspector
  --cache-root PATH       Host Isaac Sim cache root. Default: ~/docker/isaac-sim
  --flywheel-asset PATH   Asset for --flywheel-probe. Default: ~/new_3D/cup.usd
  --flywheel-out PATH     Output dir for --flywheel-probe.
  -h, --help              Show this help.

Environment overrides:
  ISAAC_IMAGE, CONTAINER_NAME, DOCKER_WORKSPACE, DOCKER_PYTHON,
  INSPECTOR_ROOT, ISAAC_CACHE_ROOT, FLYWHEEL_ASSET, FLYWHEEL_OUT.

Notes:
  - The script does not install Docker or NVIDIA Container Toolkit.
  - Pulling nvcr.io/nvidia/isaac-sim may require prior `docker login nvcr.io`.
  - The long-running container uses `tail -f /dev/null`; tests run through docker exec.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)
      MODE="check"
      ;;
    --prepare)
      MODE="custom"
      ;;
    --pull)
      MODE="custom"
      PULL_IMAGE=1
      ;;
    --start)
      MODE="custom"
      START_CONTAINER=1
      ;;
    --probe-image)
      MODE="custom"
      PROBE_IMAGE=1
      ;;
    --probe-container)
      MODE="custom"
      PROBE_CONTAINER=1
      ;;
    --flywheel-probe)
      MODE="custom"
      RUN_FLYWHEEL_PROBE=1
      ;;
    --all)
      MODE="custom"
      PULL_IMAGE=1
      START_CONTAINER=1
      PROBE_CONTAINER=1
      ;;
    --image)
      ISAAC_IMAGE="${2:?missing value for --image}"
      shift
      ;;
    --name)
      CONTAINER_NAME="${2:?missing value for --name}"
      shift
      ;;
    --workspace)
      DOCKER_WORKSPACE="${2:?missing value for --workspace}"
      shift
      ;;
    --docker-python)
      DOCKER_PYTHON="${2:?missing value for --docker-python}"
      shift
      ;;
    --inspector-root)
      INSPECTOR_ROOT="${2:?missing value for --inspector-root}"
      shift
      ;;
    --cache-root)
      ISAAC_CACHE_ROOT="${2:?missing value for --cache-root}"
      shift
      ;;
    --flywheel-asset)
      FLYWHEEL_ASSET="${2:?missing value for --flywheel-asset}"
      shift
      ;;
    --flywheel-out)
      FLYWHEEL_OUT="${2:?missing value for --flywheel-out}"
      shift
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

if [[ "${MODE}" == "check" ]]; then
  PULL_IMAGE=0
  START_CONTAINER=0
  PROBE_IMAGE=0
  PROBE_CONTAINER=0
  RUN_FLYWHEEL_PROBE=0
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

check_docker_access() {
  require_command docker
  docker version >/dev/null 2>&1 || die "Docker daemon is not reachable by this user."
}

check_paths() {
  [[ -d "${REPO_ROOT}" ]] || die "Repo root not found: ${REPO_ROOT}"
  [[ -f "${REPO_ROOT}/omni_asset_cli.py" ]] || die "omni_asset_cli.py not found in ${REPO_ROOT}"
  [[ -d "${INSPECTOR_ROOT}" ]] || log "warning: inspector root not found yet: ${INSPECTOR_ROOT}"
}

check_nvidia_runtime() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi >/tmp/isaacsim-host-nvidia-smi.log 2>&1 \
      && log "host NVIDIA driver: ok" \
      || log "warning: host nvidia-smi failed; details: /tmp/isaacsim-host-nvidia-smi.log"
  else
    log "warning: host nvidia-smi not found"
  fi

  if docker image inspect "${ISAAC_IMAGE}" >/dev/null 2>&1; then
    log "checking Docker GPU access with local Isaac Sim image"
    if docker run --rm --gpus all --entrypoint nvidia-smi "${ISAAC_IMAGE}" >/tmp/isaacsim-docker-nvidia-smi.log 2>&1; then
      log "Docker GPU access: ok"
      return
    fi
    log "warning: docker run --gpus all nvidia-smi did not pass"
    log "details: /tmp/isaacsim-docker-nvidia-smi.log"
  else
    log "warning: Isaac Sim image not present locally; skipping Docker GPU probe until --pull is run"
  fi
}

prepare_cache_dirs() {
  log "preparing cache dirs under ${ISAAC_CACHE_ROOT}"
  mkdir -p \
    "${ISAAC_CACHE_ROOT}/cache/main/ov" \
    "${ISAAC_CACHE_ROOT}/cache/main/warp" \
    "${ISAAC_CACHE_ROOT}/cache/computecache" \
    "${ISAAC_CACHE_ROOT}/config" \
    "${ISAAC_CACHE_ROOT}/data/documents" \
    "${ISAAC_CACHE_ROOT}/data/Kit" \
    "${ISAAC_CACHE_ROOT}/logs" \
    "${ISAAC_CACHE_ROOT}/pkg"
  if command -v sudo >/dev/null 2>&1; then
    sudo -n chown -R 1234:1234 "${ISAAC_CACHE_ROOT}" || log "warning: chown cache dirs failed; rerun manually if container cache writes fail"
  else
    log "warning: sudo not found; cache ownership was not changed to 1234:1234"
  fi
}

pull_image() {
  log "pulling ${ISAAC_IMAGE}"
  docker pull "${ISAAC_IMAGE}"
}

container_exists() {
  docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"
}

container_running() {
  docker ps --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"
}

start_container() {
  if container_running; then
    log "container already running: ${CONTAINER_NAME}"
    return
  fi
  if container_exists; then
    log "starting existing container: ${CONTAINER_NAME}"
    docker start "${CONTAINER_NAME}" >/dev/null
    return
  fi

  log "creating container: ${CONTAINER_NAME}"
  docker run -d \
    --name "${CONTAINER_NAME}" \
    --gpus all \
    --network host \
    --ipc host \
    -e ACCEPT_EULA=Y \
    -e PRIVACY_CONSENT=Y \
    -v "${REPO_ROOT}:${DOCKER_WORKSPACE}" \
    -v "${HOST_ROOT}:/workspace/host" \
    -v "${INSPECTOR_ROOT}:/workspace/external/usd-simready-inspector" \
    -v "${ISAAC_CACHE_ROOT}/cache/main/ov:/root/.cache/ov" \
    -v "${ISAAC_CACHE_ROOT}/cache/main/warp:/root/.cache/warp" \
    -v "${ISAAC_CACHE_ROOT}/cache/computecache:/root/.nv/ComputeCache" \
    -v "${ISAAC_CACHE_ROOT}/config:/root/.config" \
    -v "${ISAAC_CACHE_ROOT}/data:/root/.local/share/ov/data" \
    -v "${ISAAC_CACHE_ROOT}/logs:/root/.nvidia-omniverse/logs" \
    -w "${DOCKER_WORKSPACE}" \
    --entrypoint /bin/bash \
    "${ISAAC_IMAGE}" \
    -lc 'tail -f /dev/null' >/dev/null
}

probe_image() {
  log "probing Isaac Sim image via omni_asset_cli.py physics-env"
  python3 "${REPO_ROOT}/omni_asset_cli.py" physics-env \
    --runtime-docker-image "${ISAAC_IMAGE}" \
    --docker-workspace "${DOCKER_WORKSPACE}" \
    --docker-python "${DOCKER_PYTHON}"
}

probe_container() {
  container_running || die "Container is not running: ${CONTAINER_NAME}"
  log "probing Isaac Sim container via omni_asset_cli.py physics-env"
  python3 "${REPO_ROOT}/omni_asset_cli.py" physics-env \
    --runtime-docker-container "${CONTAINER_NAME}" \
    --docker-workspace "${DOCKER_WORKSPACE}" \
    --docker-python "${DOCKER_PYTHON}"
}

flywheel_probe() {
  [[ -f "${FLYWHEEL_ASSET}" ]] || die "Flywheel probe asset not found: ${FLYWHEEL_ASSET}"
  container_running || die "Container is not running: ${CONTAINER_NAME}"
  log "running short simready-flywheel probe"
  python3 "${REPO_ROOT}/omni_asset_cli.py" simready-flywheel "${FLYWHEEL_ASSET}" \
    --out "${FLYWHEEL_OUT}" \
    --output-format usda \
    --runtime-docker-container "${CONTAINER_NAME}" \
    --docker-workspace "${DOCKER_WORKSPACE}" \
    --docker-python "${DOCKER_PYTHON}" \
    --frames 10
}

main() {
  log "repo root: ${REPO_ROOT}"
  log "image: ${ISAAC_IMAGE}"
  log "container: ${CONTAINER_NAME}"
  check_paths
  check_docker_access
  check_nvidia_runtime

  if [[ "${MODE}" == "check" ]]; then
    log "local prerequisite checks completed"
    log "next: run with --all to pull/start/probe the Isaac Sim container"
    return
  fi

  prepare_cache_dirs
  [[ "${PULL_IMAGE}" -eq 1 ]] && pull_image
  [[ "${START_CONTAINER}" -eq 1 ]] && start_container
  [[ "${PROBE_IMAGE}" -eq 1 ]] && probe_image
  [[ "${PROBE_CONTAINER}" -eq 1 ]] && probe_container
  [[ "${RUN_FLYWHEEL_PROBE}" -eq 1 ]] && flywheel_probe

  log "done"
}

main
