#!/usr/bin/env python3
"""Render mesh topology issues with Isaac Sim viewport capture."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


DEBUG_ROOT = "/__OmniAssetDebugTopology"


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}
        self.rank: dict[int, int] = {}
        self.count = 0

    def make_set(self, value: int) -> None:
        if value not in self.parent:
            self.parent[value] = value
            self.rank[value] = 0
            self.count += 1

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left = self.find(left)
        right = self.find(right)
        if left == right:
            return
        if self.rank[left] < self.rank[right]:
            left, right = right, left
        self.parent[right] = left
        if self.rank[left] == self.rank[right]:
            self.rank[left] += 1
        self.count -= 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and render a USD overlay for non-manifold/co-located mesh topology issues.",
    )
    parser.add_argument("asset", type=Path, help="USD asset to inspect and render")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for debug USD and PNG")
    parser.add_argument("--mesh-path", help="Optional mesh prim path to inspect")
    parser.add_argument("--max-problem-faces", type=int, default=3000)
    parser.add_argument("--line-width", type=float, default=0.01)
    parser.add_argument("--coincident-tolerance", type=float, default=1e-6)
    parser.add_argument(
        "--include-weld-faces",
        action="store_true",
        help="Also include faces adjacent to co-located vertices reported by weld-style analysis",
    )
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument(
        "--show-source-asset",
        action="store_true",
        help="Keep the original referenced asset visible behind the topology overlay",
    )
    parser.add_argument("--no-render", action="store_true", help="Only write debug USD and summary")
    return parser.parse_args()


def _as_tuple3(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _transform_point(matrix: Any, point: Any) -> Any:
    from pxr import Gf

    return matrix.Transform(Gf.Vec3d(float(point[0]), float(point[1]), float(point[2])))


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _face_vertex_lists(counts: list[int], indices: list[int]) -> list[list[int]]:
    faces: list[list[int]] = []
    cursor = 0
    for count in counts:
        face = indices[cursor : cursor + count]
        cursor += count
        if len(face) == count and count >= 3:
            faces.append(face)
    return faces


def _quantize(point: Any, tolerance: float) -> tuple[int, int, int]:
    tolerance = max(tolerance, 1e-12)
    return (
        int(round(float(point[0]) / tolerance)),
        int(round(float(point[1]) / tolerance)),
        int(round(float(point[2]) / tolerance)),
    )


def analyze_mesh(
    stage: Any,
    mesh_prim: Any,
    tolerance: float,
    max_problem_faces: int,
    include_weld_faces: bool,
) -> dict[str, Any]:
    from pxr import UsdGeom

    mesh = UsdGeom.Mesh(mesh_prim)
    points = list(mesh.GetPointsAttr().Get() or [])
    counts = [int(item) for item in (mesh.GetFaceVertexCountsAttr().Get() or [])]
    indices = [int(item) for item in (mesh.GetFaceVertexIndicesAttr().Get() or [])]
    faces = _face_vertex_lists(counts, indices)

    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    vertex_faces: dict[int, set[int]] = defaultdict(set)
    for face_index, face in enumerate(faces):
        for vertex_index in face:
            vertex_faces[vertex_index].add(face_index)
        for i, vertex_index in enumerate(face):
            edge_faces[_edge_key(vertex_index, face[(i + 1) % len(face)])].append(face_index)

    non_manifold_edges = {edge: used_by for edge, used_by in edge_faces.items() if len(used_by) > 2}

    vertex_components = [_DisjointSet() for _ in range(len(points))]
    for face_index, face in enumerate(faces):
        for vertex_index in face:
            vertex_components[vertex_index].make_set(face_index)
    for (left, right), used_by in edge_faces.items():
        if len(used_by) == 2:
            vertex_components[left].union(used_by[0], used_by[1])
            vertex_components[right].union(used_by[0], used_by[1])
    non_manifold_vertices = sorted(
        index for index, components in enumerate(vertex_components) if components.count > 1
    )

    buckets: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for index, point in enumerate(points):
        buckets[_quantize(point, tolerance)].append(index)
    coincident_groups = [group for group in buckets.values() if len(group) > 1]
    coincident_vertices = sorted({index for group in coincident_groups for index in group})

    manifold_problem_faces = set()
    for used_by in non_manifold_edges.values():
        manifold_problem_faces.update(used_by)
    for vertex_index in non_manifold_vertices:
        manifold_problem_faces.update(vertex_faces.get(vertex_index, set()))

    problem_faces = set(manifold_problem_faces)
    for vertex_index in coincident_vertices:
        if include_weld_faces:
            problem_faces.update(vertex_faces.get(vertex_index, set()))

    sorted_problem_faces = sorted(problem_faces)
    truncated = len(sorted_problem_faces) > max_problem_faces
    selected_faces = sorted_problem_faces[:max_problem_faces]

    xform_cache = UsdGeom.XformCache()
    local_to_world = xform_cache.GetLocalToWorldTransform(mesh_prim)
    world_points = [_transform_point(local_to_world, point) for point in points]

    return {
        "mesh_path": str(mesh_prim.GetPath()),
        "point_count": len(points),
        "face_count": len(faces),
        "edge_count": len(edge_faces),
        "non_manifold_edge_count": len(non_manifold_edges),
        "non_manifold_vertex_count": len(non_manifold_vertices),
        "coincident_group_count": len(coincident_groups),
        "coincident_vertex_count": len(coincident_vertices),
        "problem_face_count": len(sorted_problem_faces),
        "manifold_problem_face_count": len(manifold_problem_faces),
        "include_weld_faces": include_weld_faces,
        "rendered_problem_face_count": len(selected_faces),
        "problem_faces_truncated": truncated,
        "non_manifold_vertices_sample": non_manifold_vertices[:50],
        "coincident_vertices_sample": coincident_vertices[:50],
        "faces": faces,
        "selected_faces": selected_faces,
        "world_points": world_points,
    }


def choose_meshes(stage: Any, mesh_path: str | None) -> list[Any]:
    from pxr import Sdf, UsdGeom

    if mesh_path:
        prim = stage.GetPrimAtPath(Sdf.Path(mesh_path))
        if not prim or not prim.IsA(UsdGeom.Mesh):
            raise ValueError(f"Mesh prim not found: {mesh_path}")
        return [prim]
    return [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]


def _range_from_points(points: list[Any]) -> Any:
    from pxr import Gf

    bbox = Gf.Range3d()
    for point in points:
        bbox.UnionWith(Gf.Vec3d(point[0], point[1], point[2]))
    return bbox


def _line_width(bbox: Any, requested: float) -> float:
    if requested > 0:
        return requested
    size = bbox.GetSize()
    diagonal = math.sqrt(float(size[0]) ** 2 + float(size[1]) ** 2 + float(size[2]) ** 2)
    return max(diagonal * 0.0025, 0.002)


def _debug_name(path: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in path.strip("/")) or "mesh"


def _bind_debug_material(stage: Any, prim: Any, material_path: str, color: tuple[float, float, float]) -> None:
    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(stage, Sdf.Path(material_path))
    shader = UsdShade.Shader.Define(stage, Sdf.Path(material_path).AppendChild("PreviewSurface"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)


def add_overlay(debug_stage: Any, analyses: list[dict[str, Any]], requested_line_width: float) -> dict[str, Any]:
    from pxr import Gf, Sdf, UsdGeom, Vt

    root = UsdGeom.Xform.Define(debug_stage, DEBUG_ROOT)
    all_problem_points: list[Any] = []
    overlay_mesh_count = 0
    overlay_curve_count = 0

    for analysis in analyses:
        faces = analysis["faces"]
        selected_faces = analysis["selected_faces"]
        world_points = analysis["world_points"]
        if not selected_faces:
            continue

        used_vertices = sorted({vertex for face_index in selected_faces for vertex in faces[face_index]})
        vertex_remap = {old: new for new, old in enumerate(used_vertices)}
        overlay_points = [world_points[index] for index in used_vertices]
        overlay_counts = [len(faces[face_index]) for face_index in selected_faces]
        overlay_indices = [
            vertex_remap[vertex]
            for face_index in selected_faces
            for vertex in faces[face_index]
        ]
        all_problem_points.extend(overlay_points)

        name = _debug_name(analysis["mesh_path"])
        mesh_path = Sdf.Path(DEBUG_ROOT).AppendChild(f"{name}_problem_faces")
        mesh = UsdGeom.Mesh.Define(debug_stage, mesh_path)
        mesh.CreatePointsAttr(overlay_points)
        mesh.CreateFaceVertexCountsAttr(overlay_counts)
        mesh.CreateFaceVertexIndicesAttr(overlay_indices)
        mesh.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(1.0, 0.05, 0.02)]))
        mesh.CreateDisplayOpacityAttr(Vt.FloatArray([0.85]))
        _bind_debug_material(debug_stage, mesh.GetPrim(), f"{DEBUG_ROOT}/RedIssueFaceMaterial", (1.0, 0.02, 0.0))
        overlay_mesh_count += 1

        line_points = []
        curve_counts = []
        seen_edges = set()
        for face_index in selected_faces:
            face = faces[face_index]
            for i, vertex in enumerate(face):
                edge = _edge_key(vertex, face[(i + 1) % len(face)])
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                line_points.extend([world_points[edge[0]], world_points[edge[1]]])
                curve_counts.append(2)

        bbox = _range_from_points(line_points or overlay_points)
        curves_path = Sdf.Path(DEBUG_ROOT).AppendChild(f"{name}_wire_edges")
        curves = UsdGeom.BasisCurves.Define(debug_stage, curves_path)
        curves.CreateTypeAttr("linear")
        curves.CreateCurveVertexCountsAttr(curve_counts)
        curves.CreatePointsAttr(line_points)
        curves.CreateWidthsAttr([_line_width(bbox, requested_line_width)])
        curves.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(1.0, 0.0, 0.0)]))
        _bind_debug_material(debug_stage, curves.GetPrim(), f"{DEBUG_ROOT}/RedIssueWireMaterial", (1.0, 0.0, 0.0))
        overlay_curve_count += 1

    full_bbox = _range_from_points(all_problem_points)
    return {
        "debug_root": str(root.GetPath()),
        "overlay_mesh_count": overlay_mesh_count,
        "overlay_curve_count": overlay_curve_count,
        "problem_bbox_min": _as_tuple3(full_bbox.GetMin()) if not full_bbox.IsEmpty() else None,
        "problem_bbox_max": _as_tuple3(full_bbox.GetMax()) if not full_bbox.IsEmpty() else None,
    }


def build_debug_stage(
    asset: Path,
    debug_usd: Path,
    analyses: list[dict[str, Any]],
    line_width: float,
    show_source_asset: bool,
) -> dict[str, Any]:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

    debug_stage = Usd.Stage.CreateNew(str(debug_usd))
    UsdGeom.SetStageUpAxis(debug_stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(debug_stage, 0.01)

    asset_root = UsdGeom.Xform.Define(debug_stage, "/World/Asset")
    reference_path = Path(asset).resolve()
    try:
        reference_value = reference_path.relative_to(debug_usd.parent.resolve())
    except ValueError:
        reference_value = reference_path
    asset_root.GetPrim().GetReferences().AddReference(str(reference_value))
    if not show_source_asset:
        asset_root.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)

    dome = UsdLux.DomeLight.Define(debug_stage, "/World/DebugDomeLight")
    dome.CreateIntensityAttr(800.0)
    dome.CreateColorAttr(Gf.Vec3f(1.0, 1.0, 1.0))
    distant = UsdLux.DistantLight.Define(debug_stage, "/World/DebugKeyLight")
    distant.CreateIntensityAttr(2500.0)
    distant.CreateAngleAttr(0.4)

    overlay = add_overlay(debug_stage, analyses, line_width)
    debug_stage.SetDefaultPrim(asset_root.GetPrim())
    debug_stage.GetRootLayer().Save()
    return overlay


def add_camera(stage: Any, bbox_min: tuple[float, float, float] | None, bbox_max: tuple[float, float, float] | None) -> str:
    from pxr import Gf, Sdf, UsdGeom

    if bbox_min is None or bbox_max is None:
        center = Gf.Vec3d(0.0, 0.0, 0.0)
        radius = 100.0
    else:
        minimum = Gf.Vec3d(*bbox_min)
        maximum = Gf.Vec3d(*bbox_max)
        center = (minimum + maximum) * 0.5
        size = maximum - minimum
        radius = max(math.sqrt(size[0] ** 2 + size[1] ** 2 + size[2] ** 2), 1.0)

    eye = center + Gf.Vec3d(radius * 1.7, -radius * 2.1, radius * 1.35)
    direction = (center - eye).GetNormalized()
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    right = Gf.Cross(direction, up).GetNormalized()
    true_up = Gf.Cross(right, direction).GetNormalized()
    matrix = Gf.Matrix4d(
        right[0], right[1], right[2], 0.0,
        true_up[0], true_up[1], true_up[2], 0.0,
        -direction[0], -direction[1], -direction[2], 0.0,
        eye[0], eye[1], eye[2], 1.0,
    )

    camera = UsdGeom.Camera.Define(stage, Sdf.Path("/World/DebugCamera"))
    camera.AddTransformOp().Set(matrix)
    camera.CreateFocalLengthAttr(35.0)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.1, float(radius * 20.0)))
    return str(camera.GetPath())


def render_png(
    debug_usd: Path,
    png_path: Path,
    bbox_min: tuple[float, float, float] | None,
    bbox_max: tuple[float, float, float] | None,
    width: int,
    height: int,
    app: Any | None = None,
) -> list[str]:
    owns_app = app is None
    if app is None:
        from isaacsim import SimulationApp  # type: ignore

        app = SimulationApp({"headless": True, "width": width, "height": height})
    errors: list[str] = []
    try:
        import omni.usd  # type: ignore
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport  # type: ignore

        context = omni.usd.get_context()
        context.open_stage(str(debug_usd))
        for _ in range(20):
            app.update()

        stage = context.get_stage()
        camera_path = add_camera(stage, bbox_min, bbox_max)
        viewport = get_active_viewport()
        if viewport is None:
            errors.append("No active viewport is available.")
            return errors
        viewport.camera_path = camera_path
        for _ in range(20):
            app.update()

        capture_viewport_to_file(viewport, str(png_path))
        for _ in range(30):
            app.update()
        if not png_path.exists():
            errors.append(f"Capture requested but file was not written: {png_path}")
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim runtime
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        if owns_app:
            app.close()
    return errors


def build_markdown_report(payload: dict[str, Any]) -> str:
    meshes = payload.get("meshes") or []
    overlay = payload.get("overlay") or {}
    first_mesh = meshes[0] if meshes else {}
    png = payload.get("png")
    debug_usd = payload.get("debug_usd")
    errors = payload.get("render_errors") or []
    truncated = bool(first_mesh.get("problem_faces_truncated"))
    include_weld = bool(first_mesh.get("include_weld_faces"))

    lines = [
        "# Mesh Topology Debug Render",
        "",
        f"Asset: `{payload.get('asset')}`",
        f"Mesh: `{first_mesh.get('mesh_path', 'N/A')}`",
        f"Rendered image: `{png or 'not written'}`",
        f"Debug USD: `{debug_usd}`",
        "",
        "## Summary",
        "",
        f"- Non-manifold vertices: `{first_mesh.get('non_manifold_vertex_count', 0)}`",
        f"- Non-manifold edges: `{first_mesh.get('non_manifold_edge_count', 0)}`",
        f"- Problem faces related to manifold issues: `{first_mesh.get('manifold_problem_face_count', 0)}`",
        f"- Rendered problem faces: `{first_mesh.get('rendered_problem_face_count', 0)}`",
        f"- Problem faces truncated: `{'yes' if truncated else 'no'}`",
        f"- Co-located vertex groups: `{first_mesh.get('coincident_group_count', 0)}`",
        f"- Co-located vertices: `{first_mesh.get('coincident_vertex_count', 0)}`",
        f"- Weld faces included in render: `{'yes' if include_weld else 'no'}`",
        "",
        "## What The Image Shows",
        "",
        (
            "The red overlay marks faces and edges adjacent to vertices that match the "
            "`ManifoldChecker` non-manifold definition. The source asset is hidden by default "
            "so the topology issue overlay is readable."
        ),
        "",
        "This render is diagnostic evidence only. It does not modify the original asset.",
        "",
        "## How To Interpret This",
        "",
        (
            "A non-manifold vertex means the faces around that vertex do not form one clean, "
            "connected surface fan. In practice this often comes from duplicated shells, "
            "touching parts, internal faces, bad welds, or topology that only meets at a point."
        ),
        "",
        (
            "This asset has no non-manifold edges in the validator-compatible analysis, but it "
            "does have non-manifold vertices. That points more toward disconnected face fans "
            "around shared vertices than toward edges shared by three or more faces."
        ),
        "",
        "## Suggested Fix",
        "",
        "- Open the mesh in a DCC tool and inspect the red regions shown in the render.",
        "- Merge/weld duplicate points carefully, then re-check whether separate shells were accidentally joined at points.",
        "- Remove internal, overlapping, or duplicate faces around the marked rings and strips.",
        "- Re-export the USD and rerun the `collidable` profile validation.",
        "",
        "## Artifacts",
        "",
        f"- Debug overlay root: `{overlay.get('debug_root')}`",
        f"- Problem bbox min: `{overlay.get('problem_bbox_min')}`",
        f"- Problem bbox max: `{overlay.get('problem_bbox_max')}`",
        f"- Overlay mesh count: `{overlay.get('overlay_mesh_count')}`",
        f"- Overlay curve count: `{overlay.get('overlay_curve_count')}`",
        "",
    ]

    samples = first_mesh.get("non_manifold_vertices_sample") or []
    if samples:
        lines.extend(
            [
                "## Vertex Samples",
                "",
                "First non-manifold vertex indices:",
                "",
                f"`{', '.join(str(item) for item in samples[:50])}`",
                "",
            ]
        )

    if errors:
        lines.extend(["## Render Errors", ""])
        lines.extend(f"- `{error}`" for error in errors)
        lines.append("")

    return "\n".join(lines)


def build_chinese_markdown_report(payload: dict[str, Any]) -> str:
    meshes = payload.get("meshes") or []
    overlay = payload.get("overlay") or {}
    first_mesh = meshes[0] if meshes else {}
    png = payload.get("png")
    debug_usd = payload.get("debug_usd")
    errors = payload.get("render_errors") or []
    truncated = bool(first_mesh.get("problem_faces_truncated"))
    include_weld = bool(first_mesh.get("include_weld_faces"))

    lines = [
        "# Mesh 拓扑问题可视化报告",
        "",
        f"资产：`{payload.get('asset')}`",
        f"Mesh：`{first_mesh.get('mesh_path', 'N/A')}`",
        f"渲染图片：`{png or '未写出'}`",
        f"Debug USD：`{debug_usd}`",
        "",
        "## 摘要",
        "",
        f"- Non-manifold 顶点数：`{first_mesh.get('non_manifold_vertex_count', 0)}`",
        f"- Non-manifold 边数：`{first_mesh.get('non_manifold_edge_count', 0)}`",
        f"- 与 manifold 问题相关的问题面数：`{first_mesh.get('manifold_problem_face_count', 0)}`",
        f"- 实际渲染的问题面数：`{first_mesh.get('rendered_problem_face_count', 0)}`",
        f"- 问题面是否被截断：`{'是' if truncated else '否'}`",
        f"- 重合点分组数：`{first_mesh.get('coincident_group_count', 0)}`",
        f"- 重合顶点数：`{first_mesh.get('coincident_vertex_count', 0)}`",
        f"- 本次渲染是否包含 weld 问题面：`{'是' if include_weld else '否'}`",
        "",
        "## 图片里显示的是什么",
        "",
        (
            "红色部分是根据 `ManifoldChecker` 的定义反推出的问题区域：也就是 non-manifold "
            "顶点周围相关的面和边。默认隐藏了原始资产，只显示红色问题面/线框，这样更容易看清问题分布。"
        ),
        "",
        "这个渲染只用于诊断和人工复核，不会修改原始资产。",
        "",
        "## 这个错误怎么理解",
        "",
        (
            "non-manifold 顶点表示：某个顶点周围的面没有形成一个干净、连续的表面扇区。"
            "常见表现是多个面片或多个壳体只在一个点上接触，或者重复点、错误焊接、内部面、重叠面导致拓扑连接异常。"
        ),
        "",
        (
            "这次分析里 `non_manifold_edge_count` 是 0，但 `non_manifold_vertex_count` 是 709。"
            "这说明问题主要不是“一条边被三个或更多面共享”，而是“顶点周围的面扇区不连续”。"
            "所以图片上看到的是分散的红色短线和小片段，而不是一整块连续红色区域。"
        ),
        "",
        "## 对后续流程的影响",
        "",
        "- 碰撞体生成可能不稳定。",
        "- 物理接触可能出现穿透、抖动或异常接触。",
        "- mesh 简化、重拓扑、布尔处理可能失败。",
        "- 作为可碰撞或可移动资产时，不建议直接进入后续物理流程。",
        "",
        "## 建议修复方式",
        "",
        "- 在 Blender、Maya、Houdini 等 DCC 工具里打开 mesh，并定位图片里红色区域。",
        "- 先做小阈值的 merge by distance / weld，避免用过大的全局阈值把本来分开的结构错误合并。",
        "- 检查红色区域附近是否有重复面、内部面、重叠壳体、只在点上接触的几何片。",
        "- 清理后重新导出 USD，再运行 `collidable` profile 复测。",
        "",
        "## 产物",
        "",
        f"- Debug overlay 根路径：`{overlay.get('debug_root')}`",
        f"- 问题区域 bbox min：`{overlay.get('problem_bbox_min')}`",
        f"- 问题区域 bbox max：`{overlay.get('problem_bbox_max')}`",
        f"- Overlay mesh 数量：`{overlay.get('overlay_mesh_count')}`",
        f"- Overlay curve 数量：`{overlay.get('overlay_curve_count')}`",
        "",
    ]

    samples = first_mesh.get("non_manifold_vertices_sample") or []
    if samples:
        lines.extend(
            [
                "## 顶点样本",
                "",
                "前 50 个 non-manifold 顶点 index：",
                "",
                f"`{', '.join(str(item) for item in samples[:50])}`",
                "",
            ]
        )

    if errors:
        lines.extend(["## 渲染错误", ""])
        lines.extend(f"- `{error}`" for error in errors)
        lines.append("")

    return "\n".join(lines)


def _load_usd_module(width: int, height: int) -> tuple[Any, Any | None]:
    try:
        from pxr import Usd

        return Usd, None
    except ModuleNotFoundError:
        from isaacsim import SimulationApp  # type: ignore

        app = SimulationApp({"headless": True, "width": width, "height": height})
        from pxr import Usd

        return Usd, app


def main() -> int:
    args = parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    asset = args.asset.resolve()
    debug_usd = args.out / f"{asset.stem}.topology_debug.usda"
    png_path = args.out / f"{asset.stem}.topology_wire.png"
    summary_path = args.out / "topology_render_summary.json"
    summary_md_path = args.out / "topology_render_summary.md"
    summary_zh_md_path = args.out / "topology_render_summary.zh.md"

    app = None
    try:
        Usd, app = _load_usd_module(args.width, args.height)

        stage = Usd.Stage.Open(str(asset))
        if stage is None:
            raise RuntimeError(f"Could not open asset: {asset}")

        analyses = [
            analyze_mesh(stage, prim, args.coincident_tolerance, args.max_problem_faces, args.include_weld_faces)
            for prim in choose_meshes(stage, args.mesh_path)
        ]
        analyses_with_issues = [
            analysis
            for analysis in analyses
            if analysis["non_manifold_edge_count"] or analysis["non_manifold_vertex_count"]
        ]
        overlay = build_debug_stage(
            asset,
            debug_usd,
            analyses_with_issues,
            args.line_width,
            show_source_asset=args.show_source_asset,
        )

        render_errors: list[str] = []
        if not args.no_render:
            render_errors = render_png(
                debug_usd,
                png_path,
                overlay["problem_bbox_min"],
                overlay["problem_bbox_max"],
                args.width,
                args.height,
                app=app,
            )
    finally:
        if app is not None:
            app.close()

    public_analyses = []
    for analysis in analyses:
        public_analyses.append(
            {
                key: value
                for key, value in analysis.items()
                if key not in {"faces", "selected_faces", "world_points"}
            }
        )

    payload = {
        "asset": str(asset),
        "debug_usd": str(debug_usd),
        "png": str(png_path) if png_path.exists() else None,
        "render_errors": render_errors,
        "overlay": overlay,
        "meshes": public_analyses,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with summary_md_path.open("w", encoding="utf-8") as handle:
        handle.write(build_markdown_report(payload))
        handle.write("\n")
    with summary_zh_md_path.open("w", encoding="utf-8") as handle:
        handle.write(build_chinese_markdown_report(payload))
        handle.write("\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not render_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
