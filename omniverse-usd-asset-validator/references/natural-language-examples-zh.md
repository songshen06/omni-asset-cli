# 自然语言调用示例

本文档给出调用 `omniverse-usd-asset-validator` skill 的自然语言示例，供 Agent、实施人员或测试人员参考。

默认假设 skill 名为：

```text
$omniverse-usd-asset-validator
```

## 1. 通用检查

- `用 $omniverse-usd-asset-validator 检查这个 USD 文件：/path/to/chair.usda`
- `帮我验证这个 USD 资产有没有基础合规问题：/path/to/asset.usd`
- `检查这个 usdz 包：/path/to/model.usdz`
- `帮我看这个资产目录里的 USD 是否能通过基础校验：/path/to/assets/`
- `验证这个文件，并给我一个简短中文结论：/path/to/scene.usda`

## 2. 结构化输出

- `用 $omniverse-usd-asset-validator 检查 /path/to/asset.usd，并输出 JSON`
- `帮我验证这个 USD，并把结果保存成 json：/path/to/asset.usd`
- `检查 /path/to/asset.usd，结果输出到 /tmp/asset_validation.json`
- `给我一个结构化验证结果，目标文件是 /path/to/asset.usd`
- `跑一次校验并返回 issue count、severity counts 和摘要：/path/to/asset.usd`

## 3. 基础元数据

- `检查这个 USD 的 stage metadata：/path/to/asset.usd`
- `帮我看这个文件有没有 upAxis 和 metersPerUnit 问题：/path/to/asset.usd`
- `只检查 defaultPrim 和基础舞台元数据：/path/to/asset.usd`
- `验证这个资产的基础元信息是否完整：/path/to/asset.usd`
- `用 StageMetadataChecker 检查 /path/to/asset.usd`

## 4. 引用与依赖

- `检查这个 USD 有没有丢失引用：/path/to/asset.usd`
- `帮我查这个资产是否引用了不存在的 usd、纹理或依赖：/path/to/asset.usd`
- `只看 missing reference 问题：/path/to/asset.usd`
- `检查这个场景里的外部依赖是否完整：/path/to/scene.usda`
- `验证 /path/to/asset.usd 的引用链是否有断裂`

## 5. 材质与贴图

- `检查这个资产的材质问题：/path/to/asset.usd`
- `只看 material category 的问题：/path/to/asset.usd`
- `帮我查贴图引用和材质定义有没有问题：/path/to/asset.usd`
- `检查这个模型的纹理和材质合规性：/path/to/asset.usd`
- `只验证材质相关规则，并输出 JSON：/path/to/asset.usd`

## 6. Mesh / Geometry

- `检查这个模型的 mesh 拓扑：/path/to/mesh_asset.usd`
- `帮我验证这个 USD 的 geometry 问题：/path/to/mesh_asset.usd`
- `只检查 zero-area face：/path/to/mesh_asset.usd`
- `帮我看这个 mesh 有没有 non-manifold 问题：/path/to/mesh_asset.usd`
- `检查 normals 是否有效：/path/to/mesh_asset.usd`
- `验证这个资产的 topology、normals 和 extents：/path/to/mesh_asset.usd`
- `只跑 ValidateTopologyChecker：/path/to/mesh_asset.usd`
- `只跑 NormalsValidChecker 和 ZeroAreaFaceChecker：/path/to/mesh_asset.usd`
- `帮我做一轮 Geometry category 检查：/path/to/mesh_asset.usd`

## 7. Physics

- `检查这个资产的 physics 问题：/path/to/asset.usd`
- `只看 physics category：/path/to/asset.usd`
- `帮我验证 rigid body、collider 和 joint 相关问题：/path/to/asset.usd`
- `检查这个 USD 的物理配置是否合法：/path/to/asset.usd`

## 8. 精确指定 rule

- `用 $omniverse-usd-asset-validator 只跑 StageMetadataChecker：/path/to/asset.usd`
- `只跑 MissingReferenceChecker：/path/to/asset.usd`
- `只检查 TextureChecker：/path/to/asset.usd`
- `只运行 DefaultPrimChecker：/path/to/asset.usd`
- `只用 ValidateTopologyChecker 检查这个 mesh：/path/to/asset.usd`

## 9. 组合多个 rule

- `检查这个 USD，只跑 StageMetadataChecker 和 MissingReferenceChecker：/path/to/asset.usd`
- `帮我组合检查 topology、normals 和 extents：/path/to/asset.usd`
- `只跑 ZeroAreaFaceChecker、NormalsValidChecker、ValidateTopologyChecker：/path/to/asset.usd`
- `检查这个模型的 mesh 质量，只启用几何相关的几条规则：/path/to/asset.usd`

## 10. 按 category

- `只检查 Geometry category：/path/to/asset.usd`
- `只检查 Material category：/path/to/asset.usd`
- `帮我按 Physics category 跑一遍：/path/to/asset.usd`
- `先只看 Basic category：/path/to/asset.usd`

## 11. 输出给人读的结论

- `检查这个 USD，然后给我一句话结论：/path/to/asset.usd`
- `验证这个资产，并告诉我它大致是通过、警告还是失败：/path/to/asset.usd`
- `帮我检查 /path/to/asset.usd，最后用中文总结关键问题`
- `不要只给原始日志，帮我输出可读摘要：/path/to/asset.usd`
- `检查这个文件，并列出最重要的前 5 个问题：/path/to/asset.usd`

## 12. 面向交付或报告

- `帮我验证这个资产，输出 JSON 并附一段适合发给客户的说明：/path/to/asset.usd`
- `检查这个 USD，给我一个测试结果摘要和建议：/path/to/asset.usd`
- `验证 /path/to/asset.usd，并告诉我是否适合进入下一步交付`
- `帮我做一版可读的 QA 结论：/path/to/asset.usd`

## 13. 面向 agent 工作流

- `用 $omniverse-usd-asset-validator 检查这个资产并保存结构化结果，然后给我中文摘要：/path/to/asset.usd`
- `调用这个 skill，验证这个 USD 的基础元数据和引用完整性：/path/to/asset.usd`
- `用这个 skill 做单资产校验，输出 json 和人类摘要：/path/to/asset.usd`
- `把自然语言需求转成验证动作：检查这个 mesh 的 topology 和 normals：/path/to/asset.usd`

## 14. 目录级调用

- `检查这个目录下所有 USD 资产：/path/to/assets/`
- `帮我看这个目录中的资产有没有基础 metadata 问题：/path/to/assets/`
- `只扫描这个目录里的几何类问题：/path/to/assets/`
- `对这个资产目录做一轮结构化验证，并输出汇总结果：/path/to/assets/`

## 15. 偏业务口吻

- `这个资产能不能过基础质检？/path/to/asset.usd`
- `帮我看这个模型有没有明显的 USD 合规问题：/path/to/asset.usd`
- `这个资产的基础结构是否完整？/path/to/asset.usd`
- `帮我做一次交付前检查：/path/to/asset.usd`
- `看看这个 USD 有没有阻塞性问题：/path/to/asset.usd`

## 16. 基于当前 boat 资产的示例

- `用 $omniverse-usd-asset-validator 检查这个 boat 资产的 stage metadata：examples/boat_test/boat.usd`
- `帮我验证这个 boat 资产有没有引用缺失：examples/boat_test/boat.usd`
- `只检查这个 boat 资产的 geometry 问题，并输出 json：examples/boat_test/boat.usd`
- `帮我对这个 boat 资产做基础校验，然后给我中文摘要：examples/boat_test/boat.usd`
