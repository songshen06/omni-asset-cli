# Omniverse USD Asset Validator 人类使用手册

## 1. 文档目的

本文档面向实施人员、维护人员、测试人员和项目成员，说明当前 `omniverse-usd-asset-validator` skill 的用途、推荐调用方式、输出结果含义以及常见工作流。

这份文档是给人看的统一入口，不替代 `SKILL.md`。

其中：

- `SKILL.md` 主要面向 Agent
- 本文档主要面向人类操作者

## 2. 这个 skill 是做什么的

这个 skill 用于对 USD 资产执行 NVIDIA Omniverse Asset Validator 校验，并同时输出：

- 结构化 JSON 结果，供程序或 Agent 读取
- Markdown 报告，供人类阅读

它支持：

- 直接对单个 USD 资产做同步校验
- 把自然语言请求映射为验证参数
- 输出人类可读的规则解释
- 在 Isaac Sim / SimReady 场景下对资产结构问题做更明确的说明

## 3. 当前推荐的执行方式

当前项目默认不再把原始 `omni_asset_validate` CLI 作为主执行入口。

推荐主路径是：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json
```

原因是：

- 原始 CLI 在当前环境中存在异步超时问题
- 同步 Python API 已验证更稳定
- 可以稳定输出 JSON 和 Markdown

## 4. 三个主要脚本分别做什么

### 4.1 `run_sync_validation.py`

这是当前主执行脚本。

作用：

- 直接调用同步 Python API 执行校验
- 输出 JSON
- 输出终端摘要
- 输出 Markdown 人类解读报告

这是默认推荐脚本。

### 4.2 `map_prompt_to_validation.py`

这是自然语言参数生成脚本。

作用：

- 把自然语言请求映射成 `run_sync_validation.py` 参数
- 输出映射结果
- 可选地直接执行映射后的验证命令

适合：

- 从自然语言触发验证
- 做 Agent 集成
- 测试“某句话会映射成什么规则”

### 4.3 `run_async_validation.py`

这是原始 CLI 的异步包装脚本。

作用：

- 启动 `omni_asset_validate`
- 观察 CLI 的运行状态
- 在 timeout 场景下输出运行摘要

定位：

- 主要用于观察 CLI 行为或复现 timeout
- 不建议作为正式主执行路径

## 5. 推荐工作流

### 5.1 人工直接校验

如果你已经知道要检查哪个资产，直接运行：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json
```

它会生成：

- `/tmp/asset_validation.json`
- `/tmp/asset_validation.md`

### 5.2 从自然语言出发

如果你只有一句自然语言需求，例如：

```text
帮我检查这个 Isaac Sim 资产结构和组件层级是否合理
```

先运行：

```bash
python scripts/map_prompt_to_validation.py /path/to/asset.usd "帮我检查这个 Isaac Sim 资产结构和组件层级是否合理"
```

如果确认映射正确，再加：

```bash
--execute
```

### 5.3 观察原始 CLI 是否超时

如果你是在排查 CLI 问题，而不是做正式校验，可以运行：

```bash
python scripts/run_async_validation.py /path/to/asset.usd --output-json /tmp/asset_validation_async.json --timeout-seconds 300
```

## 6. 输出结果怎么读

### 6.1 JSON 给谁看

JSON 主要给：

- Agent
- 自动化流程
- CI
- 后处理程序

JSON 是机器可读结果。

### 6.2 Markdown 给谁看

Markdown 主要给：

- 人工评审
- 项目负责人
- 资产制作人员
- 质量检查人员

Markdown 是人类可读报告。

### 6.3 两个关键状态字段

JSON 中有两个应该优先读取的字段：

- `execution_status`
- `validation_status`

#### `execution_status`

表示脚本本身是否成功执行。

可能值：

- `completed`
- `error`

#### `validation_status`

表示资产校验结果。

可能值：

- `passed`
- `warning`
- `failed`
- `blocked`

### 6.4 这两个字段的区别

最重要的一点是：

> 资产校验失败，并不等于脚本执行失败。

例如：

- `execution_status = completed`
- `validation_status = failed`

这表示：

- 脚本正常执行完成
- 但资产本身没有通过校验

## 7. 常见使用示例

### 7.1 默认校验

```bash
python scripts/run_sync_validation.py /workspace/body.usd --output-json /workspace/body_validation.json
```

### 7.2 只检查 Isaac Sim 结构

```bash
python scripts/run_sync_validation.py /workspace/body.usd --rule KindChecker --output-json /workspace/body_kind.json
```

### 7.3 只检查丢失引用

```bash
python scripts/run_sync_validation.py /workspace/body.usd --rule MissingReferenceChecker --output-json /workspace/body_refs.json
```

### 7.4 只看 geometry

```bash
python scripts/run_sync_validation.py /workspace/body.usd --category Geometry --output-json /workspace/body_geometry.json
```

### 7.5 用自然语言直接驱动

```bash
python scripts/map_prompt_to_validation.py /workspace/body.usd "帮我检查这个 Isaac Sim 资产结构和组件层级是否合理" --output-json /workspace/body_kind.json --execute
```

## 8. Isaac Sim / SimReady 相关说明

对于 Isaac Sim、SimReady 或机器人资产，`KindChecker` 非常重要，但不应强制加入所有校验请求。

建议仅在用户明确提到以下语义时，再加入 `KindChecker`：

- asset structure
- simulation structure
- hierarchy
- component semantics
- Isaac Sim structure
- SimReady structure
- 资产结构
- 层级结构
- 组件语义
- 仿真层级

原因是：

- `KindChecker` 主要检查结构语义
- 它不是每次校验都必须启用的规则
- 但在 Isaac Sim / SimReady 场景下，它是非常重要的结构信号

## 9. 常见问题

### 9.1 为什么不用原始 `omni_asset_validate` CLI 做主入口

因为当前环境中，CLI 异步路径存在 timeout 问题。

### 9.2 为什么终端说 failed，但脚本没有报错

因为现在区分了：

- 程序执行状态
- 资产校验状态

资产失败不等于脚本执行失败。

### 9.3 为什么既有 JSON 又有 Markdown

因为这两种输出面向不同对象：

- JSON 给机器
- Markdown 给人

## 10. 当前已知限制

1. 原始 `omni_asset_validate` CLI 在当前环境中存在异步 timeout 问题
2. 自然语言参数映射目前基于规则匹配，不是完整语义理解引擎
3. Markdown 报告已经支持规则解释，但仍可继续增强更复杂的分组和修复建议

## 11. 推荐阅读顺序

如果你是第一次接触这个 skill，建议按这个顺序阅读：

1. 本文档
2. `project-documentation-zh.md`
3. `natural-language-examples-zh.md`
4. `natural-language-to-args-zh.md`
5. `kind-checker-explained-zh.md`

这样可以先建立全局认识，再深入到具体规则和调用方式。
