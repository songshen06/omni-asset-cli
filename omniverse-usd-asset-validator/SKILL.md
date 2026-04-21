---
name: omniverse-usd-asset-validator
description: Validate OpenUSD or USDZ assets with NVIDIA Omniverse Asset Validator. Use this skill when the user wants to validate a USD asset, map natural-language validation requests into deterministic CLI arguments, or explain validation results for human and agent workflows.
---

# Omniverse USD Asset Validator

Use this skill to validate USD assets, map natural-language requests into deterministic commands, and return outputs that work well for both human operators and AI agents.

## Default Entry Point

Prefer the installed `omni-asset-cli`.

If the console script is not installed yet, fall back to:

```bash
python3 omni_asset_cli.py ...
```

## Workflow

1. Identify the target asset.
2. Check the runtime first, especially Python, `omniverse-asset-validator`, and `omni_asset_validate`.
3. If the user starts from natural language, use `map` or `validate-from-prompt`.
4. Use synchronous `validate` by default for single assets.
5. Use `validate-async` only when you explicitly need to observe timeout behavior from the raw CLI path.

## Recommended Commands

Check the environment:

```bash
omni-asset-cli env
```

Run default validation:

```bash
omni-asset-cli validate path/to/asset.usd
```

Validate with a profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

Map natural language:

```bash
omni-asset-cli map path/to/asset.usd "check references"
omni-asset-cli map path/to/asset.usd "check Isaac Sim structure"
```

Map and execute directly:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as a static asset"
```

## Natural-Language Handling Rules

- Default to read-only validation and do not add `--fix` unless the user asks.
- Keep the default rules unless the user explicitly narrows the scope.
- Fall back to standard validation if the prompt does not match a specific rule.
- Prefer `KindChecker` only when the user explicitly asks about Isaac Sim, SimReady, hierarchy, or component semantics.

## Response Pattern

Include:

- `Target`
- `Command`
- `Result`
- `Next step`

If JSON or Markdown output was produced, mention the output path as well.

## Environment Contract

- Recommended Python: 3.10
- Acceptable range: 3.10 to 3.12
- Recommended install command:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

## Long-Running Policy

- Default structured validation: `omni-asset-cli validate`
- CLI timeout observation: `omni-asset-cli validate-async`

Operational states:

- `completed`
- `timed_out`
- `blocked`

## References

- `references/environment-and-setup.md`
- `references/cli-mapping.md`
- `references/human-operator-guide.md`
- `references/natural-language-to-args.md`
- `references/kind-checker-explained.md`
