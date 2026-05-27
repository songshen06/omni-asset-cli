# omni-asset-cli 中文使用文档

## 项目简介

`omni-asset-cli` 是一个面向 OpenUSD 资产校验的统一 CLI，基于 NVIDIA Omniverse Asset Validator。当前 Stage 1 主线对齐到静态家具、摆件和装饰道具。

它提供：

- 统一命令入口 `omni-asset-cli`
- 同步 validator 校验主路径
- JSON 和 Markdown 输出
- `stage1-furniture` 家具/摆件推荐 profile
- 兼容旧 profile：`static`、`collidable`、`movable`
- 面向 AI agent 的自然语言映射入口
- Isaac Sim Docker runtime 物理碰撞 smoke test
- 可选 PNG/MP4 渲染取证和 physics bbox overlay

## 安装

安装当前项目：

```bash
python3 -m pip install --no-build-isolation -e .
```

安装当前项目和 validator 依赖：

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

如果暂时不安装 console script，也可以直接运行源码入口：

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda --profile stage1-furniture
```

## 静态 USD 校验

检查环境：

```bash
omni-asset-cli env
```

校验单个 USD 资产：

```bash
omni-asset-cli validate path/to/asset.usd
```

按 Stage 1 家具/摆件场景应用推荐规则：

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
```

输出 JSON 和 Markdown：

```bash
python3 omni_asset_cli.py validate examples/minimal_scene.usda \
  --profile stage1-furniture \
  --output-json out/minimal_scene_validator.json \
  --output-md out/minimal_scene_validator.md
```

旧 profile 仍然保留，便于兼容已有脚本：

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

## Isaac Sim Docker Runtime

本项目推荐把普通 USD 静态检查和 Isaac Sim runtime 物理检查分开：

- 宿主机 Python 运行 `validate` 并生成 validator 报告
- Linux + Isaac Sim Docker 运行 `physics-hit-test` 物理 smoke test
- 测试资产、模板和输出目录通过仓库挂载在宿主机与容器之间共享
- repo 外但位于 home 目录下的资产会被 staging 到 `out/runtime_inputs/`

权威 runtime 检查只支持 Linux + Isaac Sim Docker。非 Docker runtime 不作为权威物理检查环境。

### Runtime 环境探测

优先复用已经启动、并挂载当前仓库的 Isaac Sim 容器：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim
```

也可以用镜像启动一次性 Docker 运行：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

期望结果中应包含：

```text
probe.ready = true
simulation_app_available = true
```

### Stage 1 Top-Drop Hit Test

家具：替换模板里的桌子。

```bash
python3 omni_asset_cli.py physics-hit-test path/to/chair_or_table.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/furniture_template_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

摆件：保留模板桌子，把资产放到桌面中心。

```bash
python3 omni_asset_cli.py physics-hit-test path/to/cup_or_decor.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode tabletop \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/prop_tabletop_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

`examples/mini_test.usda` 是 Stage 1 家具/摆件模板场景。它包含桌面、静态碰撞体和动态 `/World/boxActor`。推荐组合是 `--hit-mode top-drop --size-policy preserve`，以保留目标资产真实 bbox，并从资产上方掉落动态 box。

## Runtime 输出和通过条件

`physics-hit-test` 会写出：

- `summary.json`
- `runtime_report.json`
- `timeline.csv`
- 生成的测试 stage
- 可选 `render_frames/` 和 `render_videos/`

核心字段：

```text
result
checks.asset_loaded
checks.static_colliders_applied
checks.dynamic_box_created
checks.simulation_advanced
checks.hit_targeted
checks.contact_report_detected
checks.contact_detected_or_inferred
contact_evidence_level
```

优先使用强 contact evidence：

```text
checks.contact_report_detected == true
contact_evidence_level == detected
```

`contact_report_detected` 来自 PhysX contact report，比 bbox 运动轨迹推断更强。`contact_evidence_level == inferred` 只表示满足运动轨迹推断条件，不应当等同于真实 PhysX contact event。

## 渲染取证和视频

在同一条 runtime 命令中捕获多镜头 PNG 和 MP4：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --render-video \
  --render-video-style asset-table-drop \
  --render-camera-preset front \
  --render-camera-preset side \
  --render-camera-preset top \
  --render-every-n-frames 2 \
  --render-video-fps 30 \
  --out out/minimal_scene_docker_hit_video \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

输出位置：

- PNG 帧：`OUT/render_frames/<camera>/`
- MP4 视频：`OUT/render_videos/<camera>.mp4`

`--render-video-style hit-test` 捕获同一轮 hit-test 场景。`--render-video-style asset-table-drop` 会委托给 `render_asset_table_drop.py`，用于生成更稳定的资产下落视频。视频是视觉证据，权威碰撞结论仍以 `summary.json` 和 `runtime_report.json` 的 PhysX contact report 为准。

如果需要渲染 physics bbox evidence，继续使用同一个 runtime harness：

```bash
--render-frames --render-physics-bboxes
```

`--render-physics-bbox-fallback-default-prim` 只用于调试没有 collider paths 的捕获问题，不应把 fallback bbox 当成真实 physics collider evidence。

## REST API 服务

部署 REST API 服务入口推荐使用脚本创建独立虚拟环境、安装 API 依赖并生成本地 env 文件：

```bash
scripts/deploy_api_service.sh --write-env
source .env.omni-asset-service
.venv-api/bin/omni-asset-service --host 0.0.0.0 --port 8000
```

开发环境也可以手动安装 API extra：

```bash
python3 -m pip install --no-build-isolation -e ".[api]"
```

最小本地启动示例：

```bash
export OMNI_SERVICE_STORAGE_ROOT="$PWD/out/omni-asset-service"
export OMNI_SERVICE_API_KEYS=dev-secret:tenant_a:project_a
export ISAAC_CONTAINERS=isaac-sim-0
export DOCKER_WORKSPACE=/workspace/omni-asset-cli
export DOCKER_PYTHON=/isaac-sim/python.sh
export OMNI_SERVICE_JOB_TIMEOUT_SECONDS=7200

omni-asset-service --host 0.0.0.0 --port 8000
```

核心接口：

```text
POST /v1/projects/{project_id}/assets
POST /v1/projects/{project_id}/tests/mesh
POST /v1/projects/{project_id}/tests/collision
GET  /v1/projects/{project_id}/jobs/{job_id}
GET  /v1/projects/{project_id}/jobs/{job_id}/report/summary
GET  /v1/projects/{project_id}/jobs/{job_id}/report/runtime
GET  /v1/projects/{project_id}/jobs/{job_id}/artifacts
GET  /v1/projects/{project_id}/jobs/{job_id}/artifacts/{artifact_id}
```

所有请求使用 `X-API-Key` 认证。API 不接受任意服务器路径；必须先上传 `.zip` 或 `.usd/.usda/.usdc` 资产包，再用返回的 `asset_id` 创建测试 job。

## AI Agent 命令

把自然语言映射成确定性参数：

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "按家具和摆件 Stage 1 检查"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

从自然语言直接执行校验：

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "按家具和摆件 Stage 1 检查"
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as static furniture and decor props"
```

## 目录结构

```text
omni_asset_cli.py
omni_asset_service/
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
docs/
```

更多部署和运维细节见：

- [DEPLOYMENT.md](../DEPLOYMENT.md)
- [CHANGELOG.md](../CHANGELOG.md)
- [omni-asset-cli-agent/SKILL.md](../omni-asset-cli-agent/SKILL.md)
- [omniverse-usd-asset-validator/references/](../omniverse-usd-asset-validator/references/)
