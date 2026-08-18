Exit code: 0
Wall time: 0.2 seconds
Output:
# SimReady Foundation 融合开发说明

## 状态与目标

本说明定义 `omni-asset-cli`、`usd-simready-inspector` 与 NVIDIA
SimReady Foundation 的职责边界和分阶段融合方式。

目标不是复制上游 validator、requirements 或 profiles，而是复用其规范，
将其转换为客户可执行的修复、运行时验收和可追溯交付服务。

## 三层职责

```text
SimReady Foundation
  官方 requirements / features / profiles（按 commit SHA 锁定）
             |
             v
usd-simready-inspector
  诊断、修复计划、受控 USD 修复产物
             |
             v
omni-asset-cli
  静态复验、Isaac Sim Docker 运行时验收、工件/API/客户报告
```

### SimReady Foundation

- 规范的上游来源：requirements、features 与 profiles。
- 只以固定 commit SHA 引用；上游更新不能无声改变客户验收结果。
- 通过隔离的 Python 3.12 环境调用，不与现有生产 validator 环境强行混装。
- 不 fork、不复制 profile 定义、不将其内部 CLI 直接暴露为客户接口。

### `usd-simready-inspector`

- 接收静态验证 findings，结合自身 mesh preflight 生成修复计划。
- 负责原始资产到候选修复资产的转换，但不承担最终生产通过判定。
- 默认不改写原文件；输出修复后的 USD 或 overlay layer，以及可回滚的修复记录。
- 不猜测设计意图：关节轴、limit、驱动参数、真实质量和语义分类默认只报告或要求审批。

### `omni-asset-cli`

- 保持现有生产 CLI、REST API、job 状态和工件契约兼容。
- 调用 Foundation 静态验证并规范化结果；执行最终静态复验。
- 使用 Isaac Sim Docker 执行运行时测试，维护 `summary.json`、
  `runtime_report.json`、`timeline.csv` 等客户证据链。
- 对碰撞验收，`contact_report_detected == true` 且
  `contact_evidence_level == "detected"` 是强通过证据；渲染、bbox 与
  motion-only inference 仅为辅助证据。

## Profile 选择与客户映射

第一阶段只接入下列官方目标，采用 shadow validation，不改变现有客户
pass/fail 结论：

| 内部客户套餐 | Foundation 基线 | 适用资产 | 额外 gate |
| --- | --- | --- | --- |
| `static-prop` | `Prop-Robotics-Neutral` | 仅渲染、资产库整理、静态视觉 mesh | mesh preflight 与安全修复计划 |
| `physics-prop` | `Prop-Robotics-Physx` | 可摆放、跌落、抓取或碰撞的道具/家具 | PhysX contact / top-drop |
| `articulated-asset` | `Prop-Robotics-Physx` + joint/multibody feature gate | 小推车、铰链件、轮组、夹具、可动机构 | joint motion + contact |
| `runnable-robot` | `Robot-Body-Runnable`（按需启用） | 有执行器、控制输入、运行要求的机器人本体 | drive / state / contact |

不要将客户直接暴露给上游 profile 名称。客户接口继续使用稳定的内部
套餐名；映射表必须记录 Foundation commit、profile、feature 版本和本地
运行时 gates。

`Robot-Body-Neutral` 与 `Robot-Body-Runnable` 不作为普通家具、道具或
静态小推车的默认选择。只有资产确实具有机器人本体语义或可执行控制
需求时才启用。

## 资产处理顺序

```text
1. Foundation 静态验证（原始资产，只读）
2. Inspector mesh preflight + 归因
3. Inspector repair plan（只生成计划）
4. 显式批准后生成 repaired.usda 或 repair.overlay.usda
5. Foundation 静态复验（修复产物）
6. omni-asset-cli 原有静态验证
7. Isaac Sim Docker 运行时验收
8. 归档 manifest、报告、日志和媒体证据
```

失败应回流到上游准备或修复阶段：例如 collider、缩放、placement、
contact instrumentation 或 mesh 修复策略，而不是孤立地标记为一次运行时
测试失败。

## 修复策略

| 类别 | 默认策略 | 示例 |
| --- | --- | --- |
| 低风险 authoring | 可自动执行 | default prim、单位/轴向元数据、extent、缺失 schema、法线 |
| 受控 mesh 修复 | 必须 opt-in | weld 顶点、删除零面积面、移除孤立面、统一 winding |
| 高风险几何修复 | 只输出计划 | 补洞、自交修复、重拓扑、UV 或材质重投影 |
| 物理能力补全 | 由套餐决定 | collider proxy、PhysicsCollisionAPI；Neutral 不添加 PhysX |
| 机构设计意图 | 只检查与报告 | joint body、轴、limit、drive、质量、碰撞过滤 |

