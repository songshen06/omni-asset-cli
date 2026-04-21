# 自然语言示例 / Natural-Language Examples

## 通用检查 / General Validation

- `检查这个 USD`
- `帮我看这个资产有没有明显问题`
- `check this USD asset`
- `validate this asset`

## 引用与贴图 / References and Textures

- `检查引用和贴图`
- `帮我确认依赖是否完整`
- `check references and textures`
- `verify external dependencies`

## 结构与 Isaac Sim / Structure and Isaac Sim

- `检查这个资产的 Isaac Sim 结构`
- `帮我看层级和组件语义是否合理`
- `check Isaac Sim structure`
- `validate hierarchy and component semantics`

## Mesh / Geometry

- `检查 topology`
- `帮我看法线和 mesh 质量`
- `check topology`
- `validate normals and mesh quality`

## 业务口吻 / Business-Language Prompts

- `这个资产能不能先当静态资产交付`
- `这个资产适不适合做碰撞`
- `这个机器人资产适不适合抓取和移动`
- `can this be used as a static asset`
- `is this asset good for collision`
- `is this robot asset suitable for grasping and moving`

## 示例命令 / Example Commands

```bash
omni-asset-cli map examples/boat_test/boat.usd "检查引用和贴图"
omni-asset-cli map examples/boat_test/boat.usd "check Isaac Sim structure"
omni-asset-cli validate-from-prompt examples/boat_test/boat.usd "帮我按可碰撞资产场景检查"
omni-asset-cli validate-from-prompt examples/boat_test/boat.usd "validate this as a movable asset"
```

