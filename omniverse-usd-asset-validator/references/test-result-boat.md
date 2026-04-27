# `boat.usd` 测试结果

## 中文说明

### 目标

验证 `boat.usd` 在当前工具链下是否能稳定完成校验，并输出可解释结果。这个样例保留为历史真实资产验证，不作为 Stage 1 家具/摆件主线样例。

### 推荐命令

```bash
omni-asset-cli validate examples/boat_test/boat.usd
```

也可以按场景执行：

```bash
omni-asset-cli validate examples/boat_test/boat.usd --profile stage1-furniture
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile collidable
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
```

### 结论

- 同步路径适合作为主结果来源
- 结果可以稳定输出 JSON 和 Markdown
- Stage 1 主测试应优先使用家具/摆件资产；`boat.usd` 只用于验证真实资产链路稳定性

## English

### Goal

Verify whether `boat.usd` can be validated reliably in the current toolchain and produce interpretable results. This sample is retained as a historical real-asset check, not as the primary Stage 1 furniture/prop sample.

### Recommended Command

```bash
omni-asset-cli validate examples/boat_test/boat.usd
```

You can also validate with a profile:

```bash
omni-asset-cli validate examples/boat_test/boat.usd --profile stage1-furniture
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile collidable
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
```

### Conclusion

- The synchronous path is suitable as the primary result source
- The result can reliably produce JSON and Markdown
- Stage 1 primary tests should use furniture/prop assets; `boat.usd` only verifies the real-asset validation path
