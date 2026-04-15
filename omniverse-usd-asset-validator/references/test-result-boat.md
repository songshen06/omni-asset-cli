# `boat.usd` 测试结果

## 1. 测试目标

目标资产：

- `examples/boat_test/boat.usd`

测试目的：

- 验证 `omniverse-asset-validator` 独立 CLI 是否可以识别并处理真实 USD 资产
- 验证 Skill 是否能够将自然语言检查请求映射为可执行命令
- 验证 `--json-output` 是否能够在当前环境中产出结构化结果

## 2. 测试命令

执行过的代表性命令如下：

```bash
timeout 300s omni_asset_validate --json-output /tmp/boat_validation.json examples/boat_test/boat.usd
```

```bash
timeout 180s omni_asset_validate --no-init-rules --rule StageMetadataChecker --json-output /tmp/boat_stage_metadata.json examples/boat_test/boat.usd
```

```bash
timeout 180s omni_asset_validate --no-init-rules --rule MissingReferenceChecker --json-output /tmp/boat_missing_ref.json examples/boat_test/boat.usd
```

以及异步包装脚本测试：

```bash
python scripts/run_async_validation.py examples/boat_test/boat.usd --output-json /tmp/boat_async_wrapper.json --timeout-seconds 20 --poll-seconds 2 --no-variants --no-init-rules --rule StageMetadataChecker
```

## 3. 实际观测

CLI 可以正常启动，并进入资产处理流程。

在测试过程中观察到的典型日志为：

```text
INFO:omni.asset_validator._cli:Processing .../boat.usd........0%
INFO:omni.asset_validator._cli:Processing .../boat.usd........99%
```

说明如下：

- 命令行入口可用
- 目标资产可被识别
- 验证流程已实际开始执行
- 异步包装脚本能够在超时后输出人类可读的运行摘要

## 4. 测试结果

在当前测试环境下，以上命令均未在设定超时窗口内正常完成。

结果表现为：

- 30 秒、60 秒、120 秒、180 秒、300 秒超时窗口内均未获得正常结束
- 对应 `--json-output` 结果文件未生成
- 因此未取得最终结构化校验结果
- 异步包装脚本在 20 秒超时窗口下返回了清晰的超时摘要，并保留了实际处理进度信息

## 5. 简要判断

本次测试结果表明：`boat.usd` 已能够被 `omni_asset_validate` 正常识别并开始校验，但在当前环境中未能在既定时间窗口内完成验证，也未生成 JSON 报告。

因此，本次测试的正式结论为：

“校验链路已接通，真实资产验证任务可以启动，但当前该资产的完整验证耗时较长，暂不适合作为短超时同步调用。后续建议采用异步执行、结果轮询和超时状态回传的接入方式。” 

异步包装脚本的实际输出摘要如下：

```text
Status: timed_out
Target: examples/boat_test/boat.usd
Command: omni_asset_validate --json-output /tmp/boat_async_wrapper.json --no-variants --no-init-rules --rule StageMetadataChecker examples/boat_test/boat.usd
ElapsedSeconds: 20.0
JSONOutput: /tmp/boat_async_wrapper.json
ReturnCode: -9
Summary:
- INFO:omni.asset_validator._cli:Processing examples/boat_test/boat.usd........99%
```

## 6. 同步 Python API 复测

为规避 CLI 异步路径的超时问题，新增了同步包装脚本：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json --rule StageMetadataChecker
```

实际复测结果如下。

最小样例 `minimal_scene.usda`：

```text
Status: failed
Target: examples/minimal_scene.usda
ElapsedSeconds: 0.028
IssueCount: 2
SeverityCounts: {"FAILURE": 2}
Summary:
- [FAILURE] StageMetadataChecker: Stage does not specify an upAxis.
- [FAILURE] StageMetadataChecker: Stage does not specify its linear scale in metersPerUnit.
```

真实资产 `boat.usd`：

```text
Status: passed
Target: examples/boat_test/boat.usd
ElapsedSeconds: 0.039
IssueCount: 0
SeverityCounts: {}
Summary:
- 未发现校验问题。
```

因此，当前阶段的正式建议调整为：

“对于单个 USD 资产的 agent 校验流程，优先使用同步 Python API 包装脚本 `run_sync_validation.py`。该路径已验证可以稳定输出 JSON 与人类摘要；`omni_asset_validate` CLI 仅保留用于环境核验和超时行为观察，不作为主执行路径。” 
