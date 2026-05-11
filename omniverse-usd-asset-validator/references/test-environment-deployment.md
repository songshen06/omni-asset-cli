# Test Environment Deployment

## 中文说明

### 目标

这份文档记录 `omni-asset-cli` 的本地测试环境部署方式，以及与 `usd-simready-inspector` 产物联调时的验证流程。

当前环境分两层：

- `omni-asset-cli/.venv`：运行 OpenUSD 静态 validator、CLI 映射和报告生成。
- Isaac Sim Docker 或已启动容器：运行 `physics-hit-test` 的 240 帧 runtime 物理 smoke test。

### 1. 部署 validator venv

从 `omni-asset-cli` 仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[validator]"
```

安装完成后确认 Python、USD 和 Omniverse validator 都可 import：

```bash
.venv/bin/python -c "from pxr import Usd; import omni.asset_validator; print('pxr ok'); print('validator ok')"
```

如果用 console script，建议先激活 venv，让 `omni_asset_validate` 也进入 `PATH`：

```bash
source .venv/bin/activate
omni-asset-cli env
```

未激活 venv 而直接运行 `.venv/bin/omni-asset-cli env` 时，项目 CLI 仍可运行，但环境探测里的 `omni_asset_validate` 可能因为 `PATH` 未包含 `.venv/bin` 而显示未找到。

### 2. 静态 validator 复测

对 `usd-simready-inspector` 生成的 cup 静态资产复测：

```bash
.venv/bin/omni-asset-cli validate \
  /home/horde/usd-simready-inspector/out/cup.simready_static.usda \
  --profile stage1-furniture \
  --output-json /home/horde/usd-simready-inspector/out/cup.omni_validator.retest.json \
  --output-md /home/horde/usd-simready-inspector/out/cup.omni_validator.retest.md
```

本次复测结果：

```text
ExecutionStatus: completed
ValidationStatus: failed
IssueCount: 5
SeverityCounts: {"FAILURE": 3, "WARNING": 2}
```

主要问题：

- `MaterialPathChecker`: 3 个 failure，`gltf/pbr.mdl` 应改成 `./gltf/pbr.mdl`。
- `ManifoldChecker`: 565 个 non-manifold vertices。
- `WeldChecker`: 存在 co-located points，可考虑合并。

这说明 validator 环境已经部署成功；当前结果是资产/导出内容的真实校验失败，不再是环境 `blocked`。

### 3. Isaac Sim runtime 环境

普通 validator venv 不负责启动 Isaac Sim。物理 runtime 检查依赖 Isaac Sim Docker 镜像或已运行容器。

推荐先使用仓库脚本完成前置检查、缓存目录准备、容器启动和 probe：

```bash
scripts/deploy_isaacsim_docker.sh --check
scripts/deploy_isaacsim_docker.sh --start --probe-container
```

如果是新机器，需要拉取镜像并启动容器：

```bash
scripts/deploy_isaacsim_docker.sh --all
```

脚本默认使用：

```text
image: nvcr.io/nvidia/isaac-sim:5.1.0
container: isaac-sim
workspace: /workspace/omni-asset-cli
docker python: /isaac-sim/python.sh
```

探测 Docker runtime：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

复用已启动容器：

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

容器需要能看到两个挂载位置：

- `/workspace/omni-asset-cli`
- `/workspace/external/usd-simready-inspector`

### 4. 240 帧 tabletop top-drop 流程

`~/new_3D/cup.usd` 已经通过 `usd-simready-inspector` 生成静态资产：

```text
/home/horde/usd-simready-inspector/out/cup.simready_static.usda
```

已完成的标准 240 帧 runtime 检查产物：

```text
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_hit_standard_check/summary.json
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_hit_standard_check/runtime_report.json
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_hit_standard_check/timeline.csv
```

结果摘要：

```text
result: passed
frames: 240
sample_count: 240
contact_detected_or_inferred: true
```

带渲染帧的 240 帧 rerun 产物：

```text
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_render_240_rerun/
```

其中 `render_frames/` 包含 240 张 PNG，`timeline.csv` 为 header 加 240 帧采样。

### 5. 推荐验收顺序

1. 部署并激活 `.venv`。
2. 运行 `omni-asset-cli env`，确认 validator 包可用。
3. 运行 Stage 1 validator，确认结果不是 `blocked`。
4. 修复 validator failure 后复测。
5. 使用 Isaac Sim Docker 或已启动容器跑 240 帧 `physics-hit-test`。
6. 读取 `summary.json`、`runtime_report.json` 和 `timeline.csv`，确认 `result=passed`、`sample_count=240`。

## English

### Purpose

This document records the local test environment deployment for `omni-asset-cli` and the integration flow with artifacts produced by `usd-simready-inspector`.

The environment has two layers:

- `omni-asset-cli/.venv`: runs OpenUSD static validation, CLI mapping, and report generation.
- Isaac Sim Docker or an existing Isaac Sim container: runs the 240-frame runtime physics smoke test.

### Validator Setup

From the `omni-asset-cli` repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install --no-build-isolation -e ".[validator]"
```

Verify imports:

```bash
.venv/bin/python -c "from pxr import Usd; import omni.asset_validator; print('pxr ok'); print('validator ok')"
```

Activate the venv before using the console scripts:

```bash
source .venv/bin/activate
omni-asset-cli env
```

### Cup Retest Result

The retest command:

```bash
.venv/bin/omni-asset-cli validate \
  /home/horde/usd-simready-inspector/out/cup.simready_static.usda \
  --profile stage1-furniture \
  --output-json /home/horde/usd-simready-inspector/out/cup.omni_validator.retest.json \
  --output-md /home/horde/usd-simready-inspector/out/cup.omni_validator.retest.md
```

Current result:

```text
ExecutionStatus: completed
ValidationStatus: failed
IssueCount: 5
SeverityCounts: {"FAILURE": 3, "WARNING": 2}
```

The validator environment is now working. The remaining failures are real asset/export issues, not environment blockers.

### Runtime Test

Use Isaac Sim Docker or an existing container for runtime physics checks. The known successful cup run produced:

```text
result: passed
frames: 240
sample_count: 240
contact_detected_or_inferred: true
```

Primary artifacts:

```text
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_hit_standard_check/
/home/horde/usd-simready-inspector/out/cup_omni_tabletop_render_240_rerun/
```
