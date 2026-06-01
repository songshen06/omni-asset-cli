# Architecture

This project is a unified CLI and REST API for OpenUSD asset validation and
Isaac Sim Docker-backed physics evidence generation. The maintenance boundary
is three layers: core, runtime, and interfaces.

## Layer 1: Core

Core is the stable domain model. It should be usable by the CLI, REST API,
future portal, gallery builders, and agent workflows without importing FastAPI,
Docker, Isaac Sim, or Omniverse validator process code.

Core owns:

- Asset identity and source metadata: `asset_id`, source filename, checksum,
  size, entrypoint path, and storage location.
- Job identity and lifecycle semantics: `job_id`, `test_type`, status values,
  timestamps, terminal states, and error classification.
- Artifact contracts: canonical names, artifact kinds, content roles, and how
  generated files map into job records.
- Report semantics: how `summary.json`, validator JSON, `runtime_report.json`,
  and `timeline.csv` are interpreted.
- Status classification: conversion from runtime or validator reports into
  stable statuses such as `passed`, `failed`, `blocked`, and `error`.
- Evidence hierarchy: PhysX contact report evidence is stronger than bbox,
  rendered-frame, or motion-only inference.
- Future manifest shape: stable portal-facing `manifest.json` fields and
  references to reports, evidence, videos, thumbnails, issues, and fix plans.

Core must not:

- Shell out to `omni_asset_cli.py`, Docker, Isaac Sim, or Asset Validator.
- Import FastAPI request/response schemas.
- Know API routes, HTTP headers, auth details, or tenant API key mechanics.
- Depend on presentation concerns such as galleries, thumbnails, or portal
  layout beyond artifact metadata and manifest contracts.
- Depend on local command-line defaults that belong to an interface.

Current code note: some core responsibilities still live in
`omni_asset_service/worker.py`, including `classify_summary`,
`classify_validation_summary`, and artifact-kind registration. See
`docs/REFACTOR_PLAN.md`.

## Layer 2: Runtime

Runtime is the execution adapter layer for external tools. It knows how to run
validation and physics evidence generation, but it should report results through
the core artifact and status contracts.

Runtime owns:

- Omniverse Asset Validator execution through
  `omniverse-usd-asset-validator/scripts/run_sync_validation.py`.
- Natural-language-to-validation mapping through
  `omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py`.
- Isaac Sim Docker environment checks through `physics-env`.
- Isaac Sim Docker-backed hit testing through `physics-hit-test`.
- Staging assets so USD files, textures, MDL files, GLB sidecars, and relative
  dependencies are readable under the container workspace.
- Runtime output generation: `summary.json`, `runtime_report.json`,
  `timeline.csv`, authored test stage files, rendered frames, rendered videos,
  and process logs.
- Runtime-only details such as Docker image or container name, docker workspace,
  Isaac Sim Python launcher, frame count, fps, template scene, placement mode,
  hit mode, render backend, camera presets, and video encoding options.
- Debug-only visualization such as temporary physics bbox overlays under
  `/__OmniAssetDebugPhysicsBBox`.

Runtime must not:

- Define product-facing job status semantics independently of core.
- Decide REST API route shape or portal navigation shape.
- Treat rendered frames, bbox overlays, or motion inference as stronger than
  PhysX contact report evidence.
- Mutate public CLI or API contracts while normalizing reports.
- Persist tenant/project records directly except through service storage or
  repository-local output directories.

## Layer 3: Interfaces

Interfaces expose the core and runtime capabilities to users and systems.
Interfaces should translate user input into stable core requests and runtime
adapter calls, then surface artifacts without redefining their meaning.

Interfaces currently include:

- CLI entry point: `python3 omni_asset_cli.py`.
- CLI commands: `env`, `validate`, `map`, `validate-from-prompt`,
  `validate-async`, `physics-env`, `physics-hit-test`, `simready-flywheel`,
  and `gallery`.
- REST API entry point: `omni_asset_service.app:create_app`.
- REST API routes:
  - `POST /v1/projects/{project_id}/assets`
  - `POST /v1/projects/{project_id}/tests/collision`
  - `POST /v1/projects/{project_id}/tests/mesh`
  - `GET /v1/projects/{project_id}/jobs/{job_id}`
  - `GET /v1/projects/{project_id}/jobs/{job_id}/report/summary`
  - `GET /v1/projects/{project_id}/jobs/{job_id}/report/runtime`
  - `GET /v1/projects/{project_id}/jobs/{job_id}/artifacts`
  - `GET /v1/projects/{project_id}/jobs/{job_id}/artifacts/{artifact_id}`
- Future portal/gallery/agent usage over the same job, report, artifact, and
  manifest contracts.

Interfaces own:

- User-facing validation of CLI arguments and API request schemas.
- Authentication, tenant/project scoping, uploads, downloads, and response
  formatting.
- API-compatible defaults, such as the service collision defaults that run
  `physics-hit-test` with `examples/mini_test.usda`, `replace-table`,
  `top-drop`, `preserve`, and 240 frames.
- Agent-friendly orchestration, provided it preserves the artifact contract and
  evidence hierarchy.

Interfaces must not:

- Reclassify report status in route handlers, UI pages, or agent prompts.
- Create new artifact meanings that are not documented in
  `ARTIFACT_CONTRACT.md`.
- Couple portal/gallery needs directly to runtime implementation details.
- Rename existing CLI commands or REST routes as part of internal cleanup.

## Boundary Rules

- New report interpretation belongs in core first, then interfaces may display
  it and runtime may populate it.
- New runtime outputs must be registered as artifacts with a documented role:
  authoritative, visual evidence, supporting trace, or debug-only.
- New CLI flags or API fields should call runtime adapters; they should not
  duplicate execution logic.
- A future portal should read `manifest.json` and artifact metadata instead of
  scanning runtime-specific directories by convention.
- A future agent workflow should cite the same canonical artifacts as the
  portal: validator JSON or `summary.json` for status, `runtime_report.json`
  for detailed physics evidence, `timeline.csv` for frame traces, and rendered
  media only as visual evidence.
