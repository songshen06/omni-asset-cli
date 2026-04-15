# Environment and Setup

Use this reference when the user asks for installation requirements, runtime compatibility, or setup steps.

This skill assumes the standalone Python package deployment, not the Kit extension deployment.

## Documented Requirements

Based on NVIDIA's Omniverse Asset Validator documentation:

- Recommended Python: 3.10
- Supported Python: 3.10 to 3.12
- OpenUSD: 22.11 or later
- Package: `omniverse-asset-validator`
- CLI entry point: `omni_asset_validate`

Source pages:

- https://docs.omniverse.nvidia.com/kit/docs/asset-validator/latest/source/python/docs/index.html
- https://docs.omniverse.nvidia.com/kit/docs/asset-validator/latest/source/python/docs/cli.html

## Installation

Use a dedicated virtual environment and install with one command only:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

On Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

Interpretation:

- Treat the package as an independent Python library.
- Treat `omni_asset_validate` as its independent CLI.
- Prefer `python -m pip` over bare `pip` so the install definitely targets the active venv interpreter.

## Environment Verification

Recommended sequence:

1. Check Python version.
2. Check whether `omni_asset_validate` is on `PATH`.
3. If missing, inspect `python -m pip show omniverse-asset-validator`.
4. If OpenUSD import errors appear, confirm the environment was installed with `[usd,numpy]`.

You can run:

```bash
python scripts/check_omniverse_asset_validator_env.py
```

from the skill root to collect a quick environment report.

## Practical Setup Guide

Minimal workflow for a customer machine:

1. Create or activate a Python 3.10 virtual environment.
2. Install the package:

```bash
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

3. Confirm the CLI is available:

```bash
omni_asset_validate --help
```

4. Run a first validation:

```bash
omni_asset_validate /path/to/asset.usda
```

## Agent Execution Guidance

For Codex or another agent, run validator commands inside the same venv that contains the package.

Examples:

```bash
source .venv/bin/activate && omni_asset_validate /path/to/asset.usda
```

or:

```bash
.venv/bin/omni_asset_validate /path/to/asset.usda
```

The direct executable path is more deterministic for automation.

## Troubleshooting

- `command not found: omni_asset_validate`
  The package is not installed in the active environment, the venv is not activated, or the script directory is not on `PATH`.

- `pip: command not found`
  Use `python -m pip ...` inside the venv instead of calling bare `pip`.

- Python version outside 3.10-3.12
  Move to a supported interpreter before debugging validator behavior.

- OpenUSD import/runtime failures
  Recreate the environment and install exactly `omniverse-asset-validator[usd,numpy]`.

- The detailed CLI page shows `usage: validate ...`
  Treat that as documentation wording for the validator entry point. NVIDIA's package overview explicitly documents `omni_asset_validate` as the terminal command, so prefer `omni_asset_validate` and verify with `--help` locally.
