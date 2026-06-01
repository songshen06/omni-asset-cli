# Refactor Plan

This is a consolidation plan only. Do not change public CLI commands, REST API
routes, runtime execution behavior, artifact filenames, or current service job
status values as part of the first extraction.

## Current Coupling

`omni_asset_service/worker.py` currently owns several responsibilities that are
domain logic rather than worker execution logic:

- `classify_summary`: runtime report-to-status classification.
- `classify_validation_summary`: validator report-to-status classification.
- Artifact registration: mapping filenames and extensions to artifact kinds.
- Report normalization: adapting runtime and validator reports into the compact
  job `result_json` payload.

This works today but couples subprocess execution, persistence, artifact
registration, and product semantics in one module.

## Target Modules

Create a small core/domain package before adding portal-specific behavior.

Suggested module split:

- `omni_asset_service/domain/status.py`: job status constants and report
  classification functions.
- `omni_asset_service/domain/artifacts.py`: canonical filenames, artifact
  kinds, evidence roles, and artifact registration helpers.
- `omni_asset_service/domain/reports.py`: report normalization from validator
  JSON and runtime JSON into stable job result payloads.
- `omni_asset_service/domain/manifest.py`: future `manifest.json` assembly once
  the schema is implemented.

## Extraction Order

1. Move constants and classification tests first, preserving imports with a
   compatibility shim if needed.
2. Move artifact-kind mapping and add tests that cover current filenames:
   `summary.json`, `runtime_report.json`, `timeline.csv`, rendered images,
   other JSON files, and unknown artifacts.
3. Move report normalization so `JobWorker` only selects the runner, records the
   process log, stores artifacts, and updates the job from normalized results.
4. Add manifest generation only after the portal contract needs it.

## Guardrails

- Keep `classify_summary` semantics strict: PhysX contact report evidence is
  required for a collision pass.
- Keep mesh validation warnings as passing service jobs unless they include
  physics-impacting blocking issues.
- Keep current REST routes and response models stable.
- Keep current CLI command names and default behavior stable.
- Avoid portal-specific fields in runtime scripts; portal needs should flow
  through artifact metadata and future `manifest.json`.
