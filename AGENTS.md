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

## Commit & Pull Request Guidelines
Git history is not included in this exported directory, so follow simple imperative commit subjects such as `Add timeout handling to async validation`. Keep commits scoped to one change. Pull requests should describe the user-facing effect, list validation commands run, and attach sample output when a script’s behavior or report format changes.
