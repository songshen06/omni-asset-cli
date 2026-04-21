# 自然语言到参数 / Natural Language to Arguments

## 默认策略 / Default Strategy

- 没命中特定规则时，回退到标准校验。  
  Fall back to standard validation when no specific rule is matched.
- 不自动加 `--fix`。  
  Do not add `--fix` automatically.
- 除非用户明确缩小范围，否则保留默认规则。  
  Keep the default rules unless the user explicitly narrows the scope.

## 常见映射 / Common Mapping

| 中文请求 | English request | 推荐参数 / Recommended arguments |
| --- | --- | --- |
| 检查这个资产 | check this asset | `validate <asset>` |
| 检查基础元数据 | check stage metadata | `validate <asset> --rule StageMetadataChecker` |
| 检查引用 | check references | `validate <asset> --rule MissingReferenceChecker` |
| 检查 Isaac Sim 结构 | check Isaac Sim structure | `validate <asset> --rule KindChecker` |
| 检查 topology | check topology | `validate <asset> --rule ValidateTopologyChecker` |
| 检查 normals | check normals | `validate <asset> --rule NormalsValidChecker` |
| 只看 geometry | check geometry only | `validate <asset> --category Geometry` |
| 只看 material | check material only | `validate <asset> --category Material` |
| 只看 physics | check physics only | `validate <asset> --category Physics` |
| 只看错误 | show errors only | `validate <asset> --predicate IsError` |
| 按静态资产检查 | validate as static | `validate <asset> --profile static` |
| 按可碰撞资产检查 | validate as collidable | `validate <asset> --profile collidable` |
| 按可移动资产检查 | validate as movable | `validate <asset> --profile movable` |

## 示例 / Examples

```bash
omni-asset-cli map asset.usda "check references"
omni-asset-cli map asset.usda "检查 Isaac Sim 结构"
omni-asset-cli validate-from-prompt asset.usda "帮我按静态资产场景检查"
omni-asset-cli validate-from-prompt asset.usda "validate this as a movable asset"
```

## 当前建议 / Current Recommendation

自然语言入口优先使用：
Prefer these natural-language entry points:

- `omni-asset-cli map`
- `omni-asset-cli validate-from-prompt`

