# Deployment Guide

这份文档是 `omni-asset-cli` 的独立部署入口，覆盖本地 CLI、Isaac Sim Docker runtime、runtime 输入路径约束，以及可选 REST API 服务部署。

本项目的权威 runtime 物理验证只支持 **Linux + Isaac Sim Docker**。宿主机 Python 负责调度 CLI 和 Docker；Isaac Sim `SimulationApp` 在容器内运行，并写出 `summary.json`、`runtime_report.json`、`timeline.csv` 等产物。

## 1. Host prerequisites

部署机器需要满足：

- Linux host with NVIDIA GPU access
- Docker daemon available to the deployment user
- NVIDIA Container Toolkit configured for `docker run --gpus all`
- Access to pull or run `nvcr.io/nvidia/isaac-sim:5.1.0`
- Python 3.10 or compatible Python 3
- Git access to this repository

先验证宿主机 GPU 和 Docker：

```bash
nvidia-smi
docker run hello-world
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

如果 `docker run --gpus all` 失败，先修复 Docker/NVIDIA Container Toolkit。不要用宿主机 Python、Windows Isaac Sim、WSL bridge 或非 Docker runtime 替代权威 runtime 验证。

Isaac Sim 镜像来自 NVIDIA NGC。拉取镜像可能需要先登录：

```bash
docker login nvcr.io
docker pull nvcr.io/nvidia/isaac-sim:5.1.0
```

## 2. Repository layout

推荐部署目录：

```text
~/omni-asset-cli
~/docker/isaac-sim
```

如果同时部署 `usd-simready-inspector`，推荐放在：

```text
~/usd-simready-inspector
```

`omni-asset-cli` 是调度、validator 报告、runtime hit test 和 API 服务入口。`usd-simready-inspector` 如果存在，通常负责 SimReady 推荐、静态 collider authoring、尺度/方向修复和导出。

## 3. Install the CLI environment

从仓库根目录创建 validator 环境：

```bash
cd ~/omni-asset-cli
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[validator]"
```

验证 Python、OpenUSD 和 Omniverse Asset Validator：

```bash
.venv/bin/python -c "from pxr import Usd; import omni.asset_validator; print('pxr ok'); print('validator ok')"
.venv/bin/python omni_asset_cli.py env
```

如果需要使用 console script，激活 venv：

```bash
source .venv/bin/activate
omni-asset-cli env
```

## 4. Deploy Isaac Sim Docker

推荐使用仓库脚本准备 cache 目录、启动长驻容器并运行 probe：

```bash
cd ~/omni-asset-cli
scripts/deploy_isaacsim_docker.sh --check
scripts/deploy_isaacsim_docker.sh --start --probe-container
```

新机器上如果还没有镜像和容器，使用：

```bash
scripts/deploy_isaacsim_docker.sh --all
```

脚本默认值：

```text
image: nvcr.io/nvidia/isaac-sim:5.1.0
container: isaac-sim
workspace: /workspace/omni-asset-cli
docker python: /isaac-sim/python.sh
cache root: ~/docker/isaac-sim
```

脚本不会安装 Docker 或 NVIDIA Container Toolkit。如果 `--check` 失败，需要先修复宿主机依赖。

也可以直接用 CLI probe 镜像：

```bash
.venv/bin/python omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

或者复用已启动的容器：

```bash
.venv/bin/python omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

期望结果包含：

```text
probe.ready = true
simulation_app_available = true
simulation_app_name = isaacsim.SimulationApp
```

## 5. Runtime input staging

Docker probe 通过只说明 Isaac Sim runtime 可启动，不代表容器能读取任意宿主机路径。

Runtime 输入要求：

- 优先把资产放在 `~/omni-asset-cli` 仓库下。
- 对 repo 外、但位于 host home 目录下的资产包，运行前应把整个包目录 staging 到 `out/runtime_inputs/<asset_package>/`。
- staging 必须保留 USD、textures、MDL、GLB sidecars、payloads 和相对引用关系。
- runtime harness 对 home 目录输入有自动 staging，但部署和报告中仍应记录实际 staged path，方便复现。

示例：

```bash
cd ~/omni-asset-cli
mkdir -p out/runtime_inputs
cp -a ~/new_3D out/runtime_inputs/new_3D
```

之后使用 staged path 运行 runtime：

```bash
.venv/bin/python omni_asset_cli.py physics-hit-test out/runtime_inputs/new_3D/cup.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/cup_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

## 6. Smoke tests

先跑静态 validator：

```bash
.venv/bin/python omni_asset_cli.py validate examples/minimal_scene.usda \
  --profile stage1-furniture
```

再跑最小 Docker runtime top-drop hit test：

