# Agent Bootstrap Deployment

## Purpose

This document is the entry point for a coding agent such as Codex when a new
customer provides only the two GitHub repositories:

```text
git@github.com:songshen06/omni-asset-cli.git
git@github.com:songshen06/usd-simready-inspector.git
```

The agent should use this file to deploy the validation and SimReady flywheel
environment, verify Docker Isaac Sim, and run a first smoke test.

## Expected Directory Layout

Use the customer's home directory unless they explicitly request another path:

```text
~/omni-asset-cli
~/usd-simready-inspector
~/docker/isaac-sim
```

`omni-asset-cli` is the orchestration and runtime validation repository.
`usd-simready-inspector` is the recommendation, scale/orientation repair, static
collider authoring, and package export repository.

## Host Prerequisites

The host must provide:

- Linux with NVIDIA GPU access
- Docker daemon available to the current user
- NVIDIA Container Toolkit configured for `docker run --gpus all`
- Access to pull or use `nvcr.io/nvidia/isaac-sim:5.1.0`
- Python 3.10 or compatible Python 3
- Git access to both repositories

If Docker or NVIDIA Container Toolkit is missing, stop and report the missing
host prerequisite. Do not try to replace Isaac Sim with a non-Docker runtime
unless the customer explicitly asks.

## Clone Repositories

```bash
cd ~
git clone git@github.com:songshen06/omni-asset-cli.git
git clone git@github.com:songshen06/usd-simready-inspector.git
```

If the customer provides HTTPS links instead of SSH links, use those links.

## Install Python Environments

Set up `omni-asset-cli`:

```bash
cd ~/omni-asset-cli
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[validator]"
.venv/bin/python -c "from pxr import Usd; import omni.asset_validator; print('omni validator ok')"
```

Set up `usd-simready-inspector`:

```bash
cd ~/usd-simready-inspector
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c "from pxr import Usd; print('usd inspector ok')"
```

If the inspector requirements are already installed or the repo uses a different
documented setup, follow the repository's current README after checking it.

## Deploy Isaac Sim Docker

Run the deployment helper from `omni-asset-cli`:

```bash
cd ~/omni-asset-cli
scripts/deploy_isaacsim_docker.sh --check
scripts/deploy_isaacsim_docker.sh --start --probe-container
```

For a new machine where the Isaac Sim image is not present:

```bash
scripts/deploy_isaacsim_docker.sh --all
```

The default deployment uses:

```text
image: nvcr.io/nvidia/isaac-sim:5.1.0
container: isaac-sim
workspace: /workspace/omni-asset-cli
docker python: /isaac-sim/python.sh
inspector mount: /workspace/external/usd-simready-inspector
```

The expected probe result is:

```text
probe.ready = true
simulation_app_available = true
simulation_app_name = isaacsim.SimulationApp
```

## Preflight Checks

Run these before processing customer assets:

```bash
cd ~/omni-asset-cli
.venv/bin/python omni_asset_cli.py env
.venv/bin/python omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

If `physics-env` fails, inspect Docker access, container state, image version,
and the repository mounts before running any flywheel job.

## Runtime Input Staging

Docker preflight success does not prove the container can read every host asset
path. Before runtime validation, make the input package container-readable:

- Prefer inputs already under `~/omni-asset-cli`.
- For customer assets under another home-directory folder such as `~/new_3D`,
  stage the whole package directory under `~/omni-asset-cli/out/runtime_inputs/`
  so USD files and sidecar textures, MDL files, GLB files, and relative
  dependencies remain together.
- The runtime harness auto-stages home-directory inputs into
  `out/runtime_inputs/`, but agents should still report the staged path used by
  the Docker command.

Example:

```bash
mkdir -p out/runtime_inputs
cp -a ~/new_3D out/runtime_inputs/new_3D
.venv/bin/python omni_asset_cli.py physics-hit-test out/runtime_inputs/new_3D/cup.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/cup_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

## First Flywheel Smoke Test

If `~/new_3D/cup.usd` exists, use it as the first end-to-end probe:

```bash
cd ~/omni-asset-cli
.venv/bin/python omni_asset_cli.py simready-flywheel ~/new_3D/cup.usd \
  --out out/cup_flywheel_container \
  --output-format usda \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

For customer assets, replace the input path and keep the same Docker arguments.

Expected output:

```text
out/<asset>_simready_flywheel/flywheel_report.json
```

Review these fields first:

```text
priority_checks.size
priority_checks.weight
defects.source_validator
defects.fixed_validator
runtime.status
runtime.hit_analysis
diagnosis.status
```

## Runtime Rendering Policy

The Stage 1 benchmark simulates 240 frames by default. Do not enable PNG capture
unless the customer asks for visual evidence.

No PNG capture:

```bash
--frames 240
```

Sparse PNG capture:

```bash
--frames 240 --render-frames --render-every-n-frames 20
```

Avoid saving all 240 frames unless there is a specific debugging reason.

## Agent Operating Rules

- Treat `omni-asset-cli` as the orchestration and validation entry point.
- Treat `usd-simready-inspector` as the repair and recommendation engine.
- Use `scripts/deploy_isaacsim_docker.sh` for Docker setup instead of hand
  rebuilding the `docker run` command.
- Use the persistent `isaac-sim` container when available.
- Do not claim weight is fixed unless authored `MassAPI.mass`, authored
  `MassAPI.density`, or an accepted `mass_for_authoring_kg` exists.
- Keep generated outputs under `~/omni-asset-cli/out/` unless the customer asks
  for another artifact location.
- When a command fails, report the failing step and point to
  `flywheel_report.json`, `summary.json`, or `runtime_report.json`.

## Minimal Customer Handoff

When handing this to another agent, provide only:

```text
Repos:
- git@github.com:songshen06/omni-asset-cli.git
- git@github.com:songshen06/usd-simready-inspector.git

Start here after cloning:
- ~/omni-asset-cli/omniverse-usd-asset-validator/references/agent-bootstrap-deployment.md
```
