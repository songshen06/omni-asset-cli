# cart_v2 关节资产与 Profile 讨论记录

## 资产观察

`~/cart_v2.usda` 是带四个万向脚轮的医疗推车关节资产，而非普通静态 prop。

- 根为 `/Root`，default prim、米单位和 Z-up 均已设置。
- `/Root/Cart` 有 articulation root、刚体和 8.5 kg 质量。
- 每组脚轮包含固定连接 `Cart → KingpinStem`、绕 Z 轴转向的 `KingpinStem → Yoke`，以及绕 Y 轴滚动的 `Yoke → Wheel`。
- 共有 12 个关节、13 个刚体 schema、82 个碰撞体 schema。
- 关节有低阻尼 rotational drive，但没有 position/velocity target 或 limit。
- 未发现 PhysicsScene、关节 limit 或显式摩擦/回弹物理材质参数。

## 资产套餐定位

该资产应使用内部 `articulated-asset` 套餐：

```text
Foundation: Prop-Robotics-Physx + joint/multibody feature gate
Inspector: 结构和安全 authoring 诊断
omni-asset-cli: articulation runtime + wheel/swivel contact 验收
```

不使用 `Robot-Body-Runnable`：资产没有控制器、执行器目标或机器人控制接口，属于受外力推动的被动机构。

## 拓扑契约

```text
Cart (1)
├─ 4 × KingpinStem (4)
├─ 4 × Yoke (4)
└─ 4 × Wheel (4)
= 13 rigid bodies

每个脚轮：
Cart --固定--> KingpinStem --Z 轴 Revolute--> Yoke --Y 轴 Revolute--> Wheel
= 4 × 3 = 12 joints
```

数量自洽不是通过条件。Foundation 的 `Prop-Robotics-Physx` 负责通用 USD、PhysX、刚体、碰撞体和材质约束；本地 `articulated-cart` policy 负责以下机构设计契约：

| 检查 | 预期 |
| --- | --- |
| 刚体图 | 恰好 13 个，且均属于 articulation |
| 关节图 | 恰好 12 个；每个 joint 的 `body0`/`body1` 存在、不同且具有刚体 schema |
| 脚轮链 | 固定 Cart→Stem、Z 轴 swivel Stem→Yoke、Y 轴 wheel Yoke→Wheel |
| 连通性 | 全部 13 个刚体可由 `/Root/Cart` 经 joint 图到达，无孤立 body |
| 碰撞 | frame、yoke、轮胎等参与碰撞；hub/screw 等装饰件可排除 |
| 连续旋转 | Wheel 与 swivel 无 limit 必须以明确设计声明记录，而非默认漏检 |
| 摩擦 | 轮胎与地面应显式绑定 physics material，包含静摩擦、动摩擦和回弹策略 |
| 运行时 | 静置稳定、指定推力移动、wheel/swivel 有角位移、无穿透或异常速度，并有 contact report |

## Profile 使用方式

1. 对原始 `cart_v2.usda` 只读执行锁定版本的 `Prop-Robotics-Physx`，保存 requirement 级 findings。
2. 仅对验收后的派生产物或 overlay 记录 profile/version；不要给原始资产直接打合格标记。
3. 关节轴、drive、limit、摩擦具体数值及脚轮链路留在本地 manifest/policy，不让通用 profile 自动猜测机构设计意图。

示例 metadata：

```usda
customLayerData = {
    dictionary SimReady_Metadata = {
        string profile = "Prop-Robotics-Physx"
        string profile_version = "locked-version"
    }
}
```

## 优先风险与运行时验收

`/Root/Cart` 是刚体，其 `KingpinStem`、`Yoke`、`Wheel` 又是层级后代刚体。这套 joint 意图清晰，但 PhysX 对嵌套刚体/Xform stack 的接受性不能靠文本判断。因此，先将其作为 Foundation 静态检查和 Isaac Sim Docker smoke test 的高优先级风险；不要在缺乏运行时证据时自动调整层级。

运行时测试不应只有 top-drop，应覆盖：

```text
静置稳定 → 外力推行 → wheel/swivel 转动 → 接触、穿透与异常速度检查
```

碰撞通过首选证据是 `contact_report_detected == true` 且 `contact_evidence_level == "detected"`。关节轴、limit、drive 与摩擦数值的不符合项应作为上游 authoring/repair-plan 反馈，而不是由验收工具擅自改写。

## 参考

- [Foundation Profiles Validation Workflow](https://github.com/NVIDIA/simready-foundation/blob/main/nv_core/sr_specs/docs/guides/profiles_validation_workflow.md)