每一项已执行修复必须记录：触发 requirement/feature、目标 prim、前后
mesh 统计、风险级别、输入哈希、输出路径、工具版本与回滚路径。

## 小推车与关节资产

### 静态或不可动小推车

使用 `physics-prop`。重点检查 collider、物理尺度、质量和稳定接触；
运行 top-drop 或指定接触测试。

### 可推行小车、轮组与铰链件

使用 `articulated-asset`。除物理 prop 基线外，还应检查：

- joint 两端刚体路径存在且连接有效；
- axis、limit、初始姿态与单位明确；
- 轮子或活动部件具有适当 collision/filtering；
- 无驱动时的自由运动，以及有驱动时的期望运动（若适用）；
- 运动过程中的 contact report、穿透、卡死与异常速度。

不得自动改变关节轴、limit 或 drive 参数来获得绿灯，因为那会把设计
意图替换为工具猜测。

## 分阶段实施计划

### Phase 0：生产基线保护

1. 为当前 `omni-asset-cli` 发布 v1/tag，冻结 CLI、REST 路由与现有
   报告字段语义。
2. 建立历史资产集，覆盖静态道具、家具、小推车、关节件与已知失败样本。
3. 为每个样本保存输入哈希、当前静态结果与当前 Docker 运行时结果。

验收：原有生产任务没有行为变化。

### Phase 1：Foundation 只读适配器

1. 在 `omni-asset-cli` 新增内部 `foundation-validate` adapter。
2. 输入：资产、内部套餐、Foundation commit/profile/config。
3. 输出：`foundation_validation.json` 与版本化 metadata。
4. 对历史集执行 shadow validation；只展示差异，不影响生产状态。

验收：每次验证均可由固定 SHA、命令行、输入哈希和 JSON 结果复现。

### Phase 2：标准 findings 契约

定义两项目共享的 `foundation_findings.json`，至少包含：

```json
{
  "schema_version": "1.0",
  "asset": {"path": "...", "sha256": "..."},
  "foundation": {"commit": "...", "profile": "...", "features": []},
  "findings": [
    {
      "requirement_id": "...",
      "feature_id": "...",
      "severity": "error",
      "prim_path": "/World/...",
      "message": "...",
      "repairability": "safe|opt_in|manual|not_applicable"
    }
  ]
}
```

验收：Inspector 不依赖 Foundation 的原始文本输出格式。

### Phase 3：Inspector 修复计划与低风险修复

1. 新增 `foundation-repair-plan`，只输出 `repair_plan.json`。
2. 先实现失败频率最高且低风险的 2--3 类修复。
3. 新增显式 `apply`；每次输出新文件或 overlay，不覆盖源资产。
4. 对每次修复执行 Foundation 复验，并比较修复前后 findings。

验收：修复操作可回滚；无批准时不会对源 USD 发生写入。

### Phase 4：运行时套餐验收

1. `physics-prop` 运行现有 Docker `physics-hit-test`。
2. `articulated-asset` 增加 joint-motion 测试模板和结构化 runtime report。
3. 失败统一分类为 environment、authoring、mesh、collider/contact、
   placement、scale、motion 或 joint-configuration，并回流 repair plan。

验收：每一个通过的 physics/articulated 资产都有接触或运动的结构化证据，
而不是仅靠视频判断。

### Phase 5：受控发布

1. 先让选定客户采用 `foundation-backed` 可选套餐。
2. 记录旧链路与新链路的通过率、误报、人工干预率和运行时失败类型。
3. 仅在数据证明兼容后，才把某个内部套餐的默认静态 gate 切换到
   Foundation-backed；始终保留回退版本。

## 非目标

- 不取代 SimReady Foundation 的 requirements、features、profiles 或其维护流程。
- 不把 Foundation profile 通过视为 Isaac Sim 运行时通过。
- 不为获得验证绿灯而无批准修改视觉外形、UV、材质或机构设计意图。
- 不将 Docker/Kit 的运行时依赖引入 Inspector 的纯诊断路径。

## 首个可执行里程碑

完成 `omni-asset-cli foundation-validate --shadow` 和
`foundation_validation.json`，用 20 个历史资产分别跑
`Prop-Robotics-Neutral` 与 `Prop-Robotics-Physx`。在得到失败分布前，不实现
自动 mesh 修复，也不改变客户生产验收结论。

## 当前实现状态与上游 Profile 对齐

当前 `foundation-validate`、`foundation-repair-plan` 与
`articulated-cart-policy` 已作为 CLI/工件优先的基础实现落地。后者是本地
机构策略，只检查刚体/关节图和连通性；它不是 NVIDIA SimReady Foundation
profile 的副本，也不能被表述为上游 profile 通过。

