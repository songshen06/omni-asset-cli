# omni-asset-cli

## 中文说明

### 项目简介

`omni-asset-cli` 是一个面向 OpenUSD 资产校验的统一 CLI，基于 NVIDIA Omniverse Asset Validator。当前 Stage 1 主线对齐到静态家具、摆件和装饰道具。

它提供：

- 统一命令入口 `omni-asset-cli`
- 更稳定的同步校验主路径
- JSON 和 Markdown 输出
- 面向 `stage1-furniture` 家具/摆件检查的推荐规则
- 保留 `static`、`collidable`、`movable` 旧 profile 作为兼容入口
- 面向 AI agent 的自然语言映射入口

### 快速开始

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda --profile stage1-furniture
```

如果你暂时不想安装 console script，也可以直接运行源码入口：

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda --profile stage1-furniture
```

### 安装

仅安装当前项目：

```bash
python3 -m pip install --no-build-isolation -e .
```

安装当前项目和 validator 依赖：

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

### Isaac Sim Docker 测试环境建议

本项目推荐把普通 USD 静态检查和 Isaac Sim runtime 物理检查分开：

- 宿主机 Python 环境负责运行 `omni-asset-cli validate` 和生成报告
- Linux + Isaac Sim Docker 负责运行 `physics-hit-test` 的碰撞/物理 smoke test
- 测试资产、模板和输出目录通过仓库挂载在宿主机与容器之间共享
- 运行 Docker runtime 前，输入资产包必须在容器可读的挂载路径内；推荐放到仓库下，外部 home 目录资产会被 staging 到 `out/runtime_inputs/`

官方容器安装说明参考 NVIDIA Isaac Sim 5.1.0 文档：

```text
https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html
```

宿主机建议先确认 GPU 和 Docker 可用：

```bash
nvidia-smi
docker run hello-world
```

安装 NVIDIA Container Toolkit 后，验证 Docker 能访问 GPU：

```bash
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

获取 Isaac Sim 5.1.0 镜像：

```bash
docker pull nvcr.io/nvidia/isaac-sim:5.1.0
```

建议创建 Isaac Sim cache/config/log 目录，减少反复启动时的 shader/cache 初始化成本：

```bash
mkdir -p ~/docker/isaac-sim/cache/main/ov
mkdir -p ~/docker/isaac-sim/cache/main/warp
mkdir -p ~/docker/isaac-sim/cache/computecache
mkdir -p ~/docker/isaac-sim/config
mkdir -p ~/docker/isaac-sim/data/documents
mkdir -p ~/docker/isaac-sim/data/Kit
mkdir -p ~/docker/isaac-sim/logs
mkdir -p ~/docker/isaac-sim/pkg
sudo chown -R 1234:1234 ~/docker/isaac-sim
```

本项目的最小环境探测命令：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果输出里 `probe.ready` 是 `true`，并且 `simulation_app_available` 是 `true`，说明 Isaac Sim Python runtime 可以被 CLI 调用。

推荐的完整测试顺序：

```bash
python3 omni_asset_cli.py validate examples/minimal_scene.usda \
  --profile stage1-furniture

python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果你已经手工启动并验证过一个 Isaac Sim 容器，建议保证它挂载了当前仓库，例如挂到 `/workspace/omni-asset-cli`，然后用 `docker exec` 复用容器：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

注意事项：

- Isaac Sim 5.1.0 容器镜像来自 NVIDIA NGC：`nvcr.io/nvidia/isaac-sim:5.1.0`
- 拉取镜像可能需要先登录 NGC，取决于机器和账号权限
- 运行容器时需要传入 `ACCEPT_EULA=Y`；`PRIVACY_CONSENT=Y` 表示同意数据收集
- 如果容器内无法识别 GPU，优先检查 NVIDIA Container Toolkit，并尝试加入 `--runtime=nvidia`
- 第一次启动 Isaac Sim 通常较慢，后续启动会因为 cache 挂载而更快

### Sample 测试流程

下面是一条从干净 Linux 测试机到完成 USD 静态校验和 Isaac Sim Docker 物理 smoke test 的参考流程。

1. 进入仓库并安装 CLI：

```bash
cd /path/to/omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
```

2. 确认宿主机 Docker 和 GPU runtime：

```bash
nvidia-smi
docker run hello-world
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

3. 获取 Isaac Sim 5.1.0 镜像：

```bash
docker pull nvcr.io/nvidia/isaac-sim:5.1.0
docker images nvcr.io/nvidia/isaac-sim
```

4. 探测本项目能否调用 Isaac Sim Docker：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

期望结果：

```text
probe.ready = true
simulation_app_available = true
simulation_app_name = isaacsim.SimulationApp
```

5. 跑一个静态 USD validator 检查：

```bash
python3 omni_asset_cli.py validate examples/minimal_scene.usda \
  --profile stage1-furniture \
  --output-json out/minimal_scene_validator.json \
  --output-md out/minimal_scene_validator.md
