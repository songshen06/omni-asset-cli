---
name: omniverse-usd-asset-validator
description: Validate OpenUSD or USDZ assets with NVIDIA Omniverse Asset Validator from natural-language requests. Use when the user wants to check a `.usd`, `.usda`, `.usdc`, `.usdz`, or a folder of USD assets for compliance issues, missing references, metadata problems, texture issues, category/rule-specific validation, CSV export, or auto-fix guidance with the `omni_asset_validate` CLI.
---

# Omniverse USD Asset Validator

Validate USD assets by translating natural-language requests into concrete validator executions, then explain the results in user language.

This skill targets the standalone Python package workflow, not the Kit UI extension workflow. Treat `omniverse-asset-validator` as an independent Python library with its own CLI entry point, `omni_asset_validate`.
Prefer the synchronous Python API wrapper in `scripts/run_sync_validation.py` for single-asset validation because the packaged CLI async path can hang in this environment.

Read [references/environment-and-setup.md](references/environment-and-setup.md) when the environment might be missing dependencies or when the user asks for install requirements. Read [references/cli-mapping.md](references/cli-mapping.md) when you need exact CLI option mapping or examples.
Read [references/kind-checker-explained-zh.md](references/kind-checker-explained-zh.md) when the user is asking about Isaac Sim asset structure, SimReady hierarchy, component semantics, or why `KindChecker` matters.
Use `scripts/run_sync_validation.py` as the default execution path for single assets. Use `scripts/map_prompt_to_validation.py` when the user gives a natural-language request and you need deterministic argument generation before validation. Use `scripts/run_async_validation.py` only when you explicitly want timeout-based operational monitoring of the CLI path.

## Workflow

1. Identify the asset target.
   Accept a single file or a folder. Prefer absolute or workspace-relative paths in the final command.

2. Confirm the runtime before validating.
   If the environment is unknown, run `scripts/check_omniverse_asset_validator_env.py` first.
   If the command is unavailable, give setup guidance from `references/environment-and-setup.md`.
   Prefer a dedicated virtual environment and run the CLI from that environment.

3. Convert the user's request into CLI options.
   Map intent to validation arguments conservatively:
   - "check this asset" -> no extra flags
   - "fix what can be fixed" -> `--fix`
   - "only show errors" -> `--predicate IsError`
   - "warnings only" -> `--predicate IsWarning`
   - "only check materials" -> `--category Material`
   - "only run StageMetadataChecker" -> `--rule StageMetadataChecker`
   - "check topology" -> `--rule ValidateTopologyChecker`
   - "check geometry" -> `--category Geometry`
   - "check references" -> `--rule MissingReferenceChecker`
   - "check Isaac Sim structure" -> `--rule KindChecker`
   Add `KindChecker` when the user explicitly asks about Isaac Sim asset structure, SimReady structure, hierarchy correctness, component semantics, or simulation-friendly hierarchy.
   Do not add `KindChecker` by default for every validation request.
   Use `scripts/map_prompt_to_validation.py` if the mapping is non-trivial.

4. Execute the smallest command that satisfies the request.
   Prefer `python scripts/run_sync_validation.py` for single-asset validation.
   Use direct Python API execution to avoid the async CLI timeout issue observed with `omni_asset_validate` in this environment.
   When a dedicated validator virtual environment exists, execute the script through that environment so Codex uses the correct interpreter and installed package set.

5. Summarize results for the user.
   Report:
   - asset path
   - command used
   - issue counts or notable failures
   - whether fixes were applied
   - next actions if validation failed

6. Use asynchronous handling for long-running assets.
   When validation does not complete quickly, switch to an asynchronous pattern:
   - write results to `--json-output`
   - run with a generous timeout
   - poll for completion instead of waiting in a short foreground call
   - if the process times out, report `validation started but did not complete in the allowed window`

## Natural-Language Handling

Treat the user's request as intent, not as shell text. Do not pass arbitrary natural-language fragments directly into the command.

When the request is ambiguous, make the safest reasonable assumption:
   - default to read-only validation
   - do not enable `--fix` unless the user asks
   - keep default rules enabled unless the user asks for specific rules/categories
   - keep variants enabled unless the user asks for a faster or narrower check

If the user asks for "all checks" or "standard validation", use the default wrapper:

```bash
python scripts/run_sync_validation.py path/to/asset.usda
```

If the user asks for a narrow validation scope, disable default rules only when needed:

```bash
python scripts/run_sync_validation.py path/to/asset.usda --rule StageMetadataChecker
```

## Response Pattern

Use this structure when replying after validation:

```text
Target: <path>
Command: <exact command>
Result: <pass/fail plus important issues>
Next step: <fix, rerun, or environment action>
```

If the command cannot run because the environment is missing, switch to setup guidance and provide the exact prerequisite gap.

If the user needs structured output, use this pattern:

```bash
python scripts/run_sync_validation.py path/to/asset.usd --output-json /tmp/asset_validation.json
```

Then:

1. Let the wrapper produce JSON directly from the synchronous API result.
2. Parse and summarize the JSON.
3. Use the async wrapper only when you intentionally need to characterize CLI timeout behavior.

## Environment Contract

Recommend Python 3.10 for the most conservative setup. Accept Python 3.10 to 3.12 when the user already has a supported interpreter.

Prefer this deployment shape:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

For agents such as Codex, ensure every validator command runs inside that environment, for example:

```bash
source .venv/bin/activate && python scripts/run_sync_validation.py asset.usda
```

or by calling the venv executable directly:

```bash
.venv/bin/python scripts/run_sync_validation.py asset.usda
```

## Long-Running Validation Policy

For production assets, especially packaged or layered SimReady assets, do not assume validation completes within seconds.
For single-asset validation, prefer the synchronous wrapper first because it has been verified to return on both minimal and real assets.

Default policy:

- default structured validation: `scripts/run_sync_validation.py`
- CLI timeout characterization: `scripts/run_async_validation.py`
- if CLI async execution still does not complete, return an operational status and recommend avoiding the CLI path

Operational result states:

- `completed`: validator finished and results were parsed
- `timed_out`: validator started but did not finish inside the allowed window
- `blocked`: environment or command invocation failed before validation started

## Examples

User: "帮我检查这个 USD 资源有没有贴图和引用问题：assets/chair.usda"

Agent action:

```bash
python scripts/run_sync_validation.py assets/chair.usda
```

User: "检查这个目录，只看材质类问题，并导出 csv"

Agent action:

```bash
python scripts/run_sync_validation.py assets/chair.usda --category Material --output-json /tmp/material-results.json
```

User: "只跑 StageMetadataChecker，不要默认规则"

Agent action:

```bash
python scripts/run_sync_validation.py asset.usda --rule StageMetadataChecker
```
