# 客户部署指南

## 中文说明

### 目的

这份文档面向客户或交付环境，说明如何安装、验证和调用 `omni-asset-cli`。

### 推荐环境

- Python 3.10
- 支持范围 3.10 到 3.12
- 建议使用独立虚拟环境

### 安装

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

### 安装后验证

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

如果没有安装 console script，也可以这样执行：

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
```

### Agent 集成建议

- 优先调用 `omni-asset-cli validate`
- 自然语言入口使用 `map` 或 `validate-from-prompt`
- 不要默认把 `validate-async` 当主路径

## English

### Purpose

This document targets customer or delivery environments and explains how to install, verify, and run `omni-asset-cli`.

### Recommended Environment

- Python 3.10
- Supported range 3.10 to 3.12
- Use a dedicated virtual environment

### Installation

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

### Post-Install Verification

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

If the console script is not installed, run:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
```

### Agent Integration Guidance

- Prefer `omni-asset-cli validate`
- Use `map` or `validate-from-prompt` for natural-language entry
- Do not treat `validate-async` as the default path