```

6. 跑 Isaac Sim Docker 物理碰撞 smoke test：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

7. 查看输出结果：

```bash
cat out/minimal_scene_docker_hit/summary.json
cat out/minimal_scene_docker_hit/runtime_report.json
head out/minimal_scene_docker_hit/timeline.csv
```

关键字段：

```text
result
checks.asset_loaded
checks.static_colliders_applied
checks.dynamic_box_created
checks.simulation_advanced
checks.hit_targeted
checks.size_preserved
checks.contact_report_detected
checks.contact_detected_or_inferred
contact_evidence_level
```

`checks.contact_report_detected` 来自 PhysX contact report，是比 bbox 运动轨迹推断更强的证据。
`contact_evidence_level` 为 `detected` 时表示报告里有真实 contact event；为 `inferred` 时表示只满足轨迹推断条件。

8. 对真实资产重复同样流程：

```bash
ASSET=examples/boat_test/boat.usd
OUT=out/boat_docker_hit

python3 omni_asset_cli.py validate "$ASSET" \
  --profile stage1-furniture \
  --output-json out/boat_validator.json \
  --output-md out/boat_validator.md

python3 omni_asset_cli.py physics-hit-test "$ASSET" \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out "$OUT" \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Stage 1 家具和摆件使用同一个模板，但放置策略不同：

```bash
# 家具：替换模板里的桌子
python3 omni_asset_cli.py physics-hit-test path/to/chair_or_table.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/furniture_template_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0

# 摆件：保留模板桌子，把资产放到桌面中心
python3 omni_asset_cli.py physics-hit-test path/to/cup_or_decor.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode tabletop \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/prop_tabletop_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果你只想快速验证 Docker 链路是否能跑通，可以把 `--frames 240` 临时改成 `--frames 1`。短帧数只验证启动、加载和写出产物，不用于判断真实接触结果。

### 给人用的核心命令

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

旧 profile 仍然保留，便于兼容已有脚本：

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

观察底层异步 CLI 路径：

```bash
omni-asset-cli validate-async path/to/asset.usd
```

运行最小 runtime 物理碰撞链路：

```bash
omni-asset-cli physics-hit-test path/to/chair.usd --frames 240 --out ./artifacts/chair_hit
```

使用模板场景运行 runtime 物理链路：

```bash
omni-asset-cli physics-hit-test path/to/chair.usd \
  --template-scene examples/mini_test.usda \
  --replace-prim /World/roomScene/colliders/table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out ./artifacts/chair_template_hit
```

`examples/mini_test.usda` 是 Stage 1 家具/摆件模板场景：它包含桌面、静态碰撞体和动态 `/World/boxActor`。Stage 1 推荐使用 `--hit-mode top-drop --size-policy preserve`，保持目标资产真实 bbox，只把它放到模板目标位置，然后按资产 bbox 中心把 box 放到上方掉落。top-drop 会额外生成一个按资产 bbox 对齐的静态 guide collider，保证 smoke test 有确定碰撞目标。旧的 `template-fit` 模式仍可把资产缩放到原 table footprint，但不作为尺寸准确性测试的推荐路径。

先在 Linux 宿主机上用 Isaac Sim Docker 做 runtime 环境探测：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Linux 宿主机调用 Isaac Sim Docker 跑碰撞检测：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果你已经手工启动了带仓库挂载的 Isaac Sim 容器，可以复用容器：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

`physics-hit-test` 的权威 runtime 验证只支持 Linux + Isaac Sim Docker。宿主机 Python 只负责调度 Docker；容器内子进程负责加载 `SimulationApp` 并写出 `summary.json`、`runtime_report.json` 和 `timeline.csv`。

### 给 AI agent 用的命令

下面这两个入口主要是给 AI agent、自动化流程或上层编排系统使用，不是普通用户的首选手动命令。

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

### 输出

`validate` 默认会生成：

- 终端摘要
- JSON 结果
- Markdown 报告

关键字段：

- `execution_status`
- `validation_status`

这样 agent、CI 和人工复核都可以稳定消费结果。

### 资产场景

- `stage1-furniture`：Stage 1 主线，适合静态家具、摆件、装饰道具，重点检查入口、依赖、材质链路和 mesh 质量
- `static`：适合展示、背景道具、非交互资产
- `collidable`：适合碰撞检测、障碍物、基础物理接触
- `movable`：适合搬运、抓取、机器人交互

Stage 1 的 collider 推荐、尺寸参考和家具分类由 `usd-simready-inspector` 的 static furniture 流程承接；本仓库负责 validator 报告、agent/CI 入口和 runtime 模板检查。

如果没有显式传入规则、分类或 profile，CLI 会自动回退到默认规则集。

### 目录结构

```text
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
omni_asset_cli.py
pyproject.toml
setup.py
```

- `omni_asset_cli.py`：统一 CLI 入口
- `omniverse-usd-asset-validator/scripts/`：底层脚本实现
- `omniverse-usd-asset-validator/agents/openai.yaml`：agent 元数据
- `omniverse-usd-asset-validator/references/`：详细说明文档
- `examples/`：示例 USD 资产

### 适用对象

这个仓库主要面向：

- AI agent / 自动化流程
- CI / 批处理校验
- 本地调试和人工复核

进一步文档：

- `omniverse-usd-asset-validator/SKILL.md`
- `omniverse-usd-asset-validator/references/`
- `omniverse-usd-asset-validator/references/agent-bootstrap-deployment.md`
- `omniverse-usd-asset-validator/references/test-environment-deployment.md`

## English

### Overview

`omni-asset-cli` is a unified CLI for OpenUSD asset validation, built on NVIDIA Omniverse Asset Validator. The current Stage 1 path is aligned around static furniture, furnishings, and decorative props.

It provides:

- A unified `omni-asset-cli` entry point
- A more stable synchronous validation path
- JSON and Markdown outputs
- A recommended `stage1-furniture` rule group for furniture and prop validation
- Backward-compatible `static`, `collidable`, and `movable` profiles
- Natural-language entry points for AI agents

### Quick Start

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda --profile stage1-furniture
```

