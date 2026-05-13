# Repository Guidelines

## Project Structure & Module Organization
This repository is a small skill package for validating OpenUSD assets with NVIDIA Omniverse Asset Validator. Core logic lives in `omniverse-usd-asset-validator/`: `scripts/` contains executable Python helpers, `references/` holds setup and usage notes, and `agents/openai.yaml` defines the agent entry point. Sample assets for local checks live in `examples/`, including `examples/minimal_scene.usda` and the larger `examples/boat_test/` set. The ZIP file is a packaged export of the same skill content.

## Build, Test, and Development Commands
Use a dedicated virtual environment and run scripts from the repository root:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install "omniverse-asset-validator[usd,numpy]"
python omniverse-usd-asset-validator/scripts/check_omniverse_asset_validator_env.py
python omniverse-usd-asset-validator/scripts/run_sync_validation.py examples/minimal_scene.usda
python omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py examples/minimal_scene.usda "check references"
```

`check_omniverse_asset_validator_env.py` verifies interpreter and CLI availability. `run_sync_validation.py` is the default validator wrapper. `map_prompt_to_validation.py` converts natural-language requests into deterministic validator arguments.

## Coding Style & Naming Conventions
Follow Python 3.10+ syntax with 4-space indentation, standard-library-first imports, and type hints where practical. Keep scripts focused and executable from the command line. Use `snake_case` for files, functions, and variables; reserve `PascalCase` for validator rule names such as `StageMetadataChecker`. Prefer ASCII unless a file already contains localized content, as some reference documents do.

## Testing Guidelines
There is no formal `tests/` suite in this archive, so validate changes by running the relevant script against assets in `examples/`. For parser or mapping changes, test both `examples/minimal_scene.usda` and at least one `examples/boat_test/*.usd` asset. Treat successful execution plus readable JSON or Markdown output as the minimum acceptance check.

## Runtime Validation & Data Flywheel
All Isaac Sim runtime validation must run on Linux with Isaac Sim Docker. Non-Docker runtimes are not supported for authoritative runtime physics checks. The standard preflight is:

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Agents must follow this operating procedure for runtime physics validation:

1. Confirm the runtime with `physics-env` using an Isaac Sim Docker image or container.
2. Confirm the input USD is readable inside the container. Prefer assets already under this repository.
3. If the input asset is outside the repository but under the host home directory, stage the whole asset package directory into `out/runtime_inputs/<asset_package>/` before running the test. This keeps USD files, textures, MDL files, GLB sidecars, and relative dependencies under the `/workspace/omni-asset-cli` mount. The runtime harness also stages home-directory inputs automatically, but reports must still include the staged path so failures can be reproduced.
4. Run the Stage 1 top-drop hit test in Isaac Sim Docker.
5. Treat `checks.contact_report_detected == true` and `contact_evidence_level == "detected"` as the preferred pass evidence. Motion-only inference is weaker and must be reported as such.
6. If the downstream runtime check fails, classify it as data-flywheel feedback for the upstream preparation step, not as an isolated test result.

The standard Stage 1 runtime check is:

```bash
python3 omni_asset_cli.py physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/asset_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

When the user asks for rendered physics bbox evidence, keep the work in this
runtime harness instead of creating debug USD edits upstream. Add
`--render-frames --render-physics-bboxes` to the Docker hit test. The harness
authors bbox curves only in the Kit session layer under
`/__OmniAssetDebugPhysicsBBox`, captures via the existing viewport frame path,
and clears the overlay before shutdown. Use
`--render-physics-bbox-fallback-default-prim` only to debug capture on assets
that have no collider paths; do not report fallback bbox output as physics
collider evidence.

For runtime reports, prefer PhysX contact evidence over motion heuristics. `checks.contact_report_detected == true` and `contact_evidence_level == "detected"` are stronger evidence than `checks.contact_detected_or_inferred == true` with an inferred evidence level. If a runtime check fails, feed the failure upstream as a data-flywheel signal instead of treating it as an isolated test failure. Capture `summary.json`, `runtime_report.json`, `timeline.csv`, the generated stage path, the asset path, Docker image tag, command line, and whether the failure was environment, authoring, collider/contact, placement, scale, or motion-related. Use that failure record to improve the upstream asset preparation or repair step, for example collider generation, bbox/scale normalization, template placement, contact-report instrumentation, or SimReady repair policy. Re-run the same Docker command after the upstream change and compare the structured artifacts.

## Commit & Pull Request Guidelines
Git history is not included in this exported directory, so follow simple imperative commit subjects such as `Add timeout handling to async validation`. Keep commits scoped to one change. Pull requests should describe the user-facing effect, list validation commands run, and attach sample output when a script’s behavior or report format changes.
