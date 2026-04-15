# Omniverse Asset Validator 部署与使用说明

## 1. 文档目的

本文档说明基于 NVIDIA `omniverse-asset-validator` 独立 Python 包的标准部署方式，以及在该环境中通过命令行接口执行 USD 资源校验的方法。

本文档仅覆盖以下推荐方案：

- 使用独立 Python 虚拟环境进行部署
- 使用 `pip install "omniverse-asset-validator[usd,numpy]"` 完成安装
- 使用独立命令行工具 `omni_asset_validate` 执行资源校验

本文档不涉及 Omniverse Kit 插件界面启用流程，也不依赖 Omniverse UI。

## 2. 方案说明

`omniverse-asset-validator` 是 NVIDIA 提供的独立 Python Library，并同时提供独立的命令行接口 `omni_asset_validate`。

采用该方案后，系统可直接在终端、自动化脚本、CI 流程及 Agent 环境中调用资源校验能力，而无需预先启动 Omniverse Kit 或通过 Extension Manager 启用图形界面插件。

对于 Codex 等 Agent 场景，建议通过独立 Python 虚拟环境调用验证能力，以确保运行环境稳定、依赖边界清晰、命令执行路径可控。
在当前项目中，推荐优先通过同步 Python API 包装脚本执行校验，而不是直接依赖 `omni_asset_validate` CLI。

## 3. 推荐运行环境

根据 NVIDIA 文档，`omniverse-asset-validator` 支持的 Python 版本范围为 `3.10` 至 `3.12`。

本方案推荐使用 `Python 3.10`，原因如下：

- 与官方支持范围完全一致
- 兼容性风险相对较低
- 便于客户环境标准化与后续维护

如客户现有环境已稳定运行 Python `3.11` 或 `3.12`，亦可使用，但在无特殊前提下，建议优先采用 Python `3.10`。

## 4. 安装方式

建议始终使用 `venv` 创建独立虚拟环境，以避免系统 Python 污染及与其他项目依赖发生冲突。

### 4.1 Linux / macOS

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

### 4.2 Windows PowerShell

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

### 4.3 安装说明

本方案固定推荐以下安装形式：

```bash
python -m pip install "omniverse-asset-validator[usd,numpy]"
```

说明如下：

- `usd` extra 用于补齐 OpenUSD 相关运行依赖
- `numpy` extra 用于启用文档中提到的可选 NumPy 支持
- `python -m pip` 的调用方式可确保安装动作明确发生在当前虚拟环境对应的 Python 解释器中

## 5. 安装后验证

安装完成后，应首先确认命令行工具是否可用。

### 5.1 检查 CLI 是否安装成功

```bash
omni_asset_validate --help
```

若命令能够正常输出帮助信息，则表明 CLI 已正确安装。

### 5.2 执行最小验证

```bash
omni_asset_validate /path/to/asset.usda
```

若命令能够返回验证结果，则表明运行环境已可用于实际 USD 资源检查。

## 6. Agent 集成建议

为确保 Codex 或其他 Agent 在执行资源校验时始终使用正确的 Python 解释器与依赖集合，必须保证所有验证命令运行在上述虚拟环境中。

推荐以下两种调用方式。

### 6.1 方式一：激活虚拟环境后执行

```bash
source .venv/bin/activate
omni_asset_validate /path/to/asset.usda
```

### 6.2 方式二：直接调用虚拟环境中的可执行文件

Linux / macOS:

```bash
.venv/bin/omni_asset_validate /path/to/asset.usda
```

Windows:

```powershell
.venv\Scripts\omni_asset_validate.exe C:\path\to\asset.usda
```

对于自动化系统与 Agent 场景，推荐优先采用方式二。该方式不依赖当前 Shell 会话状态，更适合批处理、服务化调用与工具链集成。

### 6.3 推荐主执行方式

在本 skill 中，推荐默认执行方式如下：

```bash
python scripts/run_sync_validation.py /path/to/asset.usda --output-json /tmp/asset_validation.json
```

该脚本通过 `omniverse-asset-validator` 的同步 Python API 执行验证，并直接生成结构化 JSON 与人类可读摘要。
同时它会区分“程序执行状态”和“资产校验状态”，避免将“校验失败”误判为“脚本运行失败”。

选择该方式的原因是：当前环境下 `omni_asset_validate` 的异步 CLI 路径存在超时现象，而同步 Python API 已验证可以稳定返回结果。

## 7. 与 Skill 的配合方式

在本项目中，Agent Skill 的职责如下：

1. 接收用户的自然语言检查请求
2. 将自然语言需求转换为同步验证脚本的具体参数
3. 在指定虚拟环境中执行验证脚本
4. 读取并整理验证结果，输出面向业务用户的结论与建议

典型执行流程如下：

1. 用户提出校验请求，例如“请检查该 USD 资源是否存在引用缺失问题”
2. Agent 识别待检查的文件或目录路径
3. Agent 在 `.venv` 环境中调用 `run_sync_validation.py`
4. Agent 对输出结果进行归纳，形成错误说明、影响判断与后续建议

该方式可将用户自然语言请求稳定映射为 NVIDIA 官方支持的 USD 资源校验流程。

在读取结果时，建议区分两个字段：

- `execution_status`
  用于判断脚本是否正常执行完成

- `validation_status`
  用于判断资产是否通过校验

这意味着：

- 资产校验失败时，脚本仍可以正常执行完成
- 只有脚本本身执行异常时，才应被视为程序错误

## 8. 长耗时资产的执行建议

对于真实业务资产，尤其是包含分层、引用、贴图或 SimReady 元数据的 USD 资源，不应假设验证过程能够在数秒内完成。

对于单个 USD 资产，建议优先尝试同步 Python API 路径；仅当需要专门观察 CLI 行为或复现 CLI 超时问题时，才使用异步 CLI 包装脚本。

建议采用以下执行策略：

1. 默认使用 `--json-output` 输出结构化结果
2. 采用较长超时窗口执行验证任务
3. 由 Agent 或后台任务轮询结果文件是否生成
4. 若在规定时间内未完成，则返回“验证已启动但未在时间窗口内完成”的运行状态，而不是输出未经证实的验证结论

建议命令形式如下：

```bash
python scripts/run_async_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json --timeout-seconds 300
```

对 Agent 而言，推荐将该流程设计为异步任务，而非短超时同步调用。

## 9. 测试结论说明方式

当验证完成时，应输出结构化检查结论。

当验证未在规定时间内完成时，应输出运行结论，例如：

“目标资产已被验证器成功识别并开始处理，但在当前时间窗口内未完成完整校验，因此当前结果应判定为校验链路已接通、验证任务已启动，但尚未生成最终验证报告。” 

## 10. 推荐对外说明口径

建议在对客户说明时使用以下正式表述：

“本方案采用 NVIDIA 提供的 `omniverse-asset-validator` 独立 Python 包，而非依赖 Omniverse Kit 图形界面插件。部署时建议使用 Python 3.10，并通过 `venv` 创建独立虚拟环境，随后执行 `python -m pip install "omniverse-asset-validator[usd,numpy]"` 完成安装。安装成功后，系统将提供独立命令行接口 `omni_asset_validate`。基于该接口，Codex 等 Agent 可在指定虚拟环境中执行 USD 资源校验命令，并将自然语言请求转换为标准化的验证操作与结果反馈。” 