If you do not want to install the console script yet, you can run the source entry point directly:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda --profile stage1-furniture
```

### Installation

Install this project only:

```bash
python3 -m pip install --no-build-isolation -e .
```

Install this project together with validator dependencies:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

### Core Commands for Human Operators

Check the runtime:

```bash
omni-asset-cli env
```

Validate a single USD asset:

```bash
omni-asset-cli validate path/to/asset.usd
```

Apply the Stage 1 furniture/prop profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
```

Legacy profiles remain available for compatibility:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

Observe the underlying asynchronous CLI path:

```bash
omni-asset-cli validate-async path/to/asset.usd
```

Run the minimal runtime physics harness:

```bash
omni-asset-cli physics-hit-test path/to/chair.usd --frames 240 --out ./artifacts/chair_hit
```

Run the runtime physics harness with an authored template scene:

```bash
omni-asset-cli physics-hit-test path/to/chair.usd \
  --template-scene examples/mini_test.usda \
  --replace-prim /World/roomScene/colliders/table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out ./artifacts/chair_template_hit
```

`examples/mini_test.usda` is the Stage 1 furniture/prop template scene. It contains a table, static colliders, and the dynamic `/World/boxActor`. The recommended Stage 1 runtime path is `--hit-mode top-drop --size-policy preserve`: keep the target asset's real bbox, place it at the template target location, then place the dynamic box above the asset bbox center so gravity drives a deterministic drop. Top-drop also authors a static guide collider aligned to the asset bbox so the smoke test has a deterministic collision target. The legacy `template-fit` path can still scale the asset to the original table footprint, but it is not the recommended size-accuracy test.

Check the Linux + Isaac Sim Docker runtime environment first:

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Authoritative `physics-hit-test` runtime validation only supports Linux + Isaac Sim Docker. Host Python only dispatches Docker; the container child process loads `SimulationApp` and writes `summary.json`, `runtime_report.json`, and `timeline.csv`.

### Commands for AI Agents

The following two commands are primarily intended for AI agents, automation pipelines, or orchestration layers. They are not the preferred manual entry points for normal human usage.

Map natural language into deterministic arguments:

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "validate this as static furniture and decor props"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

Map and execute in one step:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as static furniture and decor props"
omni-asset-cli validate-from-prompt path/to/asset.usd "check references and materials for this furnishing"
```

### Outputs

`validate` produces:

- Terminal summary
- JSON result
- Markdown report

Key fields:

- `execution_status`
- `validation_status`

This makes the output stable for agents, CI, and human review.

### Asset Profiles

- `stage1-furniture`: the recommended Stage 1 path for static furniture, furnishings, and decorative props; focuses on entry points, dependencies, materials, and mesh quality
- `static`: suitable for display assets, background props, and non-interactive assets
- `collidable`: suitable for collision checks, obstacles, and basic physical contact
- `movable`: suitable for moving, grasping, and robot interaction

Furniture classification, size references, and static collider recommendations remain owned by the `usd-simready-inspector` static furniture workflow. This repository provides the validator report, agent/CI entry point, and runtime template check.

If no explicit rule, category, or profile is provided, the CLI falls back to the default rule set.

### Repository Layout

```text
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
omni_asset_cli.py
pyproject.toml
setup.py
```

- `omni_asset_cli.py`: unified CLI entry point
- `omniverse-usd-asset-validator/scripts/`: underlying script implementations
- `omniverse-usd-asset-validator/agents/openai.yaml`: agent metadata
- `omniverse-usd-asset-validator/references/`: detailed references
- `examples/`: sample USD assets

### Intended Users

This repository is mainly for:

- AI agents and automation
- CI and batch validation
- Local debugging and human review

Further documentation:

- `omniverse-usd-asset-validator/SKILL.md`
- `omniverse-usd-asset-validator/references/`
- `omniverse-usd-asset-validator/references/agent-bootstrap-deployment.md`
- `omniverse-usd-asset-validator/references/test-environment-deployment.md`
