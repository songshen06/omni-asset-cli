# `omni_asset_validate` CLI 超时问题

## 中文说明

### 概述

这份文档记录原始 `omni_asset_validate` CLI 在当前环境中的超时和返回不稳定问题。

当前结论：

- 默认主路径应使用 `omni-asset-cli validate`
- `validate-async` 仅用于观测 CLI 行为，不应作为默认执行路径

### 现象

- 最小样例通常能较快返回
- 真实资产可能出现长时间等待、JSON 延迟落盘或超时
- CLI timeout 不一定代表资产有问题，也可能是执行路径本身不稳定

### 复现方式

```bash
omni-asset-cli validate-async examples/minimal_scene.usda
omni-asset-cli validate-async examples/boat_test/boat.usd
```

### 建议

- 用户和 agent 的默认文档只推荐 `validate`
- 只有排障时才提到 `validate-async`

## English

### Summary

This document records timeout and unstable-return behavior from the raw `omni_asset_validate` CLI in the current environment.

Current conclusion:

- The default path should be `omni-asset-cli validate`
- `validate-async` should only be used to observe CLI behavior, not as the default execution path

### Observed Behavior

- Minimal samples usually return quickly
- Real assets may show long waits, delayed JSON output, or timeouts
- A CLI timeout does not necessarily mean the asset is invalid; the execution path itself may be unstable

### Reproduction

```bash
omni-asset-cli validate-async examples/minimal_scene.usda
omni-asset-cli validate-async examples/boat_test/boat.usd
```

### Recommendation

- User-facing and agent-facing docs should recommend `validate` by default
- Mention `validate-async` only for troubleshooting