下一阶段必须完成上游对齐后，才可将 Foundation-backed 结果纳入套餐验收：

1. 选定并冻结一个 Foundation release tag，并记录对应 commit SHA、profile
   文件、feature 清单与独立 Python 3.12 环境。
2. 用该 tag 的官方 executor 对 20 个冻结资产运行 shadow validation；首批
   包括 `static-prop`、`physics-prop`、`articulated-asset` 与已知失败样本。
3. 将官方 requirement/feature/prim finding 映射到
   `foundation_findings.json`，保留原始 JSON 和执行命令，禁止仅根据文本摘要
   推断通过状态。
4. 对 `articulated-cart` 做规则差异表：Foundation 负责通用 USD/PhysX/
   collider 基线；本地策略只补充四脚轮链、连续旋转设计声明、摩擦策略与
   运行时 wheel/swivel motion gate，不能覆盖或重定义上游规则。
5. 只有在 20 个资产的差异、误报和人工干预率经审阅后，才允许把某个内部
   套餐的默认静态 gate 切换为 Foundation-backed；在此之前保持 shadow。

## 开发日记：Foundation CLI 部署与首个官方 Profile 运行（2026-08-14）

### Git 对齐

- 执行 `git fetch --prune` 后，`main` 与 `origin/main` 的 ahead/behind 均为
  `0`；本轮工作区已有的 Foundation、物理渲染和文档改动保持为未提交状态，未
  执行 pull、rebase、stash 或覆盖操作。

### 部署故障与根因

- Foundation checkout 固定为 `v2026.04.1`，commit
  `a1e9dd68ee2d107f74dc6cd6da875b54ad3f8fd3`，使用独立 Python 3.12 环境。
- 初始 `simready-validate==2026.6.4` 会跳过全部 requirement/feature，最终报
  `Prop-Robotics-Physx` 未注册。该状态是 validator 与该 Foundation tag 的
  registry API 不兼容，不是 cart 的 profile 结果。
- 按该 release 的兼容基线固定为 `simready-validate==2026.4.8` 后，官方
  capabilities、features 和 `profiles.toml` 可以完整注册；不再依赖发布包中
  缺失的 Repo/Packman bootstrap 入口。

### CLI 与工件改动

- `omni_asset_cli.py foundation-validate` 新增 `--official-cli`。它根据
  `--foundation-root` 自动组织官方 capabilities、features、profiles 路径，仍
  保留显式 `--foundation-command` 作为通用 adapter 路径。
- `run_foundation_validation.py` 识别 `simready-validate --output` 的
  `{asset_path: {features_summary: ...}}` JSON 格式，将失败 feature 与其 failing
  requirements 归一化为 findings；无可解析 JSON 时不允许通过。
- CLI 的成功只表示 executor 正常运行且全部 feature 通过；profile 未注册、执行
  非零退出、JSON 无法解析或任一 feature 失败均不能标为通过。

### 首个真实 Profile 检测

```bash
python3 omni_asset_cli.py foundation-validate out/runtime_inputs/cart_v2/cart_v2.usda \
  --package articulated-asset --foundation-tag v2026.04.1 \
  --foundation-root /tmp/simready-foundation-v2026.04.1 \
  --foundation-python /tmp/simready-foundation-v2026.04.1/.venv/bin/python \
  --official-cli --shadow --out out/cart_v2_foundation_official
```

- `Prop-Robotics-Physx v1.0.0` 已实际注册并运行；结果为资产失败，而非部署失败。
- 原始上游输出：
  `out/cart_v2_foundation_official/foundation_raw.json`；项目归一化结果：
  `out/cart_v2_foundation_official/foundation_validation.json`。
- 失败 feature 为 `FET000_CORE`、`FET003_BASE_NEUTRAL`、
  `FET003_BASE_PHYSX`、`FET004_BASE_PHYSX`、`FET005_BASE_NEUTRAL`；涉及
  `NP.006`、`RB.006`、`RB.007`、`RB.COL.002`、`COL.001`、`GSP.001`、
  `PMT.001`。这些是上游静态 authoring finding；尚未改变 USD，也不能替代
  Isaac Sim Docker 的 contact/joint motion runtime evidence。

### 后续

1. 用同一固定环境在冻结回归资产集执行 shadow validation，并保留原始 JSON。
2. 针对每一条官方 finding 创建可审计 repair plan；质量、碰撞近似、摩擦材质、
   grasp vector 与关节设计意图均先人工确认，不做自动猜测修复。
3. 完成修复后，以相同 Profile 命令复验，并补充 Isaac Sim Docker 的碰撞接触和
   wheel/swivel 运动证据。
