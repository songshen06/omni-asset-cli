# omni-asset-cli User Guide

## Overview

`omni-asset-cli` is a unified CLI for OpenUSD asset validation, built on NVIDIA Omniverse Asset Validator. The current Stage 1 path is aligned around static furniture, furnishings, and decorative props.

It provides:

- A unified `omni-asset-cli` entry point
- A synchronous validator path
- JSON and Markdown outputs
- A recommended `stage1-furniture` profile for furniture and prop validation
- Backward-compatible `static`, `collidable`, and `movable` profiles
- Natural-language entry points for AI agents
- Isaac Sim Docker runtime physics smoke tests
- Optional PNG/MP4 rendered evidence and physics bbox overlays

## Installation

Install this project only:

```bash
python3 -m pip install --no-build-isolation -e .
```

Install this project together with validator dependencies:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

If you do not want to install the console script yet, run the source entry point directly:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda --profile stage1-furniture
```

## Static USD Validation

Check the local environment:

```bash
omni-asset-cli env
```

Validate one USD asset:

```bash
omni-asset-cli validate path/to/asset.usd
```

Apply the Stage 1 furniture/prop profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
```

Write JSON and Markdown reports:

```bash
python3 omni_asset_cli.py validate examples/minimal_scene.usda \
  --profile stage1-furniture \
  --output-json out/minimal_scene_validator.json \
  --output-md out/minimal_scene_validator.md
```

Legacy profiles remain available for compatibility:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

## Isaac Sim Docker Runtime

This project separates static USD checks from Isaac Sim runtime physics checks:

- Host Python runs `validate` and writes validator reports.
- Linux + Isaac Sim Docker runs `physics-hit-test` physics smoke tests.
- Assets, templates, and output directories are shared through the repository mount.
- Assets outside the repository but under the host home directory are staged into `out/runtime_inputs/`.

Authoritative runtime checks require Linux with Isaac Sim Docker. Non-Docker runtimes are not treated as authoritative physics validation.

### Runtime Probe

Prefer reusing a running Isaac Sim container that already mounts this repository:

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim
```

You can also run through an Isaac Sim image:

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Expected fields:

```text
probe.ready = true
simulation_app_available = true
```

### Stage 1 Top-Drop Hit Test

Furniture: replace the table in the template.

```bash
python3 omni_asset_cli.py physics-hit-test path/to/chair_or_table.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/furniture_template_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

Decor props: keep the template table and place the asset on the tabletop.

```bash
python3 omni_asset_cli.py physics-hit-test path/to/cup_or_decor.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode tabletop \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/prop_tabletop_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

`examples/mini_test.usda` is the Stage 1 furniture/prop template scene. It contains a table, static colliders, and the dynamic `/World/boxActor`. The recommended path is `--hit-mode top-drop --size-policy preserve`, which preserves the target asset's real bbox and drops the dynamic box from above the asset.

## Runtime Outputs and Pass Evidence

`physics-hit-test` writes:

- `summary.json`
- `runtime_report.json`
- `timeline.csv`
- The generated test stage
- Optional `render_frames/` and `render_videos/`

Key fields:

```text
result
checks.asset_loaded
checks.static_colliders_applied
checks.dynamic_box_created
checks.simulation_advanced
checks.hit_targeted
checks.contact_report_detected
checks.contact_detected_or_inferred
contact_evidence_level
```

Prefer strong contact evidence:

```text
checks.contact_report_detected == true
contact_evidence_level == detected
```

`contact_report_detected` comes from PhysX contact reports and is stronger than bbox motion inference. `contact_evidence_level == inferred` only means the motion heuristic passed; it should not be treated as a real PhysX contact event.

## Rendered Evidence and Video

Capture multi-camera PNG frames and MP4 files from the same runtime command:

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --render-video \
  --render-video-style asset-table-drop \
  --render-camera-preset front \
  --render-camera-preset side \
  --render-camera-preset top \
  --render-every-n-frames 2 \
  --render-video-fps 30 \
  --out out/minimal_scene_docker_hit_video \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

Output paths:

- PNG frames: `OUT/render_frames/<camera>/`
- MP4 videos: `OUT/render_videos/<camera>.mp4`

`--render-video-style hit-test` captures the same hit-test scene. `--render-video-style asset-table-drop` delegates to `render_asset_table_drop.py` for the validated falling-asset visual style. Video is visual evidence; the authoritative collision result still comes from PhysX contact evidence in `summary.json` and `runtime_report.json`.

For a customer-facing report, gate the video before embedding it:

```bash
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=codec_type,codec_name,width,height,nb_frames \
  -of json OUT/render_videos/front.mp4
