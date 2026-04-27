# 项目文档

## 中文说明

### 项目目标

这个项目把 Omniverse Asset Validator 包装成更适合 agent、CI 和人工复核的统一 CLI。当前 Stage 1 主线对齐到静态家具、摆件和装饰道具。

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
- 实现层：`scripts/check_omniverse_asset_validator_env.py`、`scripts/run_sync_validation.py`、`scripts/map_prompt_to_validation.py`、`scripts/run_async_validation.py`、runtime physics scripts
- 文档层：`README.md`、`SKILL.md`、`references/`
- 示例层：`examples/minimal_scene.usda`、`examples/mini_test.usda`、`examples/boat_test/`

### 当前推荐流程

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset> --profile stage1-furniture`
3. 如需自然语言入口，使用 `map` 或 `validate-from-prompt`，例如“按家具和摆件 Stage 1 检查”
4. 只有排障时使用 `validate-async`
5. runtime 物理链路使用 `physics-env` 和 `physics-hit-test`

### Runtime 物理模板模式

`examples/mini_test.usda` 是当前 Stage 1 家具/摆件模板场景。推荐命令使用 `--hit-mode top-drop --size-policy preserve`：把目标资产放到模板目标位置但保持真实 bbox，不按 table footprint 缩放，然后按资产 bbox 中心把动态 box 放到上方掉落。top-drop 会额外生成按资产 bbox 对齐的静态 guide collider，保证 smoke test 有确定碰撞目标。输出 `summary.json`、`runtime_report.json` 和 `timeline.csv`，其中包含 `hit_targeted`、`size_preserved` 和 `contact_detected_or_inferred`。

## English

### Project Goal

This project wraps Omniverse Asset Validator into a unified CLI that is better suited for agents, CI, and human review. The current Stage 1 path is aligned around static furniture, furnishings, and decorative props.

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
- Implementation layer: `scripts/check_omniverse_asset_validator_env.py`, `scripts/run_sync_validation.py`, `scripts/map_prompt_to_validation.py`, `scripts/run_async_validation.py`, runtime physics scripts
- Documentation layer: `README.md`, `SKILL.md`, `references/`
- Examples layer: `examples/minimal_scene.usda`, `examples/mini_test.usda`, `examples/boat_test/`

### Recommended Flow

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset> --profile stage1-furniture`
3. Use `map` or `validate-from-prompt` for natural-language entry, for example "validate this as static furniture and decor props"
4. Use `validate-async` only for troubleshooting
5. Use `physics-env` and `physics-hit-test` for runtime physics checks

### Runtime Physics Template Mode

`examples/mini_test.usda` is the current Stage 1 furniture/prop template scene. The recommended command uses `--hit-mode top-drop --size-policy preserve`: place the target asset at the template target location while preserving its real bbox, then place the dynamic box above the asset bbox center and let it fall. Top-drop also authors a static guide collider aligned to the asset bbox so the smoke test has a deterministic collision target. Outputs include `summary.json`, `runtime_report.json`, and `timeline.csv` with `hit_targeted`, `size_preserved`, and `contact_detected_or_inferred`.
