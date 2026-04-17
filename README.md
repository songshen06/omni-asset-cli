# omni-asset-cli

面向 OpenUSD 资产校验的统一 CLI，基于 NVIDIA Omniverse Asset Validator。

它提供：

- 统一命令入口 `omni-asset-cli`
- 同步校验主路径
- 自然语言到校验参数的映射
- JSON 和 Markdown 输出
- 面向 `static`、`collidable`、`movable` 三类资产场景的预设规则

## Quick Start

```bash
git clone git@github.com:songshen06/omni-asset-cli.git
cd omni-asset-cli
python3 -m pip install --no-build-isolation -e ".[validator]"
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
```

如果你暂时不想安装 console script，也可以直接运行：

```bash
python3 omni_asset_cli.py env
python3 omni_asset_cli.py validate examples/minimal_scene.usda
```

## 安装

安装当前项目：

```bash
python3 -m pip install --no-build-isolation -e .
```

安装项目和 validator 依赖：

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

## 核心命令

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

把自然语言映射成确定性参数：

```bash
omni-asset-cli map path/to/asset.usd "检查引用和贴图"
```

从自然语言直接执行校验：

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "帮我按可碰撞资产场景检查"
```

运行异步 CLI 观测路径：

```bash
omni-asset-cli validate-async path/to/asset.usd
```

## 输出

`validate` 默认会生成：

- 终端摘要
- JSON 结果
- Markdown 报告

输出中会区分：

- `execution_status`
- `validation_status`

这样 agent、CI 和人工查看都能稳定消费结果。

## 资产场景

支持三类预设 profile：

- `static`
  适合展示、背景道具、非交互资产
- `collidable`
  适合碰撞检测、障碍物、基础物理接触
- `movable`
  适合搬运、抓取、机器人交互

如果不显式传入规则、分类或 profile，CLI 会自动回退到默认规则集。

## 目录结构

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

- `omni_asset_cli.py`: 统一 CLI 入口
- `omniverse-usd-asset-validator/scripts/`: 底层脚本实现
- `omniverse-usd-asset-validator/agents/openai.yaml`: agent 元数据
- `omniverse-usd-asset-validator/references/`: 详细说明文档
- `examples/`: 示例 USD 资产

## 适合谁

这个仓库主要面向：

- Agent / 自动化流程
- CI / 批处理校验
- 本地调试和人工复核

首页 README 只保留当前版本的使用方式。更细的背景、规则说明和操作指南请看：

- `omniverse-usd-asset-validator/SKILL.md`
- `omniverse-usd-asset-validator/references/`
