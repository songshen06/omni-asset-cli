# Environment and Setup / 环境与安装

Use this document when the user asks about runtime requirements, installation, or environment troubleshooting.  
当用户询问运行环境、安装方式或环境排障时，使用这份文档。

## Requirements / 要求

- Recommended Python: 3.10  
  推荐 Python：3.10
- Supported Python: 3.10 to 3.12  
  支持 Python：3.10 到 3.12
- Validator package: `omniverse-asset-validator`  
  校验包：`omniverse-asset-validator`
- Raw validator CLI: `omni_asset_validate`  
  原始 validator CLI：`omni_asset_validate`

## Installation / 安装

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

## Verification / 验证

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

## Agent Guidance / Agent 执行建议

- Prefer `omni-asset-cli validate` for single assets.  
  单资产优先使用 `omni-asset-cli validate`。
- Use `map` or `validate-from-prompt` for natural-language requests.  
  自然语言请求使用 `map` 或 `validate-from-prompt`。
- Use `validate-async` only for timeout observation.  
  `validate-async` 仅用于 timeout 观测。

## Resolver Search Path / 解析器搜索路径

If the asset depends on MDL or external material references, you may need `PXR_AR_DEFAULT_SEARCH_PATH`.  
如果资产依赖 MDL 或外部材质引用，可能需要 `PXR_AR_DEFAULT_SEARCH_PATH`。

Example:

```bash
omni-asset-cli validate /path/to/asset.usd \
  --profile static \
  --pxr-ar-default-search-path /isaac-sim/kit/mdl/core/mdl
```

## Troubleshooting / 排障

- `command not found: omni-asset-cli`  
  CLI 未安装或当前环境没有激活。  
  The CLI is not installed or the current environment is not active.
- `command not found: omni_asset_validate`  
  底层 validator 包未安装。  
  The underlying validator package is not installed.
- Python version outside 3.10-3.12  
  使用支持范围内的解释器重建环境。  
  Recreate the environment with a supported interpreter.

