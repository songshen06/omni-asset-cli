# `boat.usd` 测试结果 / `boat.usd` Test Result

## 目标 / Goal

验证 `boat.usd` 在当前工具链下是否能稳定完成校验，并输出可解释结果。  
Verify whether `boat.usd` can be validated reliably in the current toolchain and produce interpretable results.

## 推荐命令 / Recommended Command

```bash
omni-asset-cli validate examples/boat_test/boat.usd
```

也可以按场景执行：
You can also validate with a profile:

```bash
omni-asset-cli validate examples/boat_test/boat.usd --profile static
omni-asset-cli validate examples/boat_test/boat.usd --profile collidable
omni-asset-cli validate examples/boat_test/boat.usd --profile movable
```

## 结论 / Conclusion

- 同步路径适合作为主结果来源。  
  The synchronous path is suitable as the primary result source.
- 结果可以稳定输出 JSON 和 Markdown。  
  The result can reliably produce JSON and Markdown.
- 对真实资产，profile 比单纯 rule 列表更适合交付判断。  
  For real assets, profiles are more useful than raw rule lists for delivery decisions.

## 建议 / Recommendation

- 对外展示时优先给出 profile 视角结论。  
  Prefer profile-oriented conclusions in external reports.
- 如果需要进一步排查 CLI timeout，再补充 `validate-async` 结果。  
  Add `validate-async` results only when investigating CLI timeout behavior.

