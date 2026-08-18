# Foundation-backed 验证工作流

## 运行只读 shadow validation

Foundation 必须使用批准的 release tag 和独立环境。adapter 不内置或猜测上游
CLI；由部署方提供显式命令模板，避免上游 CLI 变化无声改变客户验收。

对于 Foundation `v2026.04.1`，必须将 validator 固定为
`simready-validate==2026.4.8`。该 tag 与后来版本的 validator registry API 不兼容，
使用较新版本会出现 profile 未注册的假部署失败。

已部署环境使用以下命令；`--official-cli` 会选择该 release 的官方 capabilities、
features 与 profiles，不需要手写路径：

```bash
python3 omni_asset_cli.py foundation-validate path/to/asset.usd \
  --package articulated-asset \
  --foundation-tag v2026.04.1 \
  --foundation-root /path/to/simready-foundation-v2026.04.1 \
  --foundation-python /path/to/foundation-venv/bin/python \
  --official-cli --shadow --out out/cart_foundation
```

等价的上游执行模板为：

```bash
{python}/simready-validate \
  --rules-path /opt/simready-foundation/nv_core/sr_specs/docs/capabilities \
  --features-path /opt/simready-foundation/nv_core/sr_specs/docs/features \
  --profiles-path /opt/simready-foundation/nv_core/sr_specs/docs/profiles/profiles.toml \
  --profile {profile} --version 1.0.0 --output {out} {asset}
```

`foundation-validate` 目前只展开 `{asset}`、`{profile}`、`{out}`、`{tag}` 与
`{python}`；将 Foundation 根目录写入固定命令即可。官方 executor 必须生成可解析
JSON，空输出即使退出码为 0 也会被标为失败，防止假阳性。

```bash
python3 omni_asset_cli.py foundation-validate path/to/asset.usd \
  --package articulated-asset \
  --foundation-tag <approved-release-tag> \
  --foundation-root /opt/simready-foundation \
  --foundation-python /opt/foundation-venv/bin/python \
  --foundation-command '{python} -m <foundation_executor> --asset {asset} --profile {profile} --output {out}' \
  --shadow --out out/cart_foundation
```

输出 `foundation_validation.json` 固定记录资产 SHA-256、release tag、解析出的
commit、内部套餐映射、原始执行命令和 requirement/prim 级 findings。没有配置
执行器、tag 不匹配或 Foundation 执行失败时，状态为 `blocked`/`failed`，不会被
当成通过。

## 受控修复链

```bash
python3 omni_asset_cli.py foundation-repair-plan \
  out/cart_foundation/foundation_validation.json --out out/cart_repair_plan

python3 omni_asset_cli.py apply-foundation-repair \
  out/cart_repair_plan/repair_plan.json --apply-safe --out out/cart_repair_apply
```

`repair_plan.json` 区分 `safe`、`opt_in`、`manual` 和 `not_applicable`。
候选产物始终写入新的输出目录，源文件不被覆盖。当前 adapter 在 Foundation
finding 未给出可确定 authoring 参数时只生成同哈希候选和审计记录；它不会猜测
joint、drive、limit、质量、语义或摩擦数值。

## 聚焦工作流：嵌套刚体与 collider schema

对被动 articulated cart，使用上游 `Prop-Robotics-Physx v1.0.0` 作为完整
Profile 基线，但在修复首轮仅阻断以下两条 requirement：

- `RB.006`：嵌套 `PhysicsRigidBodyAPI` 必须 reset transform stack，或改为扁平
  body-link 层级；
- `RB.COL.002`：`PhysicsMeshCollisionAPI` 只能应用于 `UsdGeomMesh`，不能用于
  `Cylinder`、`Cube`、`Sphere` 等 analytic primitive。

`RB.007`（质量）、`GSP.001`（grasp）和 `PMT.001`（physics material）会保留在
上游原始报告中，但此 workflow 标记为 deferred，不作为当前 gate。它并不意味着
完整 Profile 通过。

```bash
python3 omni_asset_cli.py articulated-physics-workflow path/to/cart.usda \
  --foundation-root /path/to/simready-foundation-v2026.04.1 \
  --foundation-python /path/to/foundation-venv/bin/python \
  --foundation-tag v2026.04.1 \
  --out out/cart_physics_structure
```

该命令产生四个可审计工件：`foundation/foundation_raw.json`（完整上游执行）、
`physics_structure/articulated_policy.json`（逐 prim 的 `RB.006`/`RB.COL.002`
清单）、`workflow.json`（本轮 scope 的单一结论）和
`articulated_physics_structure_report.html`（供审阅的 HTML 报告）。HTML 会明确
显示当前未修改源 USD、两类修复的 safe/manual 边界、受影响 prim、deferred
requirements 与后续复验链。workflow 会为 `RB.COL.002` 自动生成独立 candidate USD，
并对 candidate 同时重跑聚焦策略和完整上游 Profile；原始资产不会被覆盖。
修复顺序必须是先处理
`RB.COL.002` 的 schema，再由资产负责人批准质量和刚体层级/关节 frame 的重构；
不得用忽略质量范围的通过结论替代完整 Profile 或 runtime 验收。

## articulated-cart 静态策略

```bash
python3 omni_asset_cli.py articulated-cart-policy /home/horde/cart_v2.usda \
  --out out/cart_policy
```

策略报告检查刚体数、关节数、joint body relationship 和刚体图连通性。它不以
“数量正确”代替机构验收：轴向、连续旋转声明、摩擦材质和运行时关节运动仍须由
Inspector manifest 与 Isaac Sim Docker 测试共同确认。

该命令是本地 policy，不是 Foundation profile executor。正式使用
`Prop-Robotics-Physx` 前，必须提供冻结 release tag 的 Foundation checkout 和
官方执行命令，运行 `foundation-validate --shadow`，并在 20 个冻结回归资产上
记录官方 findings 与本地 policy 的差异。不要因本地 `articulated-cart-policy`
通过而标记为上游 profile 通过。

## 运行时边界

现有 `physics-hit-test` / `stage1-runtime` 继续作为碰撞 contact 证据链；渲染
任务先运行：

```bash
python3 omni_asset_cli.py physics-env --runtime-docker-container isaac-sim --require-gpu
```

只有 `contact_report_detected == true` 和
`contact_evidence_level == "detected"` 可作为强碰撞通过证据。关节运动专用
模板尚需在 Isaac Sim Docker 中实现可控推力和 wheel/swivel 角位移采样；在该
采样器完成前，不得用 top-drop 结果声称关节运动通过。
