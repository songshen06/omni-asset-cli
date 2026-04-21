# `KindChecker` 说明 / `KindChecker` Explained

## 这条规则检查什么 / What This Rule Checks

`KindChecker` 检查 USD 层级里的 `kind` 语义是否合理。  
`KindChecker` checks whether `kind` semantics in the USD hierarchy are reasonable.

它主要关心：
It mainly cares about:

- 父子层级关系  
  parent-child hierarchy
- `assembly`、`group`、`component`、`subcomponent` 的使用位置  
  where `assembly`, `group`, `component`, and `subcomponent` are used
- 资产入口和结构语义是否清晰  
  whether the asset entry point and structural semantics are clear

## 为什么重要 / Why It Matters

对于 Isaac Sim、SimReady、机器人交互类资产，层级语义不清会影响下游工具理解资产。  
For Isaac Sim, SimReady, and robot-interaction assets, unclear hierarchy semantics can confuse downstream tools.

## 常见好结构 / Common Good Structure

```text
/AssetRoot (assembly)
  /Body (component)
  /Handle (component)
```

## 常见坏结构 / Common Bad Structure

```text
/AssetRoot
  /Body (component)
  /Bolt (component)
```

问题在于父节点没有提供合适的语义上下文。  
The issue is that the parent node does not provide the right semantic context.

## 常见修复方式 / Common Fixes

- 给父节点补 `group` 或 `assembly`。  
  Add `group` or `assembly` to the parent node.
- 把真正的部件节点标成 `component`。  
  Mark the actual part nodes as `component`.
- 去掉没有必要的 `kind`。  
  Remove unnecessary `kind` assignments.

## 什么时候重点关注 / When to Prioritize It

- 用户明确提到 Isaac Sim  
  The user explicitly mentions Isaac Sim
- 用户明确提到 SimReady  
  The user explicitly mentions SimReady
- 用户关注抓取、搬运、机器人交互  
  The user cares about grasping, moving, or robot interaction
- 用户问层级、结构或组件语义  
  The user asks about hierarchy, structure, or component semantics

## 一句话结论 / One-Line Conclusion

`KindChecker` 不是所有资产都必须优先跑，但对结构语义敏感的资产非常重要。  
`KindChecker` is not always the top priority for every asset, but it is important for assets where structural semantics matter.

