# `omni_asset_validate` CLI 超时问题说明

## 1. 问题概述

在当前测试环境中，NVIDIA `omniverse-asset-validator 1.11.2` 提供的命令行工具 `omni_asset_validate` 在执行校验任务时存在可复现的超时问题。

该问题表现为：

- CLI 能够正常启动
- CLI 能够识别目标 USD 资产
- 校验进度日志可推进至 `99%`
- 进程未正常退出
- `--json-output` 结果文件未生成
- 最终只能由外部 `timeout` 强制终止

## 2. 测试环境

- Python: `3.10`
- Package: `omniverse-asset-validator==1.11.2`
- CLI: `omni_asset_validate --version` 返回 `1.11.2`

## 3. 复现步骤

### 3.1 最小样例复现

测试文件：

- `examples/minimal_scene.usda`

执行命令：

```bash
timeout 60s omni_asset_validate --no-variants --no-init-rules --rule StageMetadataChecker examples/minimal_scene.usda
```

预期观测：

- CLI 开始处理资产
- 命令在 60 秒内未正常结束
- 返回码为 `124`

### 3.2 真实资产复现

测试文件：

- `examples/boat_test/boat.usd`

执行命令：

```bash
timeout 60s omni_asset_validate --no-variants --no-init-rules --rule StageMetadataChecker examples/boat_test/boat.usd
```

预期观测：

- CLI 日志通常会推进至 `99%`
- 命令在 60 秒内未正常结束
- 返回码为 `124`

### 3.3 JSON 输出复现

执行命令：

```bash
rm -f /tmp/boat_validation.json
timeout 300s omni_asset_validate --json-output /tmp/boat_validation.json examples/boat_test/boat.usd
ls -l /tmp/boat_validation.json
```

预期观测：

- 命令在 300 秒内仍未正常结束
- `/tmp/boat_validation.json` 未生成

## 4. 排查结论

排查过程已确认以下事实：

1. `Usd.Stage.Open()` 可以快速打开目标资产，耗时约 `0.03s`
2. 最小 USD 样例同样能够复现 timeout
3. 同步 Python API `ValidationEngine.validate(...)` 可以立即返回结果
4. 异步 CLI 路径 `omni_asset_validate` 会卡住

因此可以得出当前工程结论：

“当前环境下，`omniverse-asset-validator 1.11.2` 的 `omni_asset_validate` CLI 在异步执行路径上存在不稳定行为。该问题并非由单个业务资产体量引起，而是工具执行路径本身的可靠性问题。”

## 5. 技术判断

从源码和实测行为综合判断，问题集中在 CLI 使用的异步执行链路：

```text
cli_main
-> asyncio.run(self._validate())
-> engine.validate_with_callbacks(...)
-> checker.check_async(...)
```

而同步链路：

```text
ValidationEngine.validate(...)
-> checker.check(...)
```

在同一环境下表现正常。

因此，当前阶段可将问题归类为：

- CLI 异步校验路径异常
- 同步 Python API 可用

## 6. 建议处理方案

当前项目的建议方案如下：

1. 不将 `omni_asset_validate` CLI 作为 agent 主执行入口
2. 改为使用同步 Python API 封装脚本执行单资产校验
3. 将 CLI 保留为环境核验工具和超时行为观察工具
4. 后续如需向 NVIDIA 报告问题，可直接提交本文档中的复现步骤与现象说明

## 7. 当前替代方案

当前 skill 中已提供同步替代脚本：

- `omniverse-usd-asset-validator/scripts/run_sync_validation.py`

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json
```

该脚本已验证可以：

- 正常返回
- 输出结构化 JSON
- 输出人类可读摘要