```bash
.venv/bin/python omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

如果不使用长驻容器，也可以改用镜像调度：

```bash
.venv/bin/python omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

检查产物：

```bash
cat out/minimal_scene_docker_hit/summary.json
cat out/minimal_scene_docker_hit/runtime_report.json
head out/minimal_scene_docker_hit/timeline.csv
```

强通过证据优先看：

```text
summary.result = passed
checks.contact_report_detected = true
contact_evidence_level = detected
```

`contact_evidence_level = inferred` 只表示基于运动轨迹的弱推断，不能等同于 PhysX contact report。

## 7. Rendered physics bbox evidence

如果需要带 physics bbox 的渲染证据，仍然使用 runtime harness，不要改写源 USD 添加 debug prim：

```bash
.venv/bin/python omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --render-frames \
  --render-physics-bboxes \
  --out out/minimal_scene_docker_hit_rendered \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

`--render-physics-bbox-fallback-default-prim` 只用于调试没有 collider paths 的捕获问题，不应把 fallback bbox 当成真实 physics collider evidence 报告。

## 8. Optional API service deployment

REST API 服务用于把 mesh validator 检查和 `physics-hit-test` 碰撞检查作为异步任务提交。API 只管理 tenant、project、asset、job 和 artifacts；实际检查仍调用同一套 CLI。

安装 API 环境并写出 env 文件：

```bash
cd ~/omni-asset-cli
scripts/deploy_api_service.sh --write-env
```

默认会创建：

```text
.venv-api
.env.omni-asset-service
```

本地启动：

```bash
source .env.omni-asset-service
.venv-api/bin/omni-asset-service --host 0.0.0.0 --port 8000
```

关键环境变量：

```text
OMNI_SERVICE_STORAGE_ROOT=out/omni-asset-service
OMNI_SERVICE_API_KEYS=api-key:tenant_id:project_id
ISAAC_CONTAINERS=isaac-sim
DOCKER_WORKSPACE=/workspace/omni-asset-cli
DOCKER_PYTHON=/isaac-sim/python.sh
OMNI_SERVICE_JOB_TIMEOUT_SECONDS=7200
OMNI_SERVICE_START_WORKER=1
```

核心测试接口：

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

`/tests/mesh` 使用宿主机 validator 环境，不需要 Isaac Sim container。warning 和非碰撞相关 validator failure 会保留在报告中，但不阻断后续碰撞测试；只有会影响物理碰撞的严重 mesh、引用、尺度或拓扑问题才判定 failed。`/tests/collision` 使用 Isaac Sim Docker container，并要求 `ISAAC_CONTAINERS` 指向可用容器。

systemd 示例文件：

```text
deploy/omni-asset-service.env.example
deploy/omni-asset-service.service
```

典型 systemd 部署路径是：

```text
/opt/omni-asset-cli
/etc/omni-asset-service.env
/etc/systemd/system/omni-asset-service.service
```

部署前确认 systemd service 中的 `WorkingDirectory`、`EnvironmentFile` 和 `.venv-api` 路径与实际安装位置一致。

## 9. Troubleshooting

常见故障优先级：

- `docker run --gpus all ... nvidia-smi` 失败：修复 NVIDIA Container Toolkit 和 Docker GPU runtime。
- `docker pull nvcr.io/nvidia/isaac-sim:5.1.0` 失败：确认 NGC 网络、账号权限和 `docker login nvcr.io`。
- `physics-env` 中 `simulation_app_available = false`：确认镜像版本、`/isaac-sim/python.sh` 路径和容器启动状态。
- 容器内找不到输入 USD 或贴图：把整个资产包 staging 到 `out/runtime_inputs/`，不要只复制单个 USD。
- `summary.json` 没有强 contact evidence：先检查 `runtime_report.json`、`timeline.csv`、asset bbox、placement、collider authoring 和模板位置。
- API job 报 `No Isaac Sim Docker container`：确认 `ISAAC_CONTAINERS` 配置了可用容器名，并且服务进程用户有 Docker 权限。

Runtime 检查失败时，把它作为 data-flywheel feedback 处理。保留：

```text
summary.json
runtime_report.json
timeline.csv
generated stage path
asset path or staged asset path
Docker image or container name
full command line
failure class: environment, authoring, collider/contact, placement, scale, motion, or runtime quality
```

修复上游资产准备或 repair policy 后，用同一条 Docker 命令复跑并比较结构化产物。

## 10. Related documents

- `README.md`
- `AGENTS.md`
- `omniverse-usd-asset-validator/references/agent-bootstrap-deployment.md`
- `omniverse-usd-asset-validator/references/test-environment-deployment.md`
- `scripts/deploy_isaacsim_docker.sh`
- `scripts/deploy_api_service.sh`
