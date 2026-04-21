# `omni_asset_validate` CLI 超时问题 / `omni_asset_validate` CLI Timeout Issue

## 概述 / Summary

这个文档记录原始 `omni_asset_validate` CLI 在当前环境中的超时和返回不稳定问题。  
This document records timeout and unstable-return behavior from the raw `omni_asset_validate` CLI in the current environment.

当前结论：  
Current conclusion:

- 默认主路径应使用 `omni-asset-cli validate`。  
  The default path should be `omni-asset-cli validate`.
- `validate-async` 仅用于观测 CLI 行为，不应作为默认执行路径。  
  `validate-async` should be used for CLI observation only, not as the default execution path.

## 现象 / Observed Behavior

- 最小样例通常能较快返回。  
  Minimal samples usually return quickly.
- 真实资产可能出现长时间等待、JSON 延迟落盘或超时。  
  Real assets may show long waits, delayed JSON output, or timeouts.
- CLI timeout 不一定代表资产有问题，也可能是执行路径本身不稳定。  
  A CLI timeout does not necessarily mean the asset is invalid; the execution path itself may be unstable.

## 复现方式 / Reproduction

```bash
omni-asset-cli validate-async examples/minimal_scene.usda
omni-asset-cli validate-async examples/boat_test/boat.usd
```

## 判断 / Interpretation

- 如果 `validate` 成功而 `validate-async` 超时，应优先相信同步路径结果。  
  If `validate` succeeds but `validate-async` times out, prefer the synchronous result.
- 如果两个路径都失败，再排查环境、依赖和资产本身。  
  If both paths fail, investigate the environment, dependencies, and the asset itself.

## 建议 / Recommendation

- 面向用户和 agent 的默认文档只推荐 `validate`。  
  User-facing and agent-facing docs should recommend `validate` by default.
- 只在需要技术排障时提到 `validate-async`。  
  Mention `validate-async` only for technical troubleshooting.

