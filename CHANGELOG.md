# 更新说明

## 2026-05-12

### Isaac Sim Docker Runtime

- 明确 runtime 物理验证只支持 Linux + Isaac Sim Docker 作为权威执行环境。
- 移除 WSL、Windows Isaac Sim Python、宿主机外部 Python runtime 的调度入口。
- `physics-env`、`physics-hit-test`、`simready-flywheel` 统一使用 `--runtime-docker-image` 或 `--runtime-docker-container`。
- 对 repo 外但位于 home 目录下的资产包增加自动 staging：例如 `/home/horde/new_3D/cup.usd` 会被复制到 `out/runtime_inputs/new_3D/cup.usd`，再从 Docker 内的 `/workspace/omni-asset-cli/out/runtime_inputs/new_3D/cup.usd` 运行。

### Runtime Contact Evidence

- `physics-hit-test` 现在会启用 PhysX contact report，并把真实接触事件写入 `runtime_report.json`。
- `summary.json` 新增 `checks.contact_report_detected` 和 `contact_evidence_level`。
- `contact_evidence_level: "detected"` 表示 Isaac Sim / PhysX 返回了真实 contact report；`"inferred"` 只表示基于 box 运动轨迹的弱推断。
- `runtime_report.json` 中的 `final_state.contact_report` 会记录事件数量、首次接触帧、参与接触的 actor/collider，以及接触目标类型，例如 `asset_subtree` 或 `guide_bbox`。

### Data Flywheel

- `simready-flywheel` 新增下游 runtime 失败反馈分类，用于把 Isaac Sim Docker 验证失败回灌给上游资产准备和修复步骤。
- 失败分类覆盖环境/调度、引用/资产包、collider authoring、bbox/placement、runtime motion、contact evidence 和 runtime quality。
- 文档和 agent 指南要求保存 `summary.json`、`runtime_report.json`、`timeline.csv`、Docker 镜像/容器、命令行和 staged asset path，作为可复现的 flywheel 记录。

### Agent 操作规范

- `AGENTS.md` 新增 runtime validation 操作规程：
  1. 先用 `physics-env` 验证 Isaac Sim Docker。
  2. 确认输入资产位于容器可读路径。
  3. repo 外 home 资产要 staging 到 `out/runtime_inputs/<asset_package>/`。
  4. 使用 Stage 1 `top-drop` hit test。
  5. 优先以 `contact_report_detected == true` 和 `contact_evidence_level == "detected"` 判断通过。
  6. 下游 fail 必须作为 data flywheel 信号回灌上游。

### 验证记录

- 使用 `/home/horde/new_3D/cup.usd` 验证了自动 staging 和 Isaac Sim Docker hit test。
- 生成的 `summary.json` 显示 `result: passed`、`checks.contact_report_detected: true`、`contact_evidence_level: detected`。
- `runtime_report.json` 显示第 22 帧 `/World/boxActor` 与资产 mesh `/World/roomScene/colliders/table/ReferencedAsset/mesh/mesh` 发生 PhysX contact report，首次事件包含 36 个 contact points。
