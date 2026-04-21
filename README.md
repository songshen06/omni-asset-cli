# omni-asset-cli

统一的 OpenUSD 资产校验 CLI，基于 NVIDIA Omniverse Asset Validator。  
Unified CLI for OpenUSD asset validation, built on NVIDIA Omniverse Asset Validator.

## 概述 / Overview

这个项目提供：

- 统一命令入口 `omni-asset-cli`
- 同步校验主路径
- 自然语言到参数的确定性映射
- JSON 和 Markdown 输出
- 面向 `static`、`collidable`、`movable` 的预设规则

This project provides:

- A unified `omni-asset-cli` entry point
- A synchronous validation path
- Deterministic natural-language-to-argument mapping
- JSON and Markdown outputs
- Preset rule groups for `static`, `collidable`, and `movable`

## 快速开始 / Quick Start

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

如果你暂时不想安装 console script，也可以直接运行：
If you do not want to install the console script yet, you can run the source entry point directly:

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
```

## 安装 / Installation

仅安装当前项目：
Install this project only:

```bash
python3 -m pip install --no-build-isolation -e .
```

安装当前项目和 validator 依赖：
Install this project together with validator dependencies:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

## 核心命令 / Core Commands

检查环境：
Check the runtime:

```bash
omni-asset-cli env
```

校验单个 USD 资产：
Validate a single USD asset:

```bash
omni-asset-cli validate path/to/asset.usd
```

按资产场景应用预设规则：
Apply a preset profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

把自然语言映射成参数：
Map natural language into deterministic arguments:

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
omni-asset-cli map path/to/asset.usd "check references and textures"
```

从自然语言直接执行校验：
Map and execute in one step:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "帮我按可碰撞资产场景检查"
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as a collidable asset"
```

观察异步 CLI 路径：
Observe the asynchronous CLI path:

```bash
omni-asset-cli validate-async path/to/asset.usd
```

## 输出 / Outputs

`validate` 默认会生成：
`validate` generates:

- 终端摘要 / terminal summary
- JSON 结果 / JSON result
- Markdown 报告 / Markdown report

关键字段：
Key fields:

- `execution_status`
- `validation_status`

这让 agent、CI 和人工查看都能稳定消费结果。  
This makes the output stable for agents, CI, and human review.

## 资产场景 / Asset Profiles

- `static`
  适合展示、背景道具、非交互资产。  
  Suitable for display assets, background props, and non-interactive assets.
- `collidable`
  适合碰撞检测、障碍物、基础物理接触。  
  Suitable for collision checks, obstacles, and basic physical contact.
- `movable`
  适合搬运、抓取、机器人交互。  
  Suitable for moving, grasping, and robot interaction.

如果未显式传入规则、分类或 profile，CLI 会自动回退到默认规则集。  
If no explicit rule, category, or profile is provided, the CLI falls back to the default rule set.

## 目录结构 / Repository Layout

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

- `omni_asset_cli.py`: 统一 CLI 入口 / unified CLI entry point
- `omniverse-usd-asset-validator/scripts/`: 底层脚本实现 / underlying script implementations
- `omniverse-usd-asset-validator/agents/openai.yaml`: agent 元数据 / agent metadata
- `omniverse-usd-asset-validator/references/`: 详细说明 / detailed references
- `examples/`: 示例 USD 资产 / sample USD assets

## 适用对象 / Intended Users

这个仓库主要面向：
This repository is mainly for:

- Agent / 自动化流程 / agents and automation
- CI / 批处理校验 / CI and batch validation
- 本地调试和人工复核 / local debugging and human review

更细的说明请看：
For more detail, see:

- `omniverse-usd-asset-validator/SKILL.md`
- `omniverse-usd-asset-validator/references/`

