# 人类使用手册 / Human Operator Guide

## 目的 / Purpose

这份文档面向人工操作人员，说明当前版本的推荐入口、输出和常见用法。  
This document targets human operators and explains the recommended entry points, outputs, and common usage patterns in the current version.

## 推荐入口 / Recommended Entry Points

- `omni-asset-cli env`
- `omni-asset-cli validate`
- `omni-asset-cli map`
- `omni-asset-cli validate-from-prompt`
- `omni-asset-cli validate-async`

如果没有安装 console script，则回退到 `python3 omni_asset_cli.py ...`。  
If the console script is not installed, fall back to `python3 omni_asset_cli.py ...`.

## 推荐工作流 / Recommended Workflow

1. 先运行 `env`。  
   Start with `env`.
2. 单资产默认运行 `validate`。  
   Use `validate` for single-asset validation by default.
3. 如果需求来自自然语言，用 `map` 或 `validate-from-prompt`。  
   If the request starts from natural language, use `map` or `validate-from-prompt`.
4. 只有排查 CLI timeout 时才使用 `validate-async`。  
   Use `validate-async` only to investigate CLI timeout behavior.

## 输出怎么读 / How to Read the Output

默认输出包括：
Default outputs include:

- 终端摘要 / terminal summary
- JSON 文件 / JSON file
- Markdown 报告 / Markdown report

两个关键字段：
Two key fields:

- `execution_status`: 命令是否正常执行完成  
  Whether the command itself completed successfully
- `validation_status`: 校验结果是 `passed`、`warning`、`failed` 还是 `blocked`  
  Whether validation ended as `passed`, `warning`, `failed`, or `blocked`

## 常见命令 / Common Commands

```bash
omni-asset-cli env
omni-asset-cli validate examples/minimal_scene.usda
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
omni-asset-cli map examples/boat_test/boat.usd "检查引用和材质"
omni-asset-cli validate-from-prompt examples/boat_test/boat.usd "帮我判断是否适合抓取"
```

## 常见问题 / FAQ

### 为什么不用原始 `omni_asset_validate` 做主入口？
### Why not use raw `omni_asset_validate` as the default entry point?

因为当前项目已经把更稳定的同步路径、自然语言映射和结构化输出统一收敛到 `omni-asset-cli`。  
Because the project now consolidates the more stable synchronous path, natural-language mapping, and structured outputs into `omni-asset-cli`.

### 为什么终端显示 failed，但命令本身没报错？
### Why can the terminal show `failed` while the command itself did not crash?

因为 `failed` 指的是校验结论，不一定表示脚本执行异常。  
Because `failed` refers to the validation result, not necessarily a process crash.

### 为什么同时输出 JSON 和 Markdown？
### Why output both JSON and Markdown?

JSON 适合 agent / CI，Markdown 适合人工复核。  
JSON is for agents and CI; Markdown is for human review.