```

Accept the video only when it exists, is non-empty, has the expected duration
and frame count, shows the real runtime scene, and comes from the same workflow
output directory as the accepted `summary.json` / `runtime_report.json`. A
separate retry is acceptable only when it uses the same input USD and same
SimReady output USD and is documented with the report. Do not use synthetic
placeholder videos, old videos from another run, or videos for a different
asset. If the visual log stops at `capture-first-frame-start` and stderr
contains `cudaErrorNoDevice`, keep the contact evidence from `summary.json` /
`runtime_report.json` and regenerate video separately. Prefer the stable
correction path first:

```bash
python3 omni_asset_cli.py physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode tabletop \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --render-video \
  --render-video-style hit-test \
  --render-camera-preset front \
  --render-every-n-frames 2 \
  --render-video-fps 30 \
  --out OUT_video_retry \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

Use `asset-table-drop` again only when the Isaac Sim container has a working
CUDA render device. Do not use synthetic placeholder videos in customer
reports.

To render physics bbox evidence, stay in the same runtime harness:

```bash
--render-frames --render-physics-bboxes
```

Use `--render-physics-bbox-fallback-default-prim` only to debug capture on assets with no collider paths. Do not report fallback bbox output as physics collider evidence.

## REST API Service

For REST API deployment, use the helper script to create an isolated virtual environment, install API dependencies, and write a local env file:

```bash
scripts/deploy_api_service.sh --write-env
source .env.omni-asset-service
.venv-api/bin/omni-asset-service --host 0.0.0.0 --port 8000
```

For development, you can install the API extra directly:

```bash
python3 -m pip install --no-build-isolation -e ".[api]"
```

Minimal local startup:

```bash
export OMNI_SERVICE_STORAGE_ROOT="$PWD/out/omni-asset-service"
export OMNI_SERVICE_API_KEYS=dev-secret:tenant_a:project_a
export ISAAC_CONTAINERS=isaac-sim-0
export DOCKER_WORKSPACE=/workspace/omni-asset-cli
export DOCKER_PYTHON=/isaac-sim/python.sh
export OMNI_SERVICE_JOB_TIMEOUT_SECONDS=7200

omni-asset-service --host 0.0.0.0 --port 8000
```

Core endpoints:

```text
POST /v1/projects/{project_id}/assets
POST /v1/projects/{project_id}/tests/mesh
POST /v1/projects/{project_id}/tests/collision
GET  /v1/projects/{project_id}/jobs/{job_id}
GET  /v1/projects/{project_id}/jobs/{job_id}/report/summary
GET  /v1/projects/{project_id}/jobs/{job_id}/report/runtime
GET  /v1/projects/{project_id}/jobs/{job_id}/artifacts
GET  /v1/projects/{project_id}/jobs/{job_id}/artifacts/{artifact_id}
```

All requests use `X-API-Key` authentication. The API does not accept arbitrary server paths; upload a `.zip` or `.usd/.usda/.usdc` asset package first, then create test jobs with the returned `asset_id`.

## AI Agent Commands

Map natural language into deterministic arguments:

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "validate this as static furniture and decor props"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

Map and execute in one step:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as static furniture and decor props"
omni-asset-cli validate-from-prompt path/to/asset.usd "check references and materials for this furnishing"
```

## Repository Layout

```text
omni_asset_cli.py
omni_asset_service/
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
docs/
```

More deployment and operations details:

- [DEPLOYMENT.md](../DEPLOYMENT.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [omni-asset-cli-agent/SKILL.md](../omni-asset-cli-agent/SKILL.md)
- [omniverse-usd-asset-validator/references/](../omniverse-usd-asset-validator/references/)
