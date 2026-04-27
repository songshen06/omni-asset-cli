# 人类使用手册

## 中文说明

### 目的

这份文档面向人工操作人员，说明当前版本的推荐入口、输出和常见用法。

### 推荐入口

- `omni-asset-cli env`
- `omni-asset-cli validate`
- `omni-asset-cli map`
- `omni-asset-cli validate-from-prompt`
- `omni-asset-cli validate-async`
- `omni-asset-cli physics-hit-test`

如果没有安装 console script，则回退到 `python3 omni_asset_cli.py ...`。

### 推荐工作流

1. 先运行 `env`
2. 单资产默认运行 `validate <asset> --profile stage1-furniture`
3. 如果需求来自自然语言，用 `map` 或 `validate-from-prompt`，例如“按家具和摆件 Stage 1 检查”
4. 只有排查 CLI timeout 时才使用 `validate-async`
5. 需要 runtime 物理链路时，先运行 `physics-env`，再运行 `physics-hit-test`

### Stage 1 家具/摆件校验

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
omni-asset-cli validate-from-prompt path/to/asset.usd "按家具和摆件 Stage 1 检查"
```

这个 profile 面向静态家具、摆件和装饰道具，重点检查入口定义、引用、材质链路和 mesh 质量。家具分类、尺寸参考和静态 collider 推荐由 `usd-simready-inspector` 的 static furniture 流程承接。

### Runtime 物理模板场景

```bash
omni-asset-cli physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --replace-prim /World/roomScene/colliders/table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/asset_template_hit
```

Stage 1 推荐使用顶部掉落模式：目标家具/摆件保持真实 bbox，不按 table footprint 缩放；测试会把 box 放到资产 bbox 中心上方并向下掉落，同时生成按资产 bbox 对齐的静态 guide collider。当前 v1 通过标准是 runtime 链路可运行、box 瞄准资产 bbox、尺寸未被缩放、并通过 contact 或 bbox/motion heuristic 推断发生接触。

### 输出怎么读

默认输出包括：

- 终端摘要
- JSON 文件
- Markdown 报告

两个关键字段：

- `execution_status`
- `validation_status`

### 常见问题

- 为什么不用原始 `omni_asset_validate` 做主入口  
  因为当前项目已经把更稳定的同步路径、自然语言映射和结构化输出统一收敛到 `omni-asset-cli`
- 为什么终端显示 failed，但命令本身没报错  
  因为 `failed` 指的是校验结论，不一定表示脚本执行异常
- 为什么同时输出 JSON 和 Markdown  
  JSON 适合 agent / CI，Markdown 适合人工复核

## English

### Purpose

This document targets human operators and explains the recommended entry points, outputs, and common usage patterns in the current version.

### Recommended Entry Points

- `omni-asset-cli env`
- `omni-asset-cli validate`
- `omni-asset-cli map`
- `omni-asset-cli validate-from-prompt`
- `omni-asset-cli validate-async`
- `omni-asset-cli physics-hit-test`

If the console script is not installed, fall back to `python3 omni_asset_cli.py ...`.

### Recommended Workflow

1. Start with `env`
2. Use `validate <asset> --profile stage1-furniture` by default for single assets
3. If the request starts from natural language, use `map` or `validate-from-prompt`, for example "validate this as static furniture and decor props"
4. Use `validate-async` only when investigating CLI timeout behavior
5. For runtime physics checks, run `physics-env` first, then `physics-hit-test`

### Stage 1 Furniture/Prop Validation

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as static furniture and decor props"
```

This profile targets static furniture, furnishings, and decorative props. It focuses on entry points, dependencies, materials, and mesh quality. Furniture classification, size references, and static collider recommendations remain owned by the `usd-simready-inspector` static furniture workflow.

### Runtime Physics Template Scene

```bash
omni-asset-cli physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --replace-prim /World/roomScene/colliders/table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/asset_template_hit
```

The recommended Stage 1 path uses top-drop mode: preserve the target furniture/prop asset's real bbox, place the box above the asset bbox center, add a static guide collider aligned to the asset bbox, and let gravity drive the hit. The v1 pass criteria are runtime progress, targeted box placement, preserved size, and contact detection or bbox/motion-based contact inference.

### How to Read the Output

Default outputs include:

- Terminal summary
- JSON file
- Markdown report

Two key fields:

- `execution_status`
- `validation_status`

### FAQ

- Why not use raw `omni_asset_validate` as the default entry point  
  Because the project now consolidates the more stable synchronous path, natural-language mapping, and structured outputs into `omni-asset-cli`
- Why can the terminal show `failed` while the command itself did not crash  
  Because `failed` refers to the validation result, not necessarily a process crash
- Why output both JSON and Markdown  
  JSON is for agents and CI; Markdown is for human review
