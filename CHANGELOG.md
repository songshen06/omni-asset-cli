# 更新说明

## 2026-05-27

### 中文

- `physics-hit-test` 新增多镜头渲染取证能力，可通过 `--render-camera-preset` 捕获 front、side、top、iso 等视角，并将 PNG 输出到 `OUT/render_frames/<camera>/`。
- 新增 `--render-video` 与 `--render-video-style`，支持直接生成每个镜头的 mp4；`asset-table-drop` 风格会复用独立资产下落渲染器，视觉输出更接近已验证的视频证据流程。
- 新增 Replicator/viewport 渲染后端选择、分辨率、RT subframes、等待更新、视频 fps/CRF、材质模式和镜头参数，便于在同一条 runtime 命令中生成可复现取证素材。
- runtime harness 新增 `replace-box` placement、资产 Y/Z 初始旋转、动态资产 bbox overlay、容器 preflight 策略，以及更详细的 progress/runtime report 字段。
- REST API 的 collision 请求模型和后台 worker 已透传渲染视频、多镜头、Docker preflight 等参数，异步服务可以产出同类 runtime artifacts。
- 新增 `render_asset_table_drop.py`、`render_asset_setup_orbit.py` 和 `check_stage_mdl_load.py` 辅助脚本，用于资产下落视频、setup orbit 取证和 Isaac Sim MDL 加载检查。
- 更新部署文档和 agent 技能说明，补充多镜头 mp4 取证命令示例，并强调权威碰撞结论仍以 `summary.json` 和 `runtime_report.json` 的 PhysX contact evidence 为准。
- 测试覆盖了 service worker 对新 collision 渲染参数的命令构造。

### English

- Added multi-camera rendered evidence for `physics-hit-test`; `--render-camera-preset` can capture front, side, top, iso, and related views under `OUT/render_frames/<camera>/`.
- Added `--render-video` and `--render-video-style` so runtime runs can emit one mp4 per camera; `asset-table-drop` delegates to the standalone falling-asset renderer for the validated visual evidence style.
- Added Replicator/viewport backend selection, render resolution, RT subframes, wait updates, video fps/CRF, material modes, and camera tuning options for reproducible evidence from one runtime command.
- Extended the runtime harness with `replace-box` placement, initial asset Y/Z rotation, dynamic asset bbox overlays, Docker container preflight policy, and richer progress/runtime report metadata.
- The REST API collision request schema and background worker now pass through video rendering, multi-camera, and Docker preflight options for async artifact generation.
- Added helper scripts for asset table-drop video rendering, setup orbit evidence rendering, and Isaac Sim MDL stage-load checks: `render_asset_table_drop.py`, `render_asset_setup_orbit.py`, and `check_stage_mdl_load.py`.
- Updated deployment and agent guidance with multi-camera mp4 evidence examples, while keeping `summary.json` and `runtime_report.json` PhysX contact evidence as the authoritative collision result.
- Tests now cover service worker command construction for the new collision rendering options.

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
