# `KindChecker` 说明

## 中文说明

### 这条规则检查什么

`KindChecker` 检查 USD 层级里的 `kind` 语义是否合理。

它主要关心：

- 父子层级关系
- `assembly`、`group`、`component`、`subcomponent` 的使用位置
- 资产入口和结构语义是否清晰

### 为什么重要

对于 Isaac Sim、SimReady、机器人交互类资产，层级语义不清会影响下游工具理解资产。

### 常见修复方式

- 给父节点补 `group` 或 `assembly`
- 把真正的部件节点标成 `component`
- 去掉没有必要的 `kind`

### 一句话结论

`KindChecker` 不是所有资产都必须优先跑，但对结构语义敏感的资产非常重要。

## English

### What This Rule Checks

`KindChecker` checks whether `kind` semantics in the USD hierarchy are reasonable.

It mainly cares about:

- parent-child hierarchy
- where `assembly`, `group`, `component`, and `subcomponent` are used
- whether the asset entry point and structural semantics are clear

### Why It Matters

For Isaac Sim, SimReady, and robot-interaction assets, unclear hierarchy semantics can confuse downstream tools.

### Common Fixes

- add `group` or `assembly` to the parent node
- mark the real part nodes as `component`
- remove unnecessary `kind` assignments

### One-Line Conclusion

`KindChecker` is not always the top priority for every asset, but it is important for assets where structural semantics matter.

