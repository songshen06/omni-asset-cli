# 项目文档 / Project Documentation

## 项目目标 / Project Goal

这个项目把 Omniverse Asset Validator 包装成更适合 agent、CI 和人工复核的统一 CLI。  
This project wraps Omniverse Asset Validator into a unified CLI that is better suited for agents, CI, and human review.

## 当前结论 / Current State

当前版本的正式入口是：  
The formal entry point in the current version is:

```bash
omni-asset-cli
```

源码 fallback 入口是：  
The source fallback entry point is:

```bash
python3 omni_asset_cli.py ...
```

## 架构 / Architecture

### 入口层 / Entry Layer

- `omni_asset_cli.py`
- `pyproject.toml`
- `setup.py`

这一层定义统一命令接口和安装方式。  
This layer defines the unified command interface and packaging.

### 实现层 / Implementation Layer

- `scripts/check_omniverse_asset_validator_env.py`
- `scripts/run_sync_validation.py`
- `scripts/map_prompt_to_validation.py`
- `scripts/run_async_validation.py`

这一层实现环境检查、同步校验、自然语言映射和异步观测。  
This layer implements environment checking, synchronous validation, prompt mapping, and asynchronous observation.

### 文档层 / Documentation Layer

- `README.md`
- `SKILL.md`
- `references/`

这一层解释如何安装、调用和解释结果。  
This layer explains how to install, run, and interpret the tool.

## 当前推荐流程 / Recommended Flow

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset>`
3. 如需自然语言入口，使用 `map` 或 `validate-from-prompt`
4. 只有排障时使用 `validate-async`

1. `omni-asset-cli env`
2. `omni-asset-cli validate <asset>`
3. Use `map` or `validate-from-prompt` for natural-language entry
4. Use `validate-async` only for troubleshooting

## 规则策略 / Profile Strategy

- `static`: 展示和非交互资产  
  display and non-interactive assets
- `collidable`: 碰撞和基础物理接触  
  collision and basic physical contact
- `movable`: 搬运、抓取、机器人交互  
  moving, grasping, and robot interaction

## 当前推荐 / Current Recommendation

- 首页文档以 `omni-asset-cli` 为中心。  
  Keep the homepage docs centered on `omni-asset-cli`.
- 原始 `omni_asset_validate` 只作为底层和排障信息出现。  
  Mention raw `omni_asset_validate` only as low-level or troubleshooting information.
- 所有文档统一保持中英双语。  
  Keep all docs bilingual in Chinese and English.

