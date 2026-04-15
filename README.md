# Omni Asset CLI

一个面向 GitHub 发布的 OpenUSD 资产校验项目，核心能力基于 NVIDIA Omniverse Asset Validator，为 Agent 和人工操作者提供：

- 单个 USD 资产的同步校验
- 自然语言到校验参数的映射
- 机器可读 JSON 输出
- 人类可读 Markdown 报告
- 面向 SimReady / Isaac Sim 场景的结果解释

## 当前进展

项目当前已经完成以下核心能力：

- 已建立可用的 skill 目录结构
- 已完成环境检查脚本
- 已完成自然语言到校验参数的映射脚本
- 已完成同步 Python API 校验主路径
- 已完成异步 CLI 观测脚本
- 已沉淀最小样例与真实资产测试结果

当前推荐的正式执行路径是：

- 默认使用 `omniverse-usd-asset-validator/scripts/run_sync_validation.py`
- 不再把原始 `omni_asset_validate` CLI 作为主执行入口

## 项目亮点

### 1. 同步主路径更稳定

项目优先通过 Python API 执行校验，避免当前环境下原始 CLI 异步路径可能出现的超时问题。

### 2. 支持自然语言驱动

可以把“检查引用”“检查材质”“检查 Isaac Sim 结构”这类自然语言请求，映射成确定性的校验参数。

### 3. 已完成三大使用场景区分

Markdown 报告会按资产用途给出判断：

- `静态资产`
- `可碰撞资产`
- `可移动资产`

这部分逻辑已经体现在 `omniverse-usd-asset-validator/scripts/run_sync_validation.py` 中，并已用于现有报告产物。

## 目录结构

```text
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
out/
AGENTS.md
```

- `omniverse-usd-asset-validator/scripts/`：主脚本目录
- `omniverse-usd-asset-validator/references/`：中文说明、环境说明与测试记录
- `omniverse-usd-asset-validator/agents/openai.yaml`：Agent 入口元数据
- `examples/`：最小样例和 `boat_test` 测试资产
- `out/`：历史 JSON / Markdown 校验输出

## 主要脚本

### `omniverse-usd-asset-validator/scripts/check_omniverse_asset_validator_env.py`

检查 Python、包和 CLI 环境是否可用。

### `omniverse-usd-asset-validator/scripts/run_sync_validation.py`

当前默认主路径：

- 同步执行校验
- 输出 JSON
- 输出 Markdown 报告
- 区分 `execution_status` 与 `validation_status`
- 输出三大使用场景判断

### `omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py`

把自然语言映射成 `run_sync_validation.py` 参数，并可选择直接执行。

### `omniverse-usd-asset-validator/scripts/run_async_validation.py`

用于观察原始 CLI 行为和 timeout 情况，不建议作为主执行路径。

## 快速开始

建议使用独立虚拟环境：

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

检查环境：

```bash
python omniverse-usd-asset-validator/scripts/check_omniverse_asset_validator_env.py
```

运行最小样例：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py examples/minimal_scene.usda
```

自然语言映射示例：

```bash
python omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py examples/minimal_scene.usda "check references"
```

## 示例产物

仓库中已经保留了一些历史校验结果，可用于展示当前阶段能力：

- `out/chair_validation_new.md`
- `out/bag_validation_new.md`
- `out/bottle_validation.md`

这些结果显示项目已经不仅能输出 rule 级问题，还能把结果转换成面向资产用途的可读结论。

## 文档入口

推荐优先阅读以下文件：

- `omniverse-usd-asset-validator/references/project-documentation-zh.md`
- `omniverse-usd-asset-validator/references/human-operator-guide-zh.md`
- `omniverse-usd-asset-validator/SKILL.md`

## 上传到 GitHub 前的建议

建议保留：

- `omniverse-usd-asset-validator/`
- `examples/`
- `README.md`
- `AGENTS.md`

建议忽略：

- `.venv/`
- `__pycache__/`
- `out/`

如果你希望把历史报告作为展示样例，也可以先保留 `out/`，后续再决定是否移出到 `examples/outputs/`。
