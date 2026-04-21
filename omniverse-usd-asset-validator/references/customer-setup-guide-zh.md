# 客户部署指南 / Customer Setup Guide

## 目的 / Purpose

这份文档面向客户或交付环境，说明如何安装、验证和调用 `omni-asset-cli`。  
This document targets customer or delivery environments and explains how to install, verify, and run `omni-asset-cli`.

## 推荐环境 / Recommended Environment

- Python 3.10  
  Python 3.10
- 支持范围 3.10 到 3.12  
  Supported range 3.10 to 3.12
- 建议使用独立虚拟环境  
  Use a dedicated virtual environment

## 安装 / Installation

Linux / macOS:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --no-build-isolation -e ".[validator]"
```

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --no-build-isolation -e ".[validator]"
```

## 安装后验证 / Post-Install Verification

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

如果没有安装 console script，也可以这样执行：  
If the console script is not installed, run:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
```

## Agent 集成建议 / Agent Integration Guidance

- 优先调用 `omni-asset-cli validate`。  
  Prefer `omni-asset-cli validate`.
- 自然语言入口使用 `map` 或 `validate-from-prompt`。  
  Use `map` or `validate-from-prompt` for natural-language entry.
- 不要默认把 `validate-async` 当主路径。  
  Do not treat `validate-async` as the default path.

## 搜索路径说明 / Resolver Search Path Notes

如果资产依赖 MDL 或其他外部材质路径，可能需要设置 `PXR_AR_DEFAULT_SEARCH_PATH`。  
If the asset depends on MDL or other external material paths, you may need `PXR_AR_DEFAULT_SEARCH_PATH`.

示例：  
Example:

```bash
omni-asset-cli validate /path/to/asset.usd \
  --profile static \
  --pxr-ar-default-search-path /isaac-sim/kit/mdl/core/mdl
```

## 对外说明口径 / Recommended External Wording

建议对客户说明：  
Recommended wording for customers:

- 这是一个统一的 USD 资产校验 CLI。  
  This is a unified CLI for USD asset validation.
- 默认输出同时适合自动化和人工复核。  
  The default output is suitable for both automation and human review.
- 对复杂资产，建议先跑同步路径。  
  For complex assets, start with the synchronous path.

