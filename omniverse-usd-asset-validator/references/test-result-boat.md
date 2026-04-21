# `boat.usd` 测试结果

## 中文说明

### 目标

验证 `boat.usd` 在当前工具链下是否能稳定完成校验，并输出可解释结果。

### 推荐命令

```bash
omni-asset-cli validate examples/boat_test/boat.usd
```

也可以按场景执行：

```bash
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile collidable
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
```

### 结论

- 同步路径适合作为主结果来源
- 结果可以稳定输出 JSON 和 Markdown
- 对真实资产，profile 比单纯 rule 列表更适合交付判断

## English

### Goal

Verify whether `boat.usd` can be validated reliably in the current toolchain and produce interpretable results.

### Recommended Command

```bash
omni-asset-cli validate examples/boat_test/boat.usd
```

You can also validate with a profile:

```bash
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile collidable
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
```

### Conclusion

- The synchronous path is suitable as the primary result source
- The result can reliably produce JSON and Markdown
- For real assets, profiles are more useful than raw rule lists for delivery decisions

