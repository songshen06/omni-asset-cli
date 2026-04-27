# 自然语言到参数

## 中文说明

### 默认策略

- 没命中特定规则时，回退到标准校验
- 不自动加 `--fix`
- 除非用户明确缩小范围，否则保留默认规则

### 常见映射

| 中文请求 | 推荐参数 |
| --- | --- |
| 检查这个资产 | `validate <asset>` |
| 按家具和摆件 Stage 1 检查 | `validate <asset> --profile stage1-furniture` |
| 检查静态家具和装饰道具 | `validate <asset> --profile stage1-furniture` |
| 检查基础元数据 | `validate <asset> --rule StageMetadataChecker` |
| 检查引用 | `validate <asset> --rule MissingReferenceChecker` |
| 检查 Isaac Sim 结构 | `validate <asset> --rule KindChecker` |
| 检查 topology | `validate <asset> --rule ValidateTopologyChecker` |
| 检查 normals | `validate <asset> --rule NormalsValidChecker` |
| 只看 geometry | `validate <asset> --category Geometry` |
| 只看 material | `validate <asset> --category Material` |
| 只看 physics | `validate <asset> --category Physics` |
| 只看错误 | `validate <asset> --predicate IsError` |
| 按静态资产检查 | `validate <asset> --profile static` |
| 按可碰撞资产检查 | `validate <asset> --profile collidable` |
| 按可移动资产检查 | `validate <asset> --profile movable` |

## English

### Default Strategy

- Fall back to standard validation when no specific rule is matched
- Do not add `--fix` automatically
- Keep the default rules unless the user explicitly narrows the scope

### Common Mapping

| Request | Recommended arguments |
| --- | --- |
| check this asset | `validate <asset>` |
| validate Stage 1 furniture and props | `validate <asset> --profile stage1-furniture` |
| validate static furniture and decor props | `validate <asset> --profile stage1-furniture` |
| check stage metadata | `validate <asset> --rule StageMetadataChecker` |
| check references | `validate <asset> --rule MissingReferenceChecker` |
| check Isaac Sim structure | `validate <asset> --rule KindChecker` |
| check topology | `validate <asset> --rule ValidateTopologyChecker` |
| check normals | `validate <asset> --rule NormalsValidChecker` |
| check geometry only | `validate <asset> --category Geometry` |
| check material only | `validate <asset> --category Material` |
| check physics only | `validate <asset> --category Physics` |
| show errors only | `validate <asset> --predicate IsError` |
| validate as static | `validate <asset> --profile static` |
| validate as collidable | `validate <asset> --profile collidable` |
| validate as movable | `validate <asset> --profile movable` |
