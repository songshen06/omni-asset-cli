# CLI Mapping

Use this reference to translate user intent into `omni_asset_validate` arguments.

Primary documentation:

- https://docs.omniverse.nvidia.com/kit/docs/asset-validator/latest/source/python/docs/cli.html

## Core Command Shape

```bash
omni_asset_validate [options] ASSET
```

`ASSET` can be a single file or a folder.

## Natural Language to Flag Mapping

- "check this asset" -> `omni_asset_validate <asset>`
- "check this folder recursively" -> `omni_asset_validate <folder>`
- "explain the args" -> `--explain`
- "show version" -> `--version`
- "run only this rule" -> `--no-init-rules --rule <RULE>`
- "disable this rule" -> `--disable-rule <RULE>`
- "only this category" -> `--category <CATEGORY>`
- "exclude this category" -> `--disable-category <CATEGORY>`
- "require this requirement profile" -> `--requirement <REQUIREMENT>`
- "target this capability" -> `--capability <CAPABILITY>`
- "enable this feature" -> `--feature <FEATURE>`
- "disable this feature" -> `--disable-feature <FEATURE>`
- "override a parameter" -> `--parameter NAME=VALUE`
- "try automatic fixes" -> `--fix`
- "only show errors/failures/warnings" -> `--predicate IsError|IsFailure|IsWarning`
- "do not preload default rules" -> `--no-init-rules`
- "skip variants for speed" -> `--no-variants`
- "save a csv report" -> `--csv-output <csv-file>`

## Safe Defaults

- Default to no `--fix`
- Default to keeping init rules enabled
- Default to keeping variants enabled
- Default to no predicate filter

## Example Commands

Validate a file:

```bash
omni_asset_validate asset.usda
```

Validate a directory:

```bash
omni_asset_validate ./assets
```

Validate and export CSV:

```bash
omni_asset_validate --csv-output results.csv asset.usda
```

Apply fixes when the user explicitly asked:

```bash
omni_asset_validate --fix asset.usda
```

Run a single rule:

```bash
omni_asset_validate --no-init-rules --rule StageMetadataChecker asset.usda
```

Limit to a category:

```bash
omni_asset_validate --category Material asset.usda
```

## Common Rule Names Mentioned in the CLI Docs

- `UsdzPackageValidator`
- `MissingReferenceChecker`
- `StageMetadataChecker`
- `TextureChecker`
- `PrimEncapsulationChecker`
- `NormalMapTextureChecker`
- `KindChecker`
- `ExtentsChecker`

If the requested rule or category is uncertain, prefer running `omni_asset_validate --explain` or `--help` locally instead of guessing.
