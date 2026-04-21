# omni-asset-cli

## 中文说明

### 项目简介

`omni-asset-cli` 是一个面向 OpenUSD 资产校验的统一 CLI，基于 NVIDIA Omniverse Asset Validator。

它提供：

- 统一命令入口 `omni-asset-cli`
- 更稳定的同步校验主路径
- JSON 和 Markdown 输出
- 面向 `static`、`collidable`、`movable` 三类资产场景的预设规则
- 面向 AI agent 的自然语言映射入口

### 快速开始

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

如果你暂时不想安装 console script，也可以直接运行源码入口：

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
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

按资产场景应用预设规则：

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

观察底层异步 CLI 路径：

```bash
omni-asset-cli validate-async path/to/asset.usd
```

### 给 AI agent 用的命令

下面这两个入口主要是给 AI agent、自动化流程或上层编排系统使用，不是普通用户的首选手动命令。

把自然语言映射成确定性参数：

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

从自然语言直接执行校验：

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "帮我按可碰撞资产场景检查"
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as a collidable asset"
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

- `static`：适合展示、背景道具、非交互资产
- `collidable`：适合碰撞检测、障碍物、基础物理接触
- `movable`：适合搬运、抓取、机器人交互

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

`omni-asset-cli` is a unified CLI for OpenUSD asset validation, built on NVIDIA Omniverse Asset Validator.

It provides:

- A unified `omni-asset-cli` entry point
- A more stable synchronous validation path
- JSON and Markdown outputs
- Preset rule groups for `static`, `collidable`, and `movable`
- Natural-language entry points for AI agents

### Quick Start

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

If you do not want to install the console script yet, you can run the source entry point directly:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
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

Apply a preset asset profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

Observe the underlying asynchronous CLI path:

```bash
omni-asset-cli validate-async path/to/asset.usd
```

### Commands for AI Agents

The following two commands are primarily intended for AI agents, automation pipelines, or orchestration layers. They are not the preferred manual entry points for normal human usage.

Map natural language into deterministic arguments:

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

Map and execute in one step:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "帮我按可碰撞资产场景检查"
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as a collidable asset"
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

- `static`: suitable for display assets, background props, and non-interactive assets
- `collidable`: suitable for collision checks, obstacles, and basic physical contact
- `movable`: suitable for moving, grasping, and robot interaction

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
