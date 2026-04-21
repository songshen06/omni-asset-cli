# 项目文档

## 中文说明

### 项目目标

这个项目把 Omniverse Asset Validator 包装成更适合 agent、CI 和人工复核的统一 CLI。

### 当前结论

当前版本的正式入口是：

```bash
omni-asset-cli
```

源码 fallback 入口是：

```bash
python3 omni_asset_cli.py ...
```

### 架构

- 入口层：`omni_asset_cli.py`、`pyproject.toml`、`setup.py`
- 实现层：`scripts/check_omniverse_asset_validator_env.py`、`scripts/run_sync_validation.py`、`scripts/map_prompt_to_validation.py`、`scripts/run_async_validation.py`
- 文档层：`README.md`、`SKILL.md`、`references/`

### 当前推荐流程

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset>`
3. 如需自然语言入口，使用 `map` 或 `validate-from-prompt`
4. 只有排障时使用 `validate-async`

## English

### Project Goal

This project wraps Omniverse Asset Validator into a unified CLI that is better suited for agents, CI, and human review.

### Current State

The formal entry point in the current version is:

```bash
omni-asset-cli
```

The source fallback entry point is:

```bash
python3 omni_asset_cli.py ...
```

### Architecture

- Entry layer: `omni_asset_cli.py`, `pyproject.toml`, `setup.py`
- Implementation layer: `scripts/check_omniverse_asset_validator_env.py`, `scripts/run_sync_validation.py`, `scripts/map_prompt_to_validation.py`, `scripts/run_async_validation.py`
- Documentation layer: `README.md`, `SKILL.md`, `references/`

### Recommended Flow

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset>`
3. Use `map` or `validate-from-prompt` for natural-language entry
4. Use `validate-async` only for troubleshooting

