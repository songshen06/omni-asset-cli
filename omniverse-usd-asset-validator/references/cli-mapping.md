# CLI Mapping

## 中文说明

### 目的

这份文档用于把用户意图映射到 `omni-asset-cli` 或底层 validator 参数。

### 主命令形态

```bash
omni-asset-cli validate [options] ASSET
omni-asset-cli map ASSET "PROMPT"
omni-asset-cli validate-from-prompt ASSET "PROMPT"
```

底层异步 CLI 路径仍然存在：

```bash
omni_asset_validate [options] ASSET
```

### 常见映射

| 中文意图 | 推荐命令 |
| --- | --- |
| 检查这个资产 | `omni-asset-cli validate <asset>` |
| 检查这个目录 | `omni-asset-cli validate-async <folder>` |
| 只检查引用 | `omni-asset-cli validate <asset> --rule MissingReferenceChecker` |
| 只检查材质 | `omni-asset-cli validate <asset> --category Material` |
| 只看错误 | `omni-asset-cli validate <asset> --predicate IsError` |
| 按静态资产检查 | `omni-asset-cli validate <asset> --profile static` |
| 按可碰撞资产检查 | `omni-asset-cli validate <asset> --profile collidable` |
| 按可移动资产检查 | `omni-asset-cli validate <asset> --profile movable` |
| 把自然语言转成参数 | `omni-asset-cli map <asset> "<prompt>"` |
| 直接从自然语言执行 | `omni-asset-cli validate-from-prompt <asset> "<prompt>"` |

### 安全默认值

- 默认不加 `--fix`
- 默认保留 init rules
- 默认保留 variants
- 没命中特定规则时，回退到标准校验

### 示例

```bash
omni-asset-cli validate asset.usda
omni-asset-cli validate asset.usda --profile static
omni-asset-cli validate asset.usda --category Material
omni-asset-cli map asset.usda "检查引用和贴图"
omni-asset-cli validate-from-prompt asset.usda "帮我判断这个机器人资产是否适合抓取"
```

## English

### Purpose

Use this document to map user intent into `omni-asset-cli` commands or underlying validator arguments.

### Core Command Shape

```bash
omni-asset-cli validate [options] ASSET
omni-asset-cli map ASSET "PROMPT"
omni-asset-cli validate-from-prompt ASSET "PROMPT"
```

The underlying asynchronous CLI path still exists:

```bash
omni_asset_validate [options] ASSET
```

### Common Mapping

| Intent | Recommended command |
| --- | --- |
| check this asset | `omni-asset-cli validate <asset>` |
| check this folder | `omni-asset-cli validate-async <folder>` |
| check references only | `omni-asset-cli validate <asset> --rule MissingReferenceChecker` |
| check materials only | `omni-asset-cli validate <asset> --category Material` |
| show errors only | `omni-asset-cli validate <asset> --predicate IsError` |
| validate as a static asset | `omni-asset-cli validate <asset> --profile static` |
| validate as a collidable asset | `omni-asset-cli validate <asset> --profile collidable` |
| validate as a movable asset | `omni-asset-cli validate <asset> --profile movable` |
| map this request into args | `omni-asset-cli map <asset> "<prompt>"` |
| map and execute directly | `omni-asset-cli validate-from-prompt <asset> "<prompt>"` |

### Safe Defaults

- Do not add `--fix` unless the user explicitly asks
- Keep init rules enabled by default
- Keep variants enabled by default
- Fall back to standard validation if no specific rule was matched

### Examples

```bash
omni-asset-cli validate asset.usda
omni-asset-cli validate asset.usda --profile static
omni-asset-cli validate asset.usda --category Material
omni-asset-cli map asset.usda "check references and textures"
omni-asset-cli validate-from-prompt asset.usda "validate this robot asset for grasping"
```

