# 自然语言到脚本参数对照表

本文档说明自然语言请求如何映射到当前 skill 的主执行脚本：

```bash
python scripts/run_sync_validation.py <asset> [options]
```

## 1. 默认规则

当用户只说“检查这个 USD”而没有指定范围时，建议执行：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json
```

说明：

- 不额外指定 `--rule`
- 不额外指定 `--category`
- 由同步包装脚本输出结构化结果和摘要
- 输出结果中应优先读取 `execution_status` 与 `validation_status`

## 2. 常见映射表

| 自然语言意图 | 推荐脚本参数 |
| --- | --- |
| 检查这个 USD | `--output-json /tmp/asset_validation.json` |
| 输出 JSON | `--output-json /tmp/asset_validation.json` |
| 检查 stage metadata | `--rule StageMetadataChecker` |
| 检查 defaultPrim | `--rule DefaultPrimChecker` |
| 检查 Isaac Sim 资产结构 | `--rule KindChecker` |
| 检查 SimReady 层级是否合理 | `--rule KindChecker` |
| 检查组件层级 / component hierarchy | `--rule KindChecker` |
| 检查丢失引用 | `--rule MissingReferenceChecker` |
| 检查贴图问题 | `--rule TextureChecker` |
| 检查几何问题 | `--category Geometry` |
| 检查材质问题 | `--category Material` |
| 检查 physics 问题 | `--category Physics` |
| 检查 extents | `--rule ExtentsChecker` |
| 检查 topology | `--rule ValidateTopologyChecker` |
| 检查 normals | `--rule NormalsValidChecker` |
| 检查 zero-area face | `--rule ZeroAreaFaceChecker` |
| 检查 non-manifold | `--rule ManifoldChecker` |
| 检查 unused primvar | `--rule UnusedPrimvarChecker` |
| 检查 indexed primvar | `--rule IndexedPrimvarChecker` |
| 检查 subdivision | `--rule SubdivisionSchemeChecker` |
| 只看 error | `--predicate IsError` |
| 只看 failure | `--predicate IsFailure` |
| 只看 warning | `--predicate IsWarning` |
| 启用默认规则 | `--init-rules` |
| 启用 variant 处理 | `--variants` |

## 3. 示例对照

### 3.1 通用检查

自然语言：

```text
帮我检查这个 USD：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --output-json /tmp/asset_validation.json
```

### 3.2 基础元数据

自然语言：

```text
检查这个文件有没有 upAxis 和 metersPerUnit 问题：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --rule StageMetadataChecker --output-json /tmp/stage_metadata.json
```

### 3.3 引用检查

自然语言：

```text
帮我查这个资产有没有丢失引用：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --rule MissingReferenceChecker --output-json /tmp/missing_reference.json
```

### 3.4 Isaac Sim / SimReady 结构检查

自然语言：

```text
帮我检查这个机器人资产的 Isaac Sim 层级结构是否合理：/path/to/robot.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/robot.usd --rule KindChecker --output-json /tmp/kind_structure.json
```

### 3.5 Mesh topology

自然语言：

```text
检查这个 mesh 的 topology：/path/to/mesh.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/mesh.usd --rule ValidateTopologyChecker --output-json /tmp/topology.json
```

### 3.6 Normals

自然语言：

```text
检查 normals 是否有效：/path/to/mesh.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/mesh.usd --rule NormalsValidChecker --output-json /tmp/normals.json
```

### 3.7 Geometry category

自然语言：

```text
帮我做一轮 geometry 检查：/path/to/mesh.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/mesh.usd --category Geometry --output-json /tmp/geometry.json
```

### 3.8 Material category

自然语言：

```text
只看材质类问题：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --category Material --output-json /tmp/material.json
```

### 3.9 Physics category

自然语言：

```text
检查这个资产的 physics 问题：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --category Physics --output-json /tmp/physics.json
```

### 3.10 多规则组合

自然语言：

```text
检查这个 mesh 的 topology、normals 和 zero-area face：/path/to/mesh.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/mesh.usd \
  --rule ValidateTopologyChecker \
  --rule NormalsValidChecker \
  --rule ZeroAreaFaceChecker \
  --output-json /tmp/mesh_combo.json
```

### 3.11 只看错误

自然语言：

```text
检查这个资产，但我只想看错误：/path/to/asset.usd
```

推荐命令：

```bash
python scripts/run_sync_validation.py /path/to/asset.usd --predicate IsError --output-json /tmp/errors_only.json
```

## 4. 业务口吻示例映射

| 自然语言 | 推荐命令思路 |
| --- | --- |
| 这个资产能不能过基础质检？ | 默认校验 |
| 这个 USD 有没有阻塞性问题？ | 默认校验，必要时加 `--predicate IsFailure` |
| 帮我做交付前检查 | 默认校验，必要时补 `Geometry` 或 `Material` |
| 看看这个 mesh 有没有明显问题 | `--category Geometry` |
| 看看这个资产的引用是不是完整 | `--rule MissingReferenceChecker` |
| 看看这个 Isaac Sim 资产层级是不是对的 | `--rule KindChecker` |

## 5. 当前项目建议

当前建议采用如下优先级：

1. 单资产默认使用 `run_sync_validation.py`
2. 需要聚焦特定问题时，补充 `--rule`
3. 需要按领域检查时，补充 `--category`
4. 需要过滤结果时，补充 `--predicate`
5. 不再默认依赖原始 `omni_asset_validate` CLI 作为主执行路径

补充说明：

- `run_sync_validation.py` 返回退出码 `0` 并不代表资产一定通过
- 应首先读取 JSON 中的 `execution_status`
- 如果 `execution_status=completed`，再读取 `validation_status` 判断资产是否 `passed / warning / failed`
- `KindChecker` 不应默认附加到所有校验请求
- 仅当用户明确提到 Isaac Sim 结构、SimReady 层级、组件语义、资产结构或 hierarchy 问题时，才建议加入 `--rule KindChecker`
