# omni-asset-cli

一个面向 OpenUSD 资产校验的实用项目，基于 NVIDIA Omniverse Asset Validator，提供：

- 稳定的同步校验主路径
- 自然语言到校验参数的映射
- 机器可读 JSON 输出
- 人类可读 Markdown 报告
- 面向不同资产用途的结果解释

这个项目当前更偏向 **Agent / 自动化工具接入**，而不是单纯的人手命令集合。

## 项目目标

很多 USD 校验工具只能返回 rule 列表，但在真实交付里，大家更关心的是：

- 这个资产能不能先当静态资产使用
- 这个资产适不适合做碰撞
- 这个资产能不能继续做可移动、抓取或物理交互

`omni-asset-cli` 的目标就是把底层 validator 输出，转换成：

- 可执行的命令
- 可复用的 JSON 结果
- 可阅读的 Markdown 报告
- 面向资产用途的判断结论

## 设计理念

这个项目当前有两个执行层面：

- `人类界面`
- `Agent 界面`

这不是重复设计，而是刻意分层。

### 人类界面

面向：

- 技术美术
- 资产制作人员
- 测试人员
- 项目实施人员

特点：

- 直接运行脚本
- 明确指定资产路径
- 可以手工选择 `--profile`
- 更适合本地调试、复测和人工分析

### Agent 界面

面向：

- Codex
- ChatGPT Agent
- 自动化流程
- 工具链集成

特点：

- 从自然语言出发
- 先识别资产场景，再映射到规则集
- 输出机器可读参数和可执行命令
- 更适合自动调用、批处理和系统集成

### 为什么要分成两层

- 人类操作时，最需要的是直接、可控、可复测
- Agent 操作时，最需要的是稳定映射、可解释和结构化输出
- 两层共用同一个验证主路径 `run_sync_validation.py`
- 这样既能保证执行一致性，也能兼顾交互方式差异

## 当前能力

- 支持单个 `.usd` / `.usda` 资产校验
- 支持自然语言请求映射为确定性参数
- 支持同步 Python API 校验
- 支持异步 CLI timeout 行为观测
- 支持生成中文 Markdown 报告
- 支持按三类资产用途输出判断

当前推荐主路径：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py examples/minimal_scene.usda
```

不再推荐把原始 `omni_asset_validate` CLI 作为默认主入口。

## 为什么这个项目有用

### 同步路径更稳定

当前环境下，原始 CLI 路径存在超时和返回不稳定问题。  
项目默认使用同步 Python API 路径，避免把“CLI 没正常返回”和“资产真的有问题”混在一起。

### 不只返回 rule，还返回结论

项目不是简单打印校验项，而是把结果组织成：

- 一句话结论
- 按优先级分类的问题
- 建议的处理顺序
- 按资产用途的可用性判断

### 已区分三类资产场景

当前报告会分别评估：

- `静态资产`
- `可碰撞资产`
- `可移动资产`

这部分逻辑已经落在 `omniverse-usd-asset-validator/scripts/run_sync_validation.py` 中。

## 三类资产场景与规则策略

这个项目的一个核心观点是：

> 不同资产用途，应该关注不同的校验规则，不能所有场景都用一套 rules。

### 1. 静态资产

适用场景：

- 展示
- 场景摆放
- 背景道具
- 非交互资产

优先关注的规则：

- `StageMetadataChecker`
- `DefaultPrimChecker`
- `MissingReferenceChecker`
- `MaterialPathChecker`
- `UsdDanglingMaterialBinding`
- `UsdMaterialBindingApi`

为什么：

- 静态资产最先暴露的问题通常是结构入口、引用完整性、材质链路和基础元数据
- 这类资产即使 mesh 不是完美，也可能还能预览，但引用和材质断掉会直接影响交付质量

推荐命令示例：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  examples/boat_test/boat.usd \
  --profile static
```

### 2. 可碰撞资产

适用场景：

- 碰撞体生成
- 障碍物
- 物理接触检测
- 可进入仿真但不强调复杂运动学

优先关注的规则：

- `MissingReferenceChecker`
- `ValidateTopologyChecker`
- `ManifoldChecker`
- `ZeroAreaFaceChecker`
- `NormalsValidChecker`
- `WeldChecker`
- `ExtentsChecker`

为什么：

- 碰撞相关资产最怕拓扑脏、non-manifold、零面积面、法线异常和尺度包围盒异常
- 即使材质不完整，也不一定阻断碰撞；但 mesh 质量差会显著影响物理稳定性

推荐命令示例：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  examples/boat_test/boat.usd \
  --profile collidable
```

### 3. 可移动资产

适用场景：

- 搬运
- 抓取
- 机器人交互
- 可配置物理行为的资产

优先关注的规则：

- `KindChecker`
- `DefaultPrimChecker`
- `StageMetadataChecker`
- `MissingReferenceChecker`
- `ValidateTopologyChecker`
- `ManifoldChecker`
- `NormalsValidChecker`

为什么：

- 可移动资产不仅要“能显示”，还要结构语义合理、层级清晰、几何质量稳定
- 对 Isaac Sim / SimReady / 机器人资产来说，`KindChecker` 的重要性会明显提高

推荐命令示例：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  examples/boat_test/boat.usd \
  --profile movable
```

## 当前项目状态

目前已经完成：

