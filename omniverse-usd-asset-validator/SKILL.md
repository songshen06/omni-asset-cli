---
name: omniverse-usd-asset-validator
description: Validate OpenUSD or USDZ assets with NVIDIA Omniverse Asset Validator. Use this skill when the user wants to check a USD asset, map natural-language validation requests into deterministic arguments, or explain validation results in Chinese and English.
---

# Omniverse USD Asset Validator

使用这个 skill 来校验 USD 资产、把自然语言映射成确定性参数，并输出适合人类和 agent 消费的结果。  
Use this skill to validate USD assets, map natural-language requests into deterministic arguments, and return results suitable for both humans and agents.

## 默认入口 / Default Entry Point

优先使用已安装的 `omni-asset-cli`。  
Prefer the installed `omni-asset-cli`.

如果当前环境还没有安装 console script，则回退到：  
If the console script is not installed yet, fall back to:

```bash
python3 omni_asset_cli.py ...
```

## 工作流 / Workflow

1. 确定目标资产。  
   Identify the target asset.
2. 先检查环境，尤其是 Python、`omniverse-asset-validator` 包和 `omni_asset_validate` 是否可用。  
   Check the environment first, especially Python, the `omniverse-asset-validator` package, and `omni_asset_validate`.
3. 如果用户是自然语言请求，先执行 `map` 或 `validate-from-prompt`。  
   If the user starts from natural language, use `map` or `validate-from-prompt`.
4. 对单资产默认使用同步路径 `validate`。  
   Use synchronous `validate` by default for single assets.
5. 只有在明确要观察 CLI timeout 行为时才使用 `validate-async`。  
   Use `validate-async` only when you explicitly need to observe CLI timeout behavior.

## 推荐命令 / Recommended Commands

检查环境：
Check the environment:

```bash
omni-asset-cli env
```

默认校验：
Default validation:

```bash
omni-asset-cli validate path/to/asset.usd
```

按资产场景校验：
Validate with a profile:

```bash
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

自然语言映射：
Natural-language mapping:

```bash
omni-asset-cli map path/to/asset.usd "check references"
omni-asset-cli map path/to/asset.usd "检查 Isaac Sim 结构"
```

自然语言直接执行：
Map and execute directly:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "帮我按静态资产场景检查"
```

## 自然语言处理约定 / Natural-Language Handling Rules

- 默认只做只读校验，不自动加 `--fix`。  
  Default to read-only validation and do not add `--fix` unless asked.
- 如果用户没有明确缩小范围，保留默认规则。  
  Keep the default rules unless the user explicitly narrows the scope.
- 如果 prompt 没命中特定规则，回退到标准校验。  
  If the prompt does not match a specific rule, fall back to standard validation.
- 只有用户明确提到 Isaac Sim、SimReady、层级或组件语义时，优先考虑 `KindChecker`。  
  Prefer `KindChecker` only when the user explicitly asks about Isaac Sim, SimReady, hierarchy, or component semantics.

## 响应格式 / Response Pattern

建议输出以下信息：
Include the following in the response:

- `Target`
- `Command`
- `Result`
- `Next step`

如果生成了 JSON 或 Markdown，也说明输出路径。  
If JSON or Markdown output was produced, mention the output path as well.

## 环境约定 / Environment Contract

- 推荐 Python 3.10。  
  Python 3.10 is the recommended baseline.
- 可接受 3.10 到 3.12。  
  Python 3.10 to 3.12 is acceptable.
- 推荐安装方式：  
  Recommended install shape:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

## 长耗时策略 / Long-Running Policy

- 默认 structured validation：`omni-asset-cli validate`  
  Default structured validation: `omni-asset-cli validate`
- CLI timeout 观测：`omni-asset-cli validate-async`  
  CLI timeout observation: `omni-asset-cli validate-async`

运行状态可分为：
Operational states:

- `completed`
- `timed_out`
- `blocked`

## 文档入口 / References

- `references/environment-and-setup.md`
- `references/cli-mapping.md`
- `references/human-operator-guide-zh.md`
- `references/natural-language-to-args-zh.md`
- `references/kind-checker-explained-zh.md`

