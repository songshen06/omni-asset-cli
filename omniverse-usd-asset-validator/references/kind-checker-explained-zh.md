# `KindChecker` 通用说明

## 1. 这条规则检查什么

`KindChecker` 是一个面向 USD 结构语义的规则。

它检查的不是 mesh 几何质量，而是：

- 一个 prim 被标记成什么 `kind`
- 这个 `kind` 放在当前层级位置是否合理
- 父子节点之间的模型层级关系是否符合 USD 约定

常见的 `kind` 包括：

- `assembly`
- `group`
- `component`
- `subcomponent`

这条规则在 Isaac Sim 场景下尤其重要，因为 Isaac Sim 官方的 `Asset Structure` 文档明确强调：

- 资产在进入仿真前应经过 transformation
- 应创建适合仿真的结构
- 应按需要分离 visuals 和 colliders
- 应调整 hierarchy 以符合 simulation requirements

参考文档：

- https://docs.isaacsim.omniverse.nvidia.com/6.0.0/robot_setup/asset_structure.html

## 2. 什么是 `kind`

可以把 `kind` 理解为：

> 一个 prim 在资产层级中的“角色标签”

例如：

- `assembly`
  表示总装、完整资产或较高层装配

- `group`
  表示逻辑分组、中间层级、组织节点

- `component`
  表示可以作为独立组件理解的对象

- `subcomponent`
  表示 component 内部更细的组成部分

这些标签不是装饰字段，而是很多工具识别资产结构的重要依据。

## 3. 为什么这个规则重要

如果 `kind` 使用混乱，会出现这些问题：

- 工具无法判断哪个节点才是完整资产
- 组件、分组、几何节点之间的角色边界不清晰
- 实例化、装配管理、层级浏览和筛选行为容易异常
- 不同 USD 工具链对该资产的解释可能不一致

所以 `KindChecker` 的本质作用是：

> 确保 USD 资产不仅“能打开”，而且结构语义清晰、可被稳定消费。

在 Isaac Sim / SimReady / 机器人资产制作里，这个作用会进一步放大，因为后续 physics、robot schema、语义标签、交互逻辑和自动化处理都依赖清晰的层级语义。

## 4. `KindChecker` 在检查什么关系

最常见的一类检查是：

> 一个 `component` 是否被放在了允许承载它的父节点下面

例如，典型错误会像这样：

```text
Invalid Kind "component". Model prims can only be parented under "('assembly', 'group')" prims.
```

翻译成更好理解的话：

> 你把这个 prim 标成了 `component`，但它的父节点不是合格的装配层或分组层，所以它的位置不对。

## 5. 常见的好层级

一个常见且合理的模型层级可能是：

```text
/RobotRoot                    kind=assembly
├── Torso                     kind=component
│   ├── visuals               kind=group 或无 kind
│   │   └── mesh
│   └── collisions            kind=group 或无 kind
│       └── mesh
├── LeftArm                   kind=component
│   ├── visuals
│   └── collisions
└── RightArm                  kind=component
```

这个结构的特点是：

- 最顶层是总装 `assembly`
- 中间真正的零部件是 `component`
- `visuals` / `collisions` 更像组织层，不一定需要 `component`
- mesh 节点本身通常不承担装配语义

## 6. 常见的坏层级

容易出问题的结构通常像这样：

```text
/RobotRoot
└── visuals
    └── imported_mesh_node    kind=component
        └── mesh
```

或者：

```text
/RobotRoot
└── collisions
    └── node_STL_BINARY_      kind=component
        └── mesh
```

这类结构的问题是：

- `component` 被贴在导入中间节点上
- 父节点只是视觉分组或碰撞分组，不是真正的装配层
- 结果是“角色标签”和“层级位置”不匹配

这也意味着资产还停留在“导入结果结构”，而没有充分整理成 Isaac Sim 所需要的“仿真友好结构”。

## 7. 最容易犯错的场景

`KindChecker` 报错最常见的来源包括：

1. 从 CAD / STL / FBX 导入时保留了大量中间包装节点
2. 自动导出器给导入节点统一贴了 `component`
3. `visuals` / `collisions` / `geometry` 这类组织层被误当成装配层
4. 复制粘贴 prim 时保留了不适合的 `kind`

## 8. 怎么理解“不是所有节点都需要 kind”

很多人第一次用 USD 时容易误解：

> 既然有 `kind`，是不是每个节点都应该加一个？

不是。

通常只有那些真正承担装配语义的节点，才需要认真建模 `kind`。

例如：

- 总装节点适合 `assembly`
- 部件节点适合 `component`
- 中间逻辑分组适合 `group`
- 纯几何容器、导入噪声节点、表现层节点，往往不需要强行标成 `component`

## 9. 常见修复方式

### 方案 A：把 `component` 上提到真正的部件节点

例如把：

- `pelvis`
- `left_arm`
- `torso`

这类真正的组件节点标成 `component`。

而不是把：

- `node_STL_BINARY_`
- `mesh_container`
- `visuals`

这类中间层节点标成 `component`。

### 方案 B：给父节点补 `group` 或 `assembly`

如果一个节点确实应该是 `component`，但父节点层级不够明确，可以让父节点先成为合法的 `group` 或 `assembly`。

### 方案 C：移除不必要的 `kind`

如果一个节点只是导入过程产生的包装层，而且没有装配语义，最简单的修法通常是：

- 不给它设置 `component`
- 保持普通 `Xform` 或普通组织节点

## 10. 怎么判断谁该是 `component`

一个实用判断标准是：

> 如果你把这个节点当成“独立零件、独立模块、独立部件”来理解是合理的，那它更适合 `component`。

反过来：

> 如果它只是“为了组织 mesh 才存在”的节点，通常不应该承担 `component` 语义。

## 11. 一句话结论

`KindChecker` 检查的是：

> 你的 USD 资产里，每个节点承担的“装配角色”是否和它所在的层级位置一致。

如果它报错，通常说明：

> 资产的结构语义不清晰，导入节点、组织节点和真实组件节点之间的边界混淆了。

如果放到 Isaac Sim 官方资产结构的语境下，这又可以理解为：

> 资产尚未完成从 source/import hierarchy 到 simulation-friendly hierarchy 的必要 transformation。

## 12. 使用建议

在人工阅读报告时，如果看到 `KindChecker` 数量很高，建议优先做以下动作：

1. 找出所有被标成 `component` 的节点
2. 查看这些节点的父节点是不是 `assembly` 或 `group`
3. 把真正的部件节点和导入包装节点区分开
4. 重新整理 `kind` 分配

对于大型资产，`KindChecker` 通常不是“单条报错”，而是一个结构设计信号。
