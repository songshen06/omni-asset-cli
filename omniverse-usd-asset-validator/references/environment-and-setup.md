# Environment and Setup

## 中文说明

### 使用场景

当用户询问运行环境、安装方式或环境排障时，使用这份文档。

### 要求

- 推荐 Python：3.10
- 支持 Python：3.10 到 3.12
- 校验包：`omniverse-asset-validator`
- 原始 validator CLI：`omni_asset_validate`

### 安装

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

### 验证

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

### 排障

- `command not found: omni-asset-cli`：CLI 未安装或当前环境没有激活
- `command not found: omni_asset_validate`：底层 validator 包未安装
- Python 版本不在 3.10-3.12：请切换到支持范围内的解释器

## English

### Usage

Use this document when the user asks about runtime requirements, installation, or environment troubleshooting.

### Requirements

- Recommended Python: 3.10
- Supported Python: 3.10 to 3.12
- Validator package: `omniverse-asset-validator`
- Raw validator CLI: `omni_asset_validate`

### Installation

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

### Verification

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

### Troubleshooting

- `command not found: omni-asset-cli`: the CLI is not installed or the environment is not active
- `command not found: omni_asset_validate`: the underlying validator package is not installed
- Python version outside 3.10-3.12: switch to a supported interpreter

