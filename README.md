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

先做 runtime 环境探测：

```bash
python3 omni_asset_cli.py physics-env --runtime-python C:\\isaacsim\\python.bat --runtime-platform windows
```

使用 Isaac Sim Docker 做 runtime 环境探测：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果当前解释器不是 Isaac Sim Python，也可以显式指定 runtime：

Linux:

```bash
omni-asset-cli physics-hit-test path/to/chair.usd \
  --runtime-python ~/.local/share/ov/pkg/isaac-sim-*/python.sh \
  --runtime-platform linux
```

WSL 调 Windows Isaac Sim:

```bash
python3 omni_asset_cli.py physics-hit-test /mnt/c/path/to/chair.usd \
  --out /mnt/c/path/to/artifacts/chair_hit \
  --runtime-python C:\\isaacsim\\python.bat \
  --runtime-platform windows
```

Linux 宿主机调用 Isaac Sim Docker 跑碰撞检测：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

如果你已经手工启动了带仓库挂载的 Isaac Sim 容器，可以复用容器：

```bash
python3 omni_asset_cli.py physics-hit-test examples/minimal_scene.usda \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/minimal_scene_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

`physics-hit-test` 会优先在当前解释器中直接运行；如果当前解释器没有 `SimulationApp`，则会尝试切换到外部 Isaac Sim Python。默认输出目录改为仓库内 `out/`，便于 Linux / Windows 共享访问。

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

Check the runtime environment first:

```bash
python3 omni_asset_cli.py physics-env --runtime-python C:\\isaacsim\\python.bat --runtime-platform windows
```

If the current interpreter is not Isaac Sim Python, you can point the command at an external runtime:

Linux:

```bash
omni-asset-cli physics-hit-test path/to/chair.usd \
  --runtime-python ~/.local/share/ov/pkg/isaac-sim-*/python.sh \
  --runtime-platform linux
```

WSL to Windows Isaac Sim:

```bash
python3 omni_asset_cli.py physics-hit-test /mnt/c/path/to/chair.usd \
  --out /mnt/c/path/to/artifacts/chair_hit \
  --runtime-python C:\\isaacsim\\python.bat \
  --runtime-platform windows
```

`physics-hit-test` first tries to run in the current interpreter. If `SimulationApp` is unavailable, it can dispatch to an external Isaac Sim Python. The default output directory is now `out/` inside the repo so the artifacts stay accessible from both Linux and Windows.

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