- Skill 基本目录结构
- 环境检查脚本
- 自然语言参数映射脚本
- 同步校验主脚本
- 异步 CLI 包装脚本
- 中文参考文档
- 最小样例和 `boat` 样例
- 三类资产用途判断逻辑

换句话说，项目已经不再是“脚本草稿”，而是一个可以继续迭代成 GitHub 项目的原型。

## 目录结构

```text
omniverse-usd-asset-validator/
  agents/
  references/
  scripts/
examples/
AGENTS.md
README.md
```

- `omniverse-usd-asset-validator/scripts/`：主脚本
- `omniverse-usd-asset-validator/references/`：说明文档和测试记录
- `omniverse-usd-asset-validator/agents/openai.yaml`：Agent 元数据
- `examples/`：最小样例和真实测试样例

## 核心脚本

### `omniverse-usd-asset-validator/scripts/check_omniverse_asset_validator_env.py`

检查 Python 版本、包安装状态和 CLI 可用性。

### `omniverse-usd-asset-validator/scripts/run_sync_validation.py`

当前默认主脚本，负责：

- 同步执行校验
- 输出 JSON
- 输出 Markdown 报告
- 区分 `execution_status` 和 `validation_status`
- 输出三类资产用途判断

### `omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py`

把自然语言映射成校验参数，适合：

- Agent 集成
- 参数生成
- 自然语言调用验证

### `omniverse-usd-asset-validator/scripts/run_async_validation.py`

用于观察原始 CLI 行为，主要用于：

- timeout 现象复现
- 长时运行观测
- 非主路径排障

## 快速开始

### 1. 创建环境

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

### 2. 检查环境

```bash
python omniverse-usd-asset-validator/scripts/check_omniverse_asset_validator_env.py
```

### 3. 运行最小样例

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py examples/minimal_scene.usda
```

### 4. 从自然语言出发

```bash
python omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py \
  examples/minimal_scene.usda \
  "check references"
```

也支持直接从场景意图映射到 profile，例如：

```bash
python omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py \
  examples/boat_test/boat.usd \
  "帮我按可碰撞资产场景检查这个 USD"

python omniverse-usd-asset-validator/scripts/map_prompt_to_validation.py \
  examples/boat_test/boat.usd \
  "帮我看这个机器人资产适不适合做抓取和移动"
```

## 两类调用示例

### 人类执行脚本的例子

#### 例子 1：按静态资产场景检查

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  examples/boat_test/boat.usd \
  --profile static
```

适合：

- 我已经知道要检查哪个文件
- 我想直接看 JSON 和 Markdown 结果
- 我想明确控制当前场景对应的规则集

#### 例子 2：按可移动资产场景检查

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  examples/boat_test/boat.usd \
  --profile movable
```

适合：

- 我关心抓取、搬运、机器人交互
- 我希望报告里明确说明为什么启用了这些 rules

### Agent 调用的例子

#### 例子 1：让 Agent 自动识别碰撞场景

```text
用 $omniverse-usd-asset-validator 检查这个 USD，按可碰撞资产场景来判断：examples/boat_test/boat.usd
```

预期行为：

- Agent 识别出这是 `collidable` 场景
- 自动生成 `--profile collidable`
- 调用同步校验主脚本
- 输出“为什么这些 rules 适合碰撞场景”

#### 例子 2：让 Agent 自动识别可移动场景

```text
用 $omniverse-usd-asset-validator 看这个机器人资产适不适合做抓取和移动：examples/boat_test/boat.usd
```

预期行为：

- Agent 识别出这是 `movable` 场景
- 自动启用结构、入口和 mesh 稳定性相关规则
- 在结果中解释为什么 `KindChecker`、`ValidateTopologyChecker` 等规则在这个场景重要

## 示例输出

项目已经生成过多份 Markdown / JSON 报告，用于验证当前能力，例如：

- `静态资产` 视角下的可用性结论
- `可碰撞资产` 视角下的风险判断
- `可移动资产` 视角下的结构与 mesh 风险判断

这说明项目已经不仅是在“跑规则”，而是在向“交付判断工具”发展。

## 文档入口

- `omniverse-usd-asset-validator/SKILL.md`
- `omniverse-usd-asset-validator/references/project-documentation-zh.md`
- `omniverse-usd-asset-validator/references/human-operator-guide-zh.md`
- `omniverse-usd-asset-validator/references/natural-language-to-args-zh.md`

## 当前限制

- 当前规则选择仍以手工指定或自然语言映射为主
- 原始 CLI 路径更适合作为观测工具，而不是默认主执行路径

## 下一步建议

现在三类资产场景已经支持 preset：

- `static`
- `collidable`
- `movable`

可以直接这样运行：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py asset.usd --profile static
python omniverse-usd-asset-validator/scripts/run_sync_validation.py asset.usd --profile collidable
python omniverse-usd-asset-validator/scripts/run_sync_validation.py asset.usd --profile movable
```

运行后，终端摘要和 Markdown 报告都会附带：

- 当前场景
- 当前场景启用的规则
- 为什么这些规则在该场景里重要

自然语言映射脚本也会优先识别这些场景意图，并自动生成对应的 `--profile` 命令。

如果你还想补充自定义规则，也可以叠加：

```bash
python omniverse-usd-asset-validator/scripts/run_sync_validation.py \
  asset.usd \
  --profile movable \
  --rule LayerSpecChecker
```
