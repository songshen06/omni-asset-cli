# CLI Mapping / CLI 参数映射

这个文档用于把用户意图映射到 `omni-asset-cli` 或底层 validator 参数。  
Use this document to map user intent into `omni-asset-cli` or underlying validator arguments.

## 主命令形态 / Core Command Shape

```bash
omni-asset-cli validate [options] ASSET
omni-asset-cli map ASSET "PROMPT"
omni-asset-cli validate-from-prompt ASSET "PROMPT"
```

底层异步 CLI 路径仍然存在：  
The underlying asynchronous CLI path still exists:

```bash
omni_asset_validate [options] ASSET
```

## 常见映射 / Common Mapping

| 中文意图 | English intent | 推荐命令 / Recommended command |
| --- | --- | --- |
| 检查这个资产 | check this asset | `omni-asset-cli validate <asset>` |
| 检查这个目录 | check this folder | `omni-asset-cli validate-async <folder>` |
| 只检查引用 | check references only | `omni-asset-cli validate <asset> --rule MissingReferenceChecker` |
| 只检查材质 | check materials only | `omni-asset-cli validate <asset> --category Material` |
| 只看错误 | show errors only | `omni-asset-cli validate <asset> --predicate IsError` |
| 作为静态资产检查 | validate as a static asset | `omni-asset-cli validate <asset> --profile static` |
| 作为可碰撞资产检查 | validate as a collidable asset | `omni-asset-cli validate <asset> --profile collidable` |
| 作为可移动资产检查 | validate as a movable asset | `omni-asset-cli validate <asset> --profile movable` |
| 把自然语言转成参数 | map this request into args | `omni-asset-cli map <asset> "<prompt>"` |
| 直接从自然语言执行 | map and execute directly | `omni-asset-cli validate-from-prompt <asset> "<prompt>"` |

## 安全默认值 / Safe Defaults

- 默认不加 `--fix`。  
  Do not add `--fix` unless the user explicitly asks.
- 默认保留 init rules。  
  Keep init rules enabled by default.
- 默认保留 variants。  
  Keep variants enabled by default.
- 如果没有命中特定规则，回退到标准校验。  
  Fall back to standard validation if no specific rule was matched.

## 常见规则名 / Common Rule Names

- `StageMetadataChecker`
- `DefaultPrimChecker`
- `MissingReferenceChecker`
- `TextureChecker`
- `KindChecker`
- `ValidateTopologyChecker`
- `NormalsValidChecker`
- `ExtentsChecker`

## 示例 / Examples

```bash
omni-asset-cli validate asset.usda
omni-asset-cli validate asset.usda --profile static
omni-asset-cli validate asset.usda --category Material
omni-asset-cli map asset.usda "check references and textures"
omni-asset-cli validate-from-prompt asset.usda "检查这个机器人资产适不适合抓取"
```

