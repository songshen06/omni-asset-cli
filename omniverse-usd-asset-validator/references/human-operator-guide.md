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

如果没有安装 console script，则回退到 `python3 omni_asset_cli.py ...`。

### 推荐工作流

1. 先运行 `env`
2. 单资产默认运行 `validate`
3. 如果需求来自自然语言，用 `map` 或 `validate-from-prompt`
4. 只有排查 CLI timeout 时才使用 `validate-async`

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

If the console script is not installed, fall back to `python3 omni_asset_cli.py ...`.

### Recommended Workflow

1. Start with `env`
2. Use `validate` by default for single assets
3. If the request starts from natural language, use `map` or `validate-from-prompt`
4. Use `validate-async` only when investigating CLI timeout behavior

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

