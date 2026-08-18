#!/usr/bin/env python3
"""Minimal runtime physics harness for dynamic-box-vs-static-asset hit tests."""

from __future__ import annotations

import csv
import json
import platform
import shutil
import subprocess
import tempfile
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics
except ImportError:  # Allows host-side Docker dispatch without local USD Python packages.
    Gf = None  # type: ignore[assignment]
    Sdf = None  # type: ignore[assignment]
    Usd = None  # type: ignore[assignment]
    UsdGeom = None  # type: ignore[assignment]
    UsdPhysics = None  # type: ignore[assignment]

try:
    from pxr import PhysicsSchemaTools, PhysxSchema
except ImportError:
    PhysicsSchemaTools = None  # type: ignore[assignment]
    PhysxSchema = None  # type: ignore[assignment]


def _ensure_pxr_loaded() -> None:
    global Gf, Sdf, Usd, UsdGeom, UsdPhysics, PhysicsSchemaTools, PhysxSchema
    if any(module is None for module in (Gf, Sdf, Usd, UsdGeom, UsdPhysics)):
        from pxr import Gf as _Gf
        from pxr import Sdf as _Sdf
        from pxr import Usd as _Usd
        from pxr import UsdGeom as _UsdGeom
        from pxr import UsdPhysics as _UsdPhysics

        Gf = _Gf
        Sdf = _Sdf
        Usd = _Usd
        UsdGeom = _UsdGeom
        UsdPhysics = _UsdPhysics

    if PhysicsSchemaTools is None or PhysxSchema is None:
        try:
            from pxr import PhysicsSchemaTools as _PhysicsSchemaTools
            from pxr import PhysxSchema as _PhysxSchema

            PhysicsSchemaTools = _PhysicsSchemaTools
            PhysxSchema = _PhysxSchema
        except ImportError:
            PhysicsSchemaTools = None  # type: ignore[assignment]
            PhysxSchema = None  # type: ignore[assignment]


DEBUG_PHYSICS_BBOX_ROOT = "/__OmniAssetDebugPhysicsBBox"
RENDER_CAMERA_ROOT = "/World/__OmniAssetRenderCameras"
RENDER_CAMERA_PRESETS = {"active", "front", "back", "left", "right", "side", "top", "iso"}


def _debug_prim_name(value: str) -> str:
    name = "".join(char if char.isalnum() or char == "_" else "_" for char in value.strip("/"))
    name = name.strip("_") or "prim"
    if name[0].isdigit():
        name = "_" + name
    return name


def _bbox_edge_points(minimum: Any, maximum: Any) -> list[Any]:
    _ensure_pxr_loaded()
    min_x, min_y, min_z = [float(value) for value in minimum]
    max_x, max_y, max_z = [float(value) for value in maximum]
    corners = [
        Gf.Vec3f(min_x, min_y, min_z),
        Gf.Vec3f(max_x, min_y, min_z),
        Gf.Vec3f(max_x, max_y, min_z),
        Gf.Vec3f(min_x, max_y, min_z),
        Gf.Vec3f(min_x, min_y, max_z),
        Gf.Vec3f(max_x, min_y, max_z),
        Gf.Vec3f(max_x, max_y, max_z),
        Gf.Vec3f(min_x, max_y, max_z),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    points: list[Any] = []
    for start, end in edges:
        points.extend([corners[start], corners[end]])
    return points


def _bbox_line_width(stage_range: Any, requested: float) -> float:
    if requested > 0:
        return requested
    if stage_range is None or stage_range.IsEmpty():
        return 0.5
    size = stage_range.GetSize()
    diagonal = (float(size[0]) ** 2 + float(size[1]) ** 2 + float(size[2]) ** 2) ** 0.5
    return max(diagonal * 0.004, 0.01)


def _define_bbox_curve(
    stage: Any,
    path: Any,
    bbox_range: Any,
    width: float,
    *,
    color: tuple[float, float, float] = (1.0, 0.12, 0.05),
) -> None:
    _ensure_pxr_loaded()
    curves = UsdGeom.BasisCurves.Define(stage, path)
    curves.CreateTypeAttr(UsdGeom.Tokens.linear)
    curves.CreateWrapAttr(UsdGeom.Tokens.nonperiodic)
    curves.CreateCurveVertexCountsAttr([2] * 12)
    curves.CreatePointsAttr(_bbox_edge_points(bbox_range.GetMin(), bbox_range.GetMax()))
    curves.CreateWidthsAttr([float(width)])
    gprim = UsdGeom.Gprim(curves.GetPrim())
    gprim.CreateDisplayColorAttr([Gf.Vec3f(*color)])


def _debug_bbox_material(
    stage: Any,
    path: Any,
    *,
    color: tuple[float, float, float],
    opacity: float,
) -> Any:
    _ensure_pxr_loaded()
    from pxr import UsdShade

    material = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path.AppendChild("PreviewSurface"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(float(opacity))
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _define_bbox_solid(
    stage: Any,
    path: Any,
    bbox_range: Any,
    *,
    material: Any,
    opacity: float,
) -> None:
    _ensure_pxr_loaded()
    from pxr import UsdShade

    minimum = bbox_range.GetMin()
    maximum = bbox_range.GetMax()
    size = bbox_range.GetSize()
    if min(float(size[0]), float(size[1]), float(size[2])) <= 0.0:
        return
    center = (minimum + maximum) * 0.5
    cube = UsdGeom.Cube.Define(stage, path)
    cube.CreateSizeAttr(1.0)
    _clear_xform_ops(cube.GetPrim())
    xformable = UsdGeom.Xformable(cube.GetPrim())
    xformable.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble).Set(center)
    xformable.AddScaleOp(UsdGeom.XformOp.PrecisionFloat).Set(Gf.Vec3f(float(size[0]), float(size[1]), float(size[2])))
    gprim = UsdGeom.Gprim(cube.GetPrim())
    gprim.CreateDisplayOpacityAttr([float(opacity)])
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(material)


def add_physics_bbox_session_overlay(
    stage: Any,
    *,
    collider_paths: list[str],
    fallback_prim_path: str | None,
    fallback_default_prim: bool,
    width: float,
) -> list[str]:
    _ensure_pxr_loaded()
    target_paths = [path for path in collider_paths if path and stage.GetPrimAtPath(path)]
    if not target_paths and fallback_default_prim and fallback_prim_path and stage.GetPrimAtPath(fallback_prim_path):
        target_paths = [fallback_prim_path]
    if not target_paths:
        return []

    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    line_width = _bbox_line_width(
        bbox_cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange(),
        width,
    )
    debug_root = Sdf.Path(DEBUG_PHYSICS_BBOX_ROOT)
    old_target = stage.GetEditTarget()
    stage.SetEditTarget(stage.GetSessionLayer())
    try:
        if stage.GetPrimAtPath(debug_root):
            stage.RemovePrim(debug_root)
        UsdGeom.Xform.Define(stage, debug_root)
        written: list[str] = []
        for index, target_path in enumerate(target_paths):
            prim = stage.GetPrimAtPath(target_path)
            bbox_range = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
            if bbox_range.IsEmpty():
                continue
            name = f"bbox_{index:03d}_{_debug_prim_name(target_path)}"
            curve_path = debug_root.AppendChild(f"{name}_wire")
            _define_bbox_curve(stage, curve_path, bbox_range, line_width)
            written.append(target_path)
        return written
    finally:
        stage.SetEditTarget(old_target)


def _collect_collision_paths_under(stage: Any, root_path: str) -> list[str]:
    _ensure_pxr_loaded()
    root = stage.GetPrimAtPath(root_path)
    if not root:
        return []
    paths: list[str] = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if not path.startswith(root_path.rstrip("/") + "/") and path != root_path:
            continue
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            paths.append(path)
    return paths


def add_dynamic_asset_bbox_session_overlay(
    stage: Any,
    *,
    asset_root_path: str,
    width: float,
) -> list[str]:
    _ensure_pxr_loaded()
    asset_root = stage.GetPrimAtPath(asset_root_path)
    if not asset_root:
        return []

    collider_paths = _collect_collision_paths_under(stage, asset_root_path)
    if not collider_paths:
        return []

    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    stage_range = bbox_cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
    line_width = _bbox_line_width(stage_range, width)
    root_path = Sdf.Path(asset_root_path).AppendChild("__OmniAssetDebugPhysicsBBox")
    old_target = stage.GetEditTarget()
    stage.SetEditTarget(stage.GetSessionLayer())
    try:
        if stage.GetPrimAtPath(root_path):
            stage.RemovePrim(root_path)
        UsdGeom.Xform.Define(stage, root_path)
        material = _debug_bbox_material(
            stage,
            root_path.AppendChild("Looks").AppendChild("DynamicAssetBBox"),
            color=(0.1, 0.55, 1.0),
            opacity=0.24,
        )
        written: list[str] = []
        for index, collider_path in enumerate(collider_paths):
            prim = stage.GetPrimAtPath(collider_path)
            bbox_range = bbox_cache.ComputeRelativeBound(prim, asset_root).ComputeAlignedRange()
            if bbox_range.IsEmpty():
                continue
            name = f"bbox_{index:03d}_{_debug_prim_name(collider_path)}"
            solid_path = root_path.AppendChild(f"{name}_solid")
            curve_path = root_path.AppendChild(f"{name}_wire")
            _define_bbox_solid(stage, solid_path, bbox_range, material=material, opacity=0.24)
            _define_bbox_curve(stage, curve_path, bbox_range, line_width, color=(0.1, 0.55, 1.0))
            written.append(collider_path)
        return written
    finally:
        stage.SetEditTarget(old_target)


def clear_physics_bbox_session_overlay(stage: Any) -> None:
    _ensure_pxr_loaded()
    debug_root = Sdf.Path(DEBUG_PHYSICS_BBOX_ROOT)
    old_target = stage.GetEditTarget()
    stage.SetEditTarget(stage.GetSessionLayer())
    try:
        if stage.GetPrimAtPath(debug_root):
            stage.RemovePrim(debug_root)
    finally:
        stage.SetEditTarget(old_target)


@dataclass
class RuntimeConfig:
    asset: Path
    out_dir: Path
    template_scene: Path | None = None
    replace_prim: str | None = "/World/roomScene/colliders/table"
    placement_mode: str = "auto"
    hit_mode: str = "side-hit"
    size_policy: str = "template-fit"
    asset_rotation_y_deg: float = 0.0
    asset_rotation_z_deg: float = 0.0
    frames: int = 240
    fps: float = 60.0
    headless: bool = True
    runtime_docker_image: str | None = None
    runtime_docker_container: str | None = None
    runtime_docker_preflight: str = "restart"
    docker_workspace: str = "/workspace/omni-asset-cli"
    docker_python: str = "/isaac-sim/python.sh"
    render_frames: bool = False
    render_every_n_frames: int = 1
    render_warmup_updates: int = 2
    render_camera_presets: list[str] = field(default_factory=list)
    render_backend: str = "replicator"
    render_width: int = 1280
    render_height: int = 720
    render_rt_subframes: int = 4
    render_wait_updates: int = 20
    render_video: bool = False
    render_video_fps: float | None = None
    render_video_crf: int = 23
    render_physics_bboxes: bool = False
    render_physics_bbox_fallback_default_prim: bool = False
    render_physics_bbox_width: float = 0.0


@dataclass
class TimelineSample:
    frame: int
    time: float
    box_x: float
    box_y: float
    box_z: float
    vel_x: float
    vel_y: float
    vel_z: float


@dataclass
class ContactEventSample:
    frame: int
    event_type: int
    actor0: str
    actor1: str
    collider0: str
    collider1: str
    num_contacts: int
    target_kind: str


@dataclass
class SceneBuildResult:
    stage_path: Path
    template_scene_path: Path | None
    test_type: str
    asset_prim_path: str
    replaced_prim_path: str | None
    box_prim_path: str
    ground_prim_path: str
    collider_prim_paths: list[str]
    box_initial_position: tuple[float, float, float]
    box_initial_velocity: tuple[float, float, float]
    box_size: float | None
    hit_mode: str
    size_policy: str
    asset_rotation_y_deg: float
    asset_rotation_z_deg: float
    drop_target_xy: tuple[float, float] | None
    asset_bbox_preserved: bool
    asset_unit_scale: float
    fit_mode: str | None
    fit_scale: float | None
    replaced_bbox_min: tuple[float, float, float] | None
    replaced_bbox_max: tuple[float, float, float] | None
    asset_bbox_before_align_min: tuple[float, float, float]
    asset_bbox_before_align_max: tuple[float, float, float]
    asset_bbox_min: tuple[float, float, float]
    asset_bbox_max: tuple[float, float, float]


@dataclass
class RenderCaptureResult:
    frame_count: int
    output_dir: Path | None
    files: list[str]
    errors: list[str]


def default_out_dir(asset_path: Path) -> Path:
    return Path("out") / f"{asset_path.stem}_physics_hit"


def _host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    return "linux"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _as_tuple(vec: Gf.Vec3d | Gf.Vec3f) -> tuple[float, float, float]:
    return (float(vec[0]), float(vec[1]), float(vec[2]))


def _append_translate_op(xformable: UsdGeom.Xformable, value: Gf.Vec3d) -> None:
    for op in xformable.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:translate":
            op.Set(value)
            return
    op = xformable.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)
    op.Set(value)


def _append_scale_op(xformable: UsdGeom.Xformable, value: Gf.Vec3f) -> None:
    for op in xformable.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:scale":
            op.Set(value)
            return
    op = xformable.AddScaleOp(UsdGeom.XformOp.PrecisionFloat)
    op.Set(value)


def _clear_xform_ops(prim: Usd.Prim) -> None:
    xformable = UsdGeom.Xformable(prim)
    for op in xformable.GetOrderedXformOps():
        prim.RemoveProperty(op.GetOpName())
    xformable.ClearXformOpOrder()


def _read_prim_position(stage: Usd.Stage, prim_path: str) -> tuple[float, float, float]:
    prim = stage.GetPrimAtPath(prim_path)
    xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    transform = xform_cache.GetLocalToWorldTransform(prim)
    return _as_tuple(transform.ExtractTranslation())


def _stage_units_for_meters(stage: Usd.Stage, meters: float) -> float:
    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage)
    if meters_per_unit <= 0:
        meters_per_unit = 1.0
    return meters / meters_per_unit


def _asset_units_to_stage_scale(asset_path: Path, target_stage: Usd.Stage) -> float:
    asset_stage = Usd.Stage.Open(str(asset_path.resolve()))
    if asset_stage is None:
        return 1.0
    asset_meters_per_unit = UsdGeom.GetStageMetersPerUnit(asset_stage)
    target_meters_per_unit = UsdGeom.GetStageMetersPerUnit(target_stage)
    if asset_meters_per_unit <= 0 or target_meters_per_unit <= 0:
        return 1.0
    return float(asset_meters_per_unit / target_meters_per_unit)


def _reference_asset_under(
    stage: Usd.Stage,
    asset_path: Path,
    reference_path: str,
    *,
    rotation_y_deg: float = 0.0,
    rotation_z_deg: float = 0.0,
) -> Usd.Prim:
    wrapper = UsdGeom.Xform.Define(stage, reference_path)
    wrapper_prim = wrapper.GetPrim()
    _clear_xform_ops(wrapper_prim)
    wrapper_xform = UsdGeom.Xformable(wrapper_prim)
    if abs(float(rotation_y_deg)) > 1e-9:
        wrapper_xform.AddRotateYOp(UsdGeom.XformOp.PrecisionFloat).Set(float(rotation_y_deg))
    if abs(float(rotation_z_deg)) > 1e-9:
        wrapper_xform.AddRotateZOp(UsdGeom.XformOp.PrecisionFloat).Set(float(rotation_z_deg))
    unit_scale = _asset_units_to_stage_scale(asset_path, stage)
    if abs(unit_scale - 1.0) > 1e-9:
        _append_scale_op(wrapper_xform, Gf.Vec3f(unit_scale, unit_scale, unit_scale))
    # Keep unit conversion and orientation on a wrapper prim. Authoring them on
    # the referenced prim itself can override the referenced default prim's own
    # xformOps, including SimReady scale authored upstream.
    referenced_asset = UsdGeom.Xform.Define(stage, f"{reference_path}/Asset")
    referenced_prim = referenced_asset.GetPrim()
    referenced_prim.GetReferences().AddReference(str(asset_path.resolve()))
    stage.Load(referenced_prim.GetPath())
    return referenced_prim


def create_base_stage(stage_path: Path, fps: float) -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(stage_path))
    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetTimeCodesPerSecond(fps)
    stage.SetStartTimeCode(0.0)
    stage.SetEndTimeCode(fps)

    scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)
    return stage


def create_ground_plane(stage: Usd.Stage) -> str:
    plane_path = "/World/GroundPlane"
    plane_mesh = UsdGeom.Mesh.Define(stage, plane_path)
    plane_mesh.CreatePointsAttr(
        [
            Gf.Vec3f(-10.0, -10.0, 0.0),
            Gf.Vec3f(10.0, -10.0, 0.0),
            Gf.Vec3f(10.0, 10.0, 0.0),
            Gf.Vec3f(-10.0, 10.0, 0.0),
        ]
    )
    plane_mesh.CreateFaceVertexCountsAttr([4])
    plane_mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
    plane_mesh.CreateExtentAttr([Gf.Vec3f(-10.0, -10.0, 0.0), Gf.Vec3f(10.0, 10.0, 0.0)])
    UsdPhysics.CollisionAPI.Apply(plane_mesh.GetPrim())
    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(plane_mesh.GetPrim())
    mesh_collision.CreateApproximationAttr().Set(UsdPhysics.Tokens.none)
    return plane_path


def create_input_asset_prim(
    stage: Usd.Stage,
    asset_path: Path,
    *,
    rotation_y_deg: float = 0.0,
    rotation_z_deg: float = 0.0,
) -> Usd.Prim:
    asset_root = UsdGeom.Xform.Define(stage, "/World/InputAsset")
    _clear_xform_ops(asset_root.GetPrim())
    _reference_asset_under(
        stage,
        asset_path,
        "/World/InputAsset/ReferencedAsset",
        rotation_y_deg=rotation_y_deg,
        rotation_z_deg=rotation_z_deg,
    )
    return asset_root.GetPrim()


def compute_world_bbox(stage: Usd.Stage, prim: Usd.Prim) -> Gf.Range3d:
    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    bbox = bbox_cache.ComputeWorldBound(prim)
    return bbox.ComputeAlignedRange()


def align_asset_to_ground(stage: Usd.Stage, asset_prim: Usd.Prim) -> Gf.Range3d:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty():
        return initial_range

    bbox_min = initial_range.GetMin()
    bbox_max = initial_range.GetMax()
    center_x = (bbox_min[0] + bbox_max[0]) / 2.0
    center_y = (bbox_min[1] + bbox_max[1]) / 2.0
    translate = Gf.Vec3d(-center_x, -center_y, -bbox_min[2])

    asset_xform = UsdGeom.Xformable(asset_prim)
    _append_translate_op(asset_xform, translate)
    return compute_world_bbox(stage, asset_prim)


def fit_asset_to_replaced_footprint(
    stage: Usd.Stage,
    asset_prim: Usd.Prim,
    replaced_range: Gf.Range3d,
) -> tuple[Gf.Range3d, float]:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty() or replaced_range.IsEmpty():
        return initial_range, 1.0

    asset_min = initial_range.GetMin()
    asset_max = initial_range.GetMax()
    replaced_min = replaced_range.GetMin()
    replaced_max = replaced_range.GetMax()

    asset_span = asset_max - asset_min
    replaced_span = replaced_max - replaced_min
    asset_x = max(float(asset_span[0]), 1e-6)
    asset_y = max(float(asset_span[1]), 1e-6)
    replaced_x = max(float(replaced_span[0]), 1e-6)
    replaced_y = max(float(replaced_span[1]), 1e-6)
    scale = min(replaced_x / asset_x, replaced_y / asset_y)

    asset_center_x = (float(asset_min[0]) + float(asset_max[0])) / 2.0
    asset_center_y = (float(asset_min[1]) + float(asset_max[1])) / 2.0
    replaced_center_x = (float(replaced_min[0]) + float(replaced_max[0])) / 2.0
    replaced_center_y = (float(replaced_min[1]) + float(replaced_max[1])) / 2.0
    replaced_top_z = float(replaced_max[2])

    translate = Gf.Vec3d(
        replaced_center_x - asset_center_x * scale,
        replaced_center_y - asset_center_y * scale,
        replaced_top_z - float(asset_min[2]) * scale,
    )

    asset_xform = UsdGeom.Xformable(asset_prim)
    _clear_xform_ops(asset_prim)
    # USD's common xformOpOrder form is translate then scale, which applies scale before placement.
    _append_translate_op(asset_xform, translate)
    _append_scale_op(asset_xform, Gf.Vec3f(scale, scale, scale))
    return compute_world_bbox(stage, asset_prim), scale


def place_asset_on_replaced_prim_preserving_size(
    stage: Usd.Stage,
    asset_prim: Usd.Prim,
    replaced_range: Gf.Range3d,
) -> Gf.Range3d:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty() or replaced_range.IsEmpty():
        return initial_range

    asset_min = initial_range.GetMin()
    asset_max = initial_range.GetMax()
    replaced_min = replaced_range.GetMin()
    replaced_max = replaced_range.GetMax()

    asset_center_x = (float(asset_min[0]) + float(asset_max[0])) / 2.0
    asset_center_y = (float(asset_min[1]) + float(asset_max[1])) / 2.0
    replaced_center_x = (float(replaced_min[0]) + float(replaced_max[0])) / 2.0
    replaced_center_y = (float(replaced_min[1]) + float(replaced_max[1])) / 2.0
    replaced_top_z = float(replaced_max[2])

    translate = Gf.Vec3d(
        replaced_center_x - asset_center_x,
        replaced_center_y - asset_center_y,
        replaced_top_z - float(asset_min[2]),
    )

    asset_xform = UsdGeom.Xformable(asset_prim)
    _clear_xform_ops(asset_prim)
    _append_translate_op(asset_xform, translate)
    return compute_world_bbox(stage, asset_prim)


def place_asset_on_tabletop_preserving_size(
    stage: Usd.Stage,
    asset_prim: Usd.Prim,
    table_range: Gf.Range3d,
) -> Gf.Range3d:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty() or table_range.IsEmpty():
        return initial_range

    asset_min = initial_range.GetMin()
    asset_max = initial_range.GetMax()
    table_min = table_range.GetMin()
    table_max = table_range.GetMax()

    asset_center_x = (float(asset_min[0]) + float(asset_max[0])) / 2.0
    asset_center_y = (float(asset_min[1]) + float(asset_max[1])) / 2.0
    table_center_x = (float(table_min[0]) + float(table_max[0])) / 2.0
    table_center_y = (float(table_min[1]) + float(table_max[1])) / 2.0
    table_top_z = float(table_max[2])

    translate = Gf.Vec3d(
        table_center_x - asset_center_x,
        table_center_y - asset_center_y,
        table_top_z - float(asset_min[2]),
    )

    asset_xform = UsdGeom.Xformable(asset_prim)
    _clear_xform_ops(asset_prim)
    _append_translate_op(asset_xform, translate)
    return compute_world_bbox(stage, asset_prim)


def place_asset_at_bbox_center(
    stage: Usd.Stage,
    asset_prim: Usd.Prim,
    target_range: Gf.Range3d,
) -> Gf.Range3d:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty() or target_range.IsEmpty():
        return initial_range

    asset_min = initial_range.GetMin()
    asset_max = initial_range.GetMax()
    target_min = target_range.GetMin()
    target_max = target_range.GetMax()
    asset_center = (asset_min + asset_max) * 0.5
    target_center = (target_min + target_max) * 0.5

    asset_xform = UsdGeom.Xformable(asset_prim)
    _clear_xform_ops(asset_prim)
    _append_translate_op(asset_xform, target_center - asset_center)
    return compute_world_bbox(stage, asset_prim)


def fit_asset_to_replaced_bbox(
    stage: Usd.Stage,
    asset_prim: Usd.Prim,
    replaced_range: Gf.Range3d,
) -> tuple[Gf.Range3d, float]:
    initial_range = compute_world_bbox(stage, asset_prim)
    if initial_range.IsEmpty() or replaced_range.IsEmpty():
        return initial_range, 1.0

    asset_size = initial_range.GetSize()
    replaced_size = replaced_range.GetSize()
    ratios = [
        float(replaced_size[index]) / max(float(asset_size[index]), 1e-6)
        for index in range(3)
    ]
    scale = max(min(ratios), 1e-6)
    asset_min = initial_range.GetMin()
    asset_max = initial_range.GetMax()
    replaced_min = replaced_range.GetMin()
    replaced_max = replaced_range.GetMax()
    asset_center = (asset_min + asset_max) * 0.5
    replaced_center = (replaced_min + replaced_max) * 0.5

    asset_xform = UsdGeom.Xformable(asset_prim)
    _clear_xform_ops(asset_prim)
    _append_translate_op(asset_xform, Gf.Vec3d(
        float(replaced_center[0]) - float(asset_center[0]) * scale,
        float(replaced_center[1]) - float(asset_center[1]) * scale,
        float(replaced_center[2]) - float(asset_center[2]) * scale,
    ))
    _append_scale_op(asset_xform, Gf.Vec3f(scale, scale, scale))
    return compute_world_bbox(stage, asset_prim), scale


def _is_gprim(prim: Usd.Prim) -> bool:
    return prim.IsA(UsdGeom.Gprim)


def _strip_dynamic_physics_apis(asset_root: Usd.Prim) -> list[str]:
    stripped: list[str] = []
    for prim in Usd.PrimRange(asset_root):
        if not prim.IsActive() or not prim.IsDefined():
            continue
        # A referenced articulated asset may be inserted below a different
        # namespace in a diagnostic scene.  Its absolute joint body targets do
        # not compose through that namespace, so a static-collider probe must
        # deactivate joints in the temporary test stage.  This never writes to
        # the source asset and deliberately isolates collision evidence from
        # articulation behavior.
        if prim.IsA(UsdPhysics.Joint):
            prim.SetActive(False)
            stripped.append(str(prim.GetPath()))
            continue
        removed = False
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
            removed = True
        if prim.HasAPI(UsdPhysics.MassAPI):
            prim.RemoveAPI(UsdPhysics.MassAPI)
            removed = True
        if PhysxSchema is not None and prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
            prim.RemoveAPI(PhysxSchema.PhysxRigidBodyAPI)
            removed = True
        if removed:
            stripped.append(str(prim.GetPath()))
    return stripped


def apply_static_colliders(asset_root: Usd.Prim) -> list[str]:
    collider_paths: list[str] = []
    _strip_dynamic_physics_apis(asset_root)

    for prim in Usd.PrimRange(asset_root):
        if not prim.IsActive() or not prim.IsDefined():
            continue
        if not _is_gprim(prim):
            continue

        # Input asset remains static: collision only, never rigid body.
        UsdPhysics.CollisionAPI.Apply(prim)
        if prim.IsA(UsdGeom.Mesh):
            mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
            mesh_collision.CreateApproximationAttr().Set(UsdPhysics.Tokens.none)
        collider_paths.append(str(prim.GetPath()))

    if collider_paths:
        return collider_paths

    UsdPhysics.CollisionAPI.Apply(asset_root)
    return [str(asset_root.GetPath())]


def collect_collision_paths(root: Usd.Prim) -> list[str]:
    paths: list[str] = []
    for prim in Usd.PrimRange(root):
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            paths.append(str(prim.GetPath()))
    return paths


def apply_dynamic_asset_physics(asset_root: Usd.Prim, velocity: Gf.Vec3f | None = None) -> list[str]:
    if velocity is None:
        velocity = Gf.Vec3f(0.0, 0.0, 0.0)

    _strip_dynamic_physics_apis(asset_root)
    collider_paths: list[str] = []
    for prim in Usd.PrimRange(asset_root):
        if not prim.IsActive() or not prim.IsDefined() or not _is_gprim(prim):
            continue
        UsdPhysics.CollisionAPI.Apply(prim)
        if prim.IsA(UsdGeom.Mesh):
            mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
            mesh_collision.CreateApproximationAttr().Set("convexDecomposition")
        collider_paths.append(str(prim.GetPath()))

    if not collider_paths:
        UsdPhysics.CollisionAPI.Apply(asset_root)
        collider_paths.append(str(asset_root.GetPath()))

    rigid_body = UsdPhysics.RigidBodyAPI.Apply(asset_root)
    rigid_body.CreateVelocityAttr().Set(velocity)
    rigid_body.CreateAngularVelocityAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    mass = UsdPhysics.MassAPI.Apply(asset_root)
    mass.CreateMassAttr().Set(1.0)
    apply_contact_report(asset_root)
    return collider_paths


def apply_contact_report(prim: Usd.Prim, threshold: float = 0.0) -> bool:
    if PhysxSchema is None:
        return False
    contact_report = PhysxSchema.PhysxContactReportAPI.Apply(prim)
    contact_report.CreateThresholdAttr().Set(threshold)
    return True


def create_bbox_collider(stage: Usd.Stage, asset_range: Gf.Range3d, collider_path: str = "/World/TopDropBBoxCollider") -> str | None:
    if asset_range.IsEmpty():
        return None

    existing_prim = stage.GetPrimAtPath(collider_path)
    if existing_prim and existing_prim.IsValid():
        stage.RemovePrim(collider_path)

    asset_min = asset_range.GetMin()
    asset_max = asset_range.GetMax()
    span = asset_max - asset_min
    center = (asset_min + asset_max) * 0.5
    scale = Gf.Vec3f(
        max(float(span[0]), 1e-4),
        max(float(span[1]), 1e-4),
        max(float(span[2]), 1e-4),
    )

    cube = UsdGeom.Cube.Define(stage, collider_path)
    cube.CreateSizeAttr(1.0)
    cube.CreateExtentAttr([Gf.Vec3f(-0.5, -0.5, -0.5), Gf.Vec3f(0.5, 0.5, 0.5)])
    imageable = UsdGeom.Imageable(cube.GetPrim())
    imageable.CreatePurposeAttr().Set(UsdGeom.Tokens.guide)
    xformable = UsdGeom.Xformable(cube.GetPrim())
    _append_translate_op(xformable, center)
    _append_scale_op(xformable, scale)
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())
    return collider_path


def create_dynamic_box(stage: Usd.Stage, asset_range: Gf.Range3d) -> tuple[str, tuple[float, float, float], tuple[float, float, float]]:
    box_path = "/World/DynamicHitBox"
    cube = UsdGeom.Cube.Define(stage, box_path)
    min_span = _stage_units_for_meters(stage, 0.5)
    min_cube_size = _stage_units_for_meters(stage, 0.2)
    max_cube_size = _stage_units_for_meters(stage, 0.75)
    min_velocity = _stage_units_for_meters(stage, 1.5)

    if asset_range.IsEmpty():
        half_span = min_span * 0.5
        asset_min = Gf.Vec3d(-half_span, -half_span, 0.0)
        asset_max = Gf.Vec3d(half_span, half_span, min_span)
    else:
        asset_min = asset_range.GetMin()
        asset_max = asset_range.GetMax()

    span = asset_max - asset_min
    span_x = max(float(span[0]), min_span)
    span_y = max(float(span[1]), min_span)
    span_z = max(float(span[2]), min_span)
    max_span = max(span_x, span_y, span_z)
    cube_size = max(min_cube_size, min(max_span * 0.25, max_cube_size))
    half_extent = cube_size / 2.0

    start_position = Gf.Vec3d(
        float(asset_min[0]) - cube_size * 3.0,
        float((asset_min[1] + asset_max[1]) / 2.0),
        float(max(cube_size, asset_min[2] + span_z * 0.5)),
    )
    start_velocity = Gf.Vec3f(max(min_velocity, span_x * 2.0), 0.0, 0.0)

    cube.CreateSizeAttr(cube_size)
    cube.CreateExtentAttr(
        [Gf.Vec3f(-half_extent, -half_extent, -half_extent), Gf.Vec3f(half_extent, half_extent, half_extent)]
    )
    xformable = UsdGeom.Xformable(cube.GetPrim())
    _append_translate_op(xformable, start_position)
    _append_scale_op(xformable, Gf.Vec3f(1.0, 1.0, 1.0))

    box_prim = cube.GetPrim()
    # Dynamic test object: collision + rigid body + mass + initial velocity.
    UsdPhysics.CollisionAPI.Apply(box_prim)
    rigid_body = UsdPhysics.RigidBodyAPI.Apply(box_prim)
    rigid_body.CreateVelocityAttr().Set(start_velocity)
    rigid_body.CreateAngularVelocityAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    mass = UsdPhysics.MassAPI.Apply(box_prim)
    mass.CreateMassAttr().Set(1.0)
    apply_contact_report(box_prim)

    return str(box_prim.GetPath()), _as_tuple(start_position), _as_tuple(start_velocity)


def _asset_span(asset_range: Gf.Range3d) -> tuple[Gf.Vec3d, Gf.Vec3d, Gf.Vec3d]:
    if asset_range.IsEmpty():
        asset_min = Gf.Vec3d(-0.25, -0.25, 0.0)
        asset_max = Gf.Vec3d(0.25, 0.25, 0.5)
    else:
        asset_min = asset_range.GetMin()
        asset_max = asset_range.GetMax()
    return asset_min, asset_max, asset_max - asset_min


def compute_top_drop_box_size(stage: Usd.Stage, asset_range: Gf.Range3d) -> float:
    _, _, span = _asset_span(asset_range)
    min_box_size = _stage_units_for_meters(stage, 0.08)
    max_box_size = _stage_units_for_meters(stage, 0.75)
    footprint_min = max(min(float(span[0]), float(span[1])), 1e-6)
    max_span = max(float(span[0]), float(span[1]), float(span[2]), min_box_size)
    return max(min_box_size, min(footprint_min * 0.45, max_span * 0.25, max_box_size))


def create_top_drop_box(
    stage: Usd.Stage,
    asset_range: Gf.Range3d,
    *,
    box_path: str = "/World/DynamicHitBox",
) -> tuple[str, tuple[float, float, float], tuple[float, float, float], float, tuple[float, float]]:
    existing_prim = stage.GetPrimAtPath(box_path)
    if existing_prim and existing_prim.IsValid():
        stage.RemovePrim(box_path)

    asset_min, asset_max, span = _asset_span(asset_range)
    cube_size = compute_top_drop_box_size(stage, asset_range)
    half_extent = cube_size / 2.0
    target_x = float((asset_min[0] + asset_max[0]) / 2.0)
    target_y = float((asset_min[1] + asset_max[1]) / 2.0)
    max_clearance = _stage_units_for_meters(stage, 1.5)
    min_velocity = _stage_units_for_meters(stage, 0.2)
    clearance = max(cube_size * 2.0, min(max(float(span[2]), cube_size) * 0.35, max_clearance))

    start_position = Gf.Vec3d(
        target_x,
        target_y,
        float(asset_max[2]) + clearance + half_extent,
    )
    start_velocity = Gf.Vec3f(0.0, 0.0, -max(min_velocity, cube_size * 0.5))

    cube = UsdGeom.Cube.Define(stage, box_path)
    cube.CreateSizeAttr(cube_size)
    cube.CreateExtentAttr(
        [Gf.Vec3f(-half_extent, -half_extent, -half_extent), Gf.Vec3f(half_extent, half_extent, half_extent)]
    )
    xformable = UsdGeom.Xformable(cube.GetPrim())
    _append_translate_op(xformable, start_position)

    box_prim = cube.GetPrim()
    UsdPhysics.CollisionAPI.Apply(box_prim)
    rigid_body = UsdPhysics.RigidBodyAPI.Apply(box_prim)
    rigid_body.CreateVelocityAttr().Set(start_velocity)
    rigid_body.CreateAngularVelocityAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    mass = UsdPhysics.MassAPI.Apply(box_prim)
    mass.CreateMassAttr().Set(1.0)
    apply_contact_report(box_prim)

    return str(box_prim.GetPath()), _as_tuple(start_position), _as_tuple(start_velocity), cube_size, (target_x, target_y)


def build_hit_test_stage(config: RuntimeConfig) -> SceneBuildResult:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix="omni_asset_cli_physics_hit_"))
    stage_path = stage_dir / "physics_hit_test_stage.usda"
    stage = create_base_stage(stage_path, config.fps)
    ground_prim_path = create_ground_plane(stage)
    asset_prim = create_input_asset_prim(
        stage,
        config.asset,
        rotation_y_deg=config.asset_rotation_y_deg,
        rotation_z_deg=config.asset_rotation_z_deg,
    )
    asset_unit_scale = _asset_units_to_stage_scale(config.asset, stage)
    asset_range_before_align = compute_world_bbox(stage, asset_prim)
    asset_range = align_asset_to_ground(stage, asset_prim)
    collider_paths = apply_static_colliders(asset_prim)
    if config.hit_mode == "top-drop":
        box_prim_path, box_initial_position, box_initial_velocity, box_size, drop_target_xy = create_top_drop_box(
            stage,
            asset_range,
        )
        test_type = "top_drop_box_hits_static_asset"
    else:
        box_prim_path, box_initial_position, box_initial_velocity = create_dynamic_box(stage, asset_range)
        box_size = None
        drop_target_xy = None
        test_type = "dynamic_box_hits_static_asset"
    stage.GetRootLayer().Save()

    bbox_min = asset_range.GetMin() if not asset_range.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    bbox_max = asset_range.GetMax() if not asset_range.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    bbox_before_min = (
        asset_range_before_align.GetMin() if not asset_range_before_align.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    )
    bbox_before_max = (
        asset_range_before_align.GetMax() if not asset_range_before_align.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    )

    return SceneBuildResult(
        stage_path=stage_path,
        template_scene_path=None,
        test_type=test_type,
        asset_prim_path=str(asset_prim.GetPath()),
        replaced_prim_path=None,
        box_prim_path=box_prim_path,
        ground_prim_path=ground_prim_path,
        collider_prim_paths=collider_paths,
        box_initial_position=box_initial_position,
        box_initial_velocity=box_initial_velocity,
        box_size=box_size,
        hit_mode=config.hit_mode,
        size_policy="preserve",
        asset_rotation_y_deg=config.asset_rotation_y_deg,
        asset_rotation_z_deg=config.asset_rotation_z_deg,
        drop_target_xy=drop_target_xy,
        asset_bbox_preserved=True,
        asset_unit_scale=asset_unit_scale,
        fit_mode=None,
        fit_scale=None,
        replaced_bbox_min=None,
        replaced_bbox_max=None,
        asset_bbox_before_align_min=_as_tuple(bbox_before_min),
        asset_bbox_before_align_max=_as_tuple(bbox_before_max),
        asset_bbox_min=_as_tuple(bbox_min),
        asset_bbox_max=_as_tuple(bbox_max),
    )


def build_template_hit_test_stage(config: RuntimeConfig) -> SceneBuildResult:
    if config.template_scene is None:
        raise ValueError("Template scene is required for template hit-test mode.")
    if not config.template_scene.exists():
        raise FileNotFoundError(f"Template scene does not exist: {config.template_scene}")

    config.out_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix="omni_asset_cli_template_hit_"))
    stage_path = stage_dir / "template_physics_hit_test_stage.usda"
    shutil.copyfile(config.template_scene, stage_path)

    stage = Usd.Stage.Open(str(stage_path))
    if stage is None:
        raise RuntimeError(f"Failed to open template scene: {stage_path}")

    slot_path = "/World/TestAssetSlot"
    default_table_path = "/World/roomScene/colliders/table"
    template_box_path = "/World/boxActor"
    table_path = config.replace_prim or default_table_path
    placement_mode = config.placement_mode
    if placement_mode == "auto":
        placement_mode = "replace-table" if config.replace_prim else "tabletop"
    if placement_mode == "replace-box":
        table_path = default_table_path
    if placement_mode not in {"replace-table", "tabletop", "replace-box"}:
        raise ValueError(f"Unsupported placement mode: {config.placement_mode}")
    asset_unit_scale = _asset_units_to_stage_scale(config.asset, stage)

    injection_path = table_path if placement_mode == "replace-table" else slot_path
    box_prim_path = template_box_path
    table_prim = stage.GetPrimAtPath(table_path)
    if not table_prim or not table_prim.IsValid():
        raise RuntimeError(f"Template table prim does not exist: {table_path}")
    table_range = compute_world_bbox(stage, table_prim)

    if placement_mode == "replace-box":
        original_box_prim = stage.GetPrimAtPath(template_box_path)
        if not original_box_prim or not original_box_prim.IsValid():
            raise RuntimeError(f"Template dynamic actor does not exist: {template_box_path}")
        replaced_range = compute_world_bbox(stage, original_box_prim)
        velocity = _read_box_velocity(stage, template_box_path)
        stage.RemovePrim(template_box_path)
        injected = UsdGeom.Xform.Define(stage, template_box_path)
        injected_prim = injected.GetPrim()
        _clear_xform_ops(injected_prim)
        _reference_asset_under(
            stage,
            config.asset,
            f"{template_box_path}/ReferencedAsset",
            rotation_y_deg=config.asset_rotation_y_deg,
            rotation_z_deg=config.asset_rotation_z_deg,
        )

        asset_range_before_align = compute_world_bbox(stage, injected_prim)
        if config.size_policy == "template-fit" and not replaced_range.IsEmpty():
            asset_range, fit_scale = fit_asset_to_replaced_bbox(stage, injected_prim, replaced_range)
            fit_mode = "uniform_bbox_to_replaced_box"
            asset_bbox_preserved = False
        elif not replaced_range.IsEmpty():
            asset_range = place_asset_at_bbox_center(stage, injected_prim, replaced_range)
            fit_scale = None
            fit_mode = "preserve_size_at_replaced_box_center"
            asset_bbox_preserved = True
        else:
            asset_range = align_asset_to_ground(stage, injected_prim)
            fit_scale = None
            fit_mode = "ground_align"
            asset_bbox_preserved = True

        collider_paths = collect_collision_paths(table_prim)
        if not collider_paths:
            collider_paths = apply_static_colliders(table_prim)
        apply_dynamic_asset_physics(injected_prim, Gf.Vec3f(*velocity))
        box_initial_position = _read_prim_position(stage, template_box_path)
        box_initial_velocity = velocity
        box_size = max(float(value) for value in asset_range.GetSize()) if not asset_range.IsEmpty() else None
        drop_target_xy = (
            (float(asset_range.GetMin()[0]) + float(asset_range.GetMax()[0])) / 2.0,
            (float(asset_range.GetMin()[1]) + float(asset_range.GetMax()[1])) / 2.0,
        ) if not asset_range.IsEmpty() else None
        test_type = "template_scene_input_asset_replaces_box"
        asset_prim_path = str(injected_prim.GetPath())
        replaced_prim_path = template_box_path
    else:
        replaced_range = table_range

        if placement_mode == "replace-table":
            stage.RemovePrim(injection_path)
        else:
            existing_slot = stage.GetPrimAtPath(slot_path)
            if existing_slot and existing_slot.IsValid():
                stage.RemovePrim(slot_path)
        injected = UsdGeom.Xform.Define(stage, injection_path)
        injected_prim = injected.GetPrim()
        _clear_xform_ops(injected_prim)
        _reference_asset_under(
            stage,
            config.asset,
            f"{injection_path}/ReferencedAsset",
            rotation_y_deg=config.asset_rotation_y_deg,
            rotation_z_deg=config.asset_rotation_z_deg,
        )

        asset_range_before_align = compute_world_bbox(stage, injected_prim)
        asset_bbox_preserved = True
        if placement_mode == "replace-table" and not replaced_range.IsEmpty() and config.size_policy == "template-fit":
            asset_range, fit_scale = fit_asset_to_replaced_footprint(stage, injected_prim, replaced_range)
            fit_mode = "uniform_footprint_to_replaced_prim"
            asset_bbox_preserved = False
        elif placement_mode == "replace-table" and not replaced_range.IsEmpty():
            asset_range = place_asset_on_replaced_prim_preserving_size(stage, injected_prim, replaced_range)
            fit_scale = None
            fit_mode = "preserve_size_on_replaced_prim"
        elif placement_mode == "tabletop" and not replaced_range.IsEmpty():
            asset_range = place_asset_on_tabletop_preserving_size(stage, injected_prim, replaced_range)
            fit_scale = None
            fit_mode = "preserve_size_on_tabletop_center"
        else:
            asset_range = align_asset_to_ground(stage, injected_prim)
            fit_scale = None
            fit_mode = "ground_align"
        collider_paths = apply_static_colliders(injected_prim)

        if config.hit_mode == "top-drop":
            box_prim_path, box_initial_position, box_initial_velocity, box_size, drop_target_xy = create_top_drop_box(
                stage,
                asset_range,
                box_path=box_prim_path,
            )
            test_type = "template_scene_top_drop_box_hits_asset"
        else:
            box_prim = stage.GetPrimAtPath(box_prim_path)
            if not box_prim or not box_prim.IsValid():
                raise RuntimeError(f"Template dynamic actor does not exist: {box_prim_path}")
            if not box_prim.HasAPI(UsdPhysics.RigidBodyAPI):
                raise RuntimeError(f"Template dynamic actor is not a rigid body: {box_prim_path}")
            apply_contact_report(box_prim)
            box_initial_position = _read_prim_position(stage, box_prim_path)
            box_initial_velocity = _read_box_velocity(stage, box_prim_path)
            box_size = None
            drop_target_xy = None
            test_type = "template_scene_dynamic_box_hits_asset"
        asset_prim_path = injection_path
        replaced_prim_path = table_path if placement_mode == "replace-table" else None
    stage.GetRootLayer().Save()

    bbox_min = asset_range.GetMin() if not asset_range.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    bbox_max = asset_range.GetMax() if not asset_range.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    bbox_before_min = (
        asset_range_before_align.GetMin() if not asset_range_before_align.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    )
    bbox_before_max = (
        asset_range_before_align.GetMax() if not asset_range_before_align.IsEmpty() else Gf.Vec3d(0.0, 0.0, 0.0)
    )
    replaced_bbox_min = replaced_range.GetMin() if not replaced_range.IsEmpty() else None
    replaced_bbox_max = replaced_range.GetMax() if not replaced_range.IsEmpty() else None

    return SceneBuildResult(
        stage_path=stage_path,
        template_scene_path=config.template_scene,
        test_type=test_type,
        asset_prim_path=asset_prim_path,
        replaced_prim_path=replaced_prim_path,
        box_prim_path=box_prim_path,
        ground_prim_path="",
        collider_prim_paths=collider_paths,
        box_initial_position=box_initial_position,
        box_initial_velocity=box_initial_velocity,
        box_size=box_size,
        hit_mode=config.hit_mode,
        size_policy=config.size_policy,
        asset_rotation_y_deg=config.asset_rotation_y_deg,
        asset_rotation_z_deg=config.asset_rotation_z_deg,
        drop_target_xy=drop_target_xy,
        asset_bbox_preserved=asset_bbox_preserved,
        asset_unit_scale=asset_unit_scale,
        fit_mode=fit_mode,
        fit_scale=fit_scale,
        replaced_bbox_min=_as_tuple(replaced_bbox_min) if replaced_bbox_min is not None else None,
        replaced_bbox_max=_as_tuple(replaced_bbox_max) if replaced_bbox_max is not None else None,
        asset_bbox_before_align_min=_as_tuple(bbox_before_min),
        asset_bbox_before_align_max=_as_tuple(bbox_before_max),
        asset_bbox_min=_as_tuple(bbox_min),
        asset_bbox_max=_as_tuple(bbox_max),
    )


def _load_simulation_app():
    try:
        from isaacsim import SimulationApp  # type: ignore

        return SimulationApp, "isaacsim.SimulationApp"
    except ImportError:
        pass

    try:
        from omni.isaac.kit import SimulationApp  # type: ignore

        return SimulationApp, "omni.isaac.kit.SimulationApp"
    except ImportError:
        return None, None


def _path_in_docker(path: Path, config: RuntimeConfig) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        relative = resolved.relative_to(root)
        return str(Path(config.docker_workspace) / relative)
    except ValueError:
        pass

    inspector_root = Path.home().resolve() / "usd-simready-inspector"
    try:
        relative = resolved.relative_to(inspector_root)
        return str(Path("/workspace/external/usd-simready-inspector") / relative)
    except ValueError:
        pass

    home = Path.home().resolve()
    try:
        resolved.relative_to(home)
    except ValueError as exc:
        raise ValueError(
            f"Docker runtime paths must be inside the repository or home mount: path={resolved}, repo={root}, home={home}"
        ) from exc

    staged = _stage_host_path_for_docker(resolved)
    relative = staged.relative_to(root)
    return str(Path(config.docker_workspace) / relative)


def _safe_stage_name(path: Path) -> str:
    name = path.name or path.stem or "asset"
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in name)


def _stage_host_path_for_docker(path: Path) -> Path:
    root = repo_root().resolve()
    stage_root = root / "out" / "runtime_inputs"
    home = Path.home().resolve()

    if path.is_dir():
        destination = stage_root / _safe_stage_name(path)
        shutil.copytree(path, destination, dirs_exist_ok=True)
        return destination

    if path.parent == home:
        destination_dir = stage_root / _safe_stage_name(path.with_suffix(""))
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / path.name
        shutil.copy2(path, destination)
        return destination

    package_root = path.parent
    destination_root = stage_root / _safe_stage_name(package_root)
    shutil.copytree(package_root, destination_root, dirs_exist_ok=True)
    return destination_root / path.relative_to(package_root)


def _build_docker_child_args(script_path: Path, config: RuntimeConfig) -> list[str]:
    command = [
        _path_in_docker(script_path, config),
        _path_in_docker(config.asset, config),
        "--frames",
        str(config.frames),
        "--fps",
        str(config.fps),
        "--out",
        _path_in_docker(config.out_dir, config),
        "--external-runtime-child",
    ]
    if config.template_scene is not None:
        command.extend(["--template-scene", _path_in_docker(config.template_scene, config)])
    if config.replace_prim:
        command.extend(["--replace-prim", config.replace_prim])
    command.extend(["--placement-mode", config.placement_mode])
    command.extend(["--hit-mode", config.hit_mode])
    command.extend(["--size-policy", config.size_policy])
    command.extend(["--asset-rotation-y-deg", str(config.asset_rotation_y_deg)])
    command.extend(["--asset-rotation-z-deg", str(config.asset_rotation_z_deg)])
    if not config.headless:
        command.append("--no-headless")
    if config.render_frames:
        command.append("--render-frames")
    command.extend(["--render-every-n-frames", str(config.render_every_n_frames)])
    command.extend(["--render-warmup-updates", str(config.render_warmup_updates)])
    for preset in config.render_camera_presets:
        command.extend(["--render-camera-preset", preset])
    command.extend(["--render-backend", config.render_backend])
    command.extend(["--render-width", str(config.render_width)])
    command.extend(["--render-height", str(config.render_height)])
    command.extend(["--render-rt-subframes", str(config.render_rt_subframes)])
    command.extend(["--render-wait-updates", str(config.render_wait_updates)])
    if config.render_video:
        command.append("--render-video")
    if config.render_video_fps is not None:
        command.extend(["--render-video-fps", str(config.render_video_fps)])
    command.extend(["--render-video-crf", str(config.render_video_crf)])
    if config.render_physics_bboxes:
        command.append("--render-physics-bboxes")
    if config.render_physics_bbox_fallback_default_prim:
        command.append("--render-physics-bbox-fallback-default-prim")
    command.extend(["--render-physics-bbox-width", str(config.render_physics_bbox_width)])
    return command


def _build_docker_run_command(script_path: Path, config: RuntimeConfig) -> list[str]:
    if not config.runtime_docker_image:
        raise ValueError("runtime_docker_image is required for docker run dispatch.")

    return [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--network",
        "host",
        "--ipc",
        "host",
        "-e",
        "ACCEPT_EULA=Y",
        "-e",
        "PRIVACY_CONSENT=Y",
        "-v",
        f"{repo_root().resolve()}:{config.docker_workspace}",
        "-v",
        f"{Path.home().resolve()}:/workspace/host",
        "-v",
        f"{(Path.home().resolve() / 'usd-simready-inspector')}:/workspace/external/usd-simready-inspector",
        "-w",
        config.docker_workspace,
        "--entrypoint",
        config.docker_python,
        config.runtime_docker_image,
        *_build_docker_child_args(script_path, config),
    ]


def _build_docker_exec_command(script_path: Path, config: RuntimeConfig) -> list[str]:
    if not config.runtime_docker_container:
        raise ValueError("runtime_docker_container is required for docker exec dispatch.")

    return [
        "docker",
        "exec",
        "-w",
        config.docker_workspace,
        config.runtime_docker_container,
        config.docker_python,
        *_build_docker_child_args(script_path, config),
    ]


RUNTIME_DOCKER_RESIDUAL_PATTERNS = (
    "run_physics_hit_test.py",
    "render_asset_table_drop.py",
    "render_asset_setup_orbit.py",
    "/isaac-sim/kit/python/bin/python3",
    "/isaac-sim/python.sh",
)


def _docker_container_runtime_processes(config: RuntimeConfig) -> list[dict[str, str]]:
    if not config.runtime_docker_container:
        return []
    completed = subprocess.run(
        [
            "docker",
            "exec",
            config.runtime_docker_container,
            "ps",
            "-eo",
            "pid=,ppid=,stat=,args=",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return [
            {
                "pid": "",
                "ppid": "",
                "stat": "",
                "args": f"process_scan_failed returncode={completed.returncode}: {completed.stderr.strip()[-500:]}",
            }
        ]

    processes: list[dict[str, str]] = []
    for line in completed.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, stat, args = parts
        if "ps -eo" in args:
            continue
        if any(pattern in args for pattern in RUNTIME_DOCKER_RESIDUAL_PATTERNS):
            processes.append({"pid": pid, "ppid": ppid, "stat": stat, "args": args})
    return processes


def _probe_docker_simulation_app(config: RuntimeConfig) -> tuple[bool, str]:
    if not config.runtime_docker_container:
        return True, ""
    probe_code = "\n".join(
        [
            "import json",
            "import sys",
            "ok = False",
            "name = None",
            "try:",
            "    from isaacsim import SimulationApp",
            "    ok = True",
            "    name = 'isaacsim.SimulationApp'",
            "except ImportError:",
            "    try:",
            "        from omni.isaac.kit import SimulationApp",
            "        ok = True",
            "        name = 'omni.isaac.kit.SimulationApp'",
            "    except ImportError:",
            "        pass",
            "print(json.dumps({'python': sys.executable, 'simulation_app_available': ok, 'simulation_app_name': name}))",
        ]
    )
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "-w",
            config.docker_workspace,
            config.runtime_docker_container,
            config.docker_python,
            "-c",
            probe_code,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        return False, f"returncode={completed.returncode}: {output[-500:]}"
    payload_line = output
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payload_line = stripped
            break
    try:
        payload = json.loads(payload_line)
    except Exception:
        return False, output[-500:]
    return bool(payload.get("simulation_app_available")), output


def _wait_for_docker_simulation_app(config: RuntimeConfig, timeout_seconds: float = 90.0) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    last_output = ""
    while time.monotonic() < deadline:
        ready, output = _probe_docker_simulation_app(config)
        last_output = output
        if ready:
            return True, output
        time.sleep(2.0)
    return False, last_output


def preflight_runtime_docker_container(config: RuntimeConfig) -> dict[str, Any]:
    mode = (config.runtime_docker_preflight or "auto").strip().lower()
    result: dict[str, Any] = {
        "mode": mode,
        "runtime_docker_container": config.runtime_docker_container,
        "residual_processes": [],
        "action": "skip",
        "ready": None,
        "probe_output": "",
    }
    if not config.runtime_docker_container or mode == "skip":
        return result
    if mode not in {"auto", "check", "restart"}:
        raise ValueError("--runtime-docker-preflight must be one of: auto, check, restart, skip")

    _progress(f"docker-preflight-start container={config.runtime_docker_container} mode={mode}")
    residuals = _docker_container_runtime_processes(config)
    result["residual_processes"] = residuals
    should_restart = mode == "restart" or (mode == "auto" and bool(residuals))
    if mode == "check" and residuals:
        result["action"] = "blocked_residual_processes"
        _progress(f"docker-preflight-blocked residual_processes={len(residuals)}")
        return result
    if should_restart:
        _progress(
            f"docker-preflight-restart container={config.runtime_docker_container} "
            f"residual_processes={len(residuals)}"
        )
        completed = subprocess.run(
            ["docker", "restart", config.runtime_docker_container],
            check=False,
            capture_output=True,
            text=True,
        )
        result["action"] = "restart"
        result["restart_returncode"] = completed.returncode
        result["restart_output"] = (completed.stdout or completed.stderr).strip()[-500:]
        if completed.returncode != 0:
            result["ready"] = False
            result["probe_output"] = result["restart_output"]
            _progress(f"docker-preflight-done action=restart ready=False returncode={completed.returncode}")
            return result
        ready, probe_output = _wait_for_docker_simulation_app(config)
        result["ready"] = ready
        result["probe_output"] = probe_output
        _progress(f"docker-preflight-done action=restart ready={ready}")
        return result

    ready, probe_output = _probe_docker_simulation_app(config)
    result["action"] = "probe"
    result["ready"] = ready
    result["probe_output"] = probe_output
    _progress(f"docker-preflight-done action=probe ready={ready} residual_processes={len(residuals)}")
    return result


def _prepare_docker_output_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        out_dir.chmod(0o777)
    except PermissionError:
        pass


def _make_docker_output_host_writable(config: RuntimeConfig) -> None:
    if not config.runtime_docker_container:
        return
    subprocess.run(
        [
            "docker",
            "exec",
            "-w",
            config.docker_workspace,
            config.runtime_docker_container,
            "chmod",
            "-R",
            "a+rwX",
            _path_in_docker(config.out_dir, config),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _load_summary_payload(out_dir: Path) -> dict[str, Any] | None:
    summary_path = out_dir / "summary.json"
    if not summary_path.exists():
        return None
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_json_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _test_type_for_config(config: RuntimeConfig) -> str:
    if config.template_scene is not None and config.placement_mode == "replace-box":
        return "template_scene_input_asset_replaces_box"
    if config.template_scene is not None and config.hit_mode == "top-drop":
        return "template_scene_top_drop_box_hits_asset"
    if config.template_scene is not None:
        return "template_scene_dynamic_box_hits_asset"
    if config.hit_mode == "top-drop":
        return "top_drop_box_hits_static_asset"
    return "dynamic_box_hits_static_asset"


def _clear_runtime_artifacts(out_dir: Path) -> None:
    for name in ("summary.json", "runtime_report.json", "timeline.csv"):
        path = out_dir / name
        if path.exists():
            path.unlink()
    for name in ("render_frames", "render_videos"):
        path = out_dir / name
        if path.exists() and path.is_dir():
            try:
                shutil.rmtree(path)
            except PermissionError:
                # Docker-created render artifacts can be root-owned on the host.
                # Leave stale media in place instead of blocking the authoritative runtime run.
                pass


def run_external_runtime(script_path: Path, config: RuntimeConfig) -> tuple[dict[str, Any], int] | None:
    if not (config.runtime_docker_container or config.runtime_docker_image):
        return None
    if _host_platform() != "linux":
        summary_payload = {
            "asset": str(config.asset),
            "test_type": _test_type_for_config(config),
            "result": "blocked",
            "frames": config.frames,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "checks": {
                "asset_loaded": False,
                "static_colliders_applied": False,
                "dynamic_box_created": False,
                "simulation_advanced": False,
                "hit_targeted": False,
                "size_preserved": False,
                "contact_report_detected": False,
                "contact_detected_or_inferred": False,
                "artifacts_written": True,
            },
            "notes": [
                "Runtime physics validation requires a Linux host with Isaac Sim Docker.",
                f"host_platform={_host_platform()}",
            ],
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
            "replace_prim": config.replace_prim,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "runtime_policy": "linux_docker_only",
        }
        write_json(config.out_dir / "summary.json", summary_payload)
        write_json(config.out_dir / "runtime_report.json", report_payload)
        write_timeline_csv(config.out_dir, [])
        return summary_payload, 2

    _prepare_docker_output_dir(config.out_dir)
    _clear_runtime_artifacts(config.out_dir)
    preflight_payload = preflight_runtime_docker_container(config)
    preflight_ready = preflight_payload.get("ready")
    if preflight_payload.get("action") == "blocked_residual_processes" or preflight_ready is False:
        residual_count = len(preflight_payload.get("residual_processes") or [])
        summary_payload = {
            "asset": str(config.asset),
            "test_type": _test_type_for_config(config),
            "result": "blocked",
            "frames": config.frames,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "checks": {
                "asset_loaded": False,
                "static_colliders_applied": False,
                "dynamic_box_created": False,
                "simulation_advanced": False,
                "hit_targeted": False,
                "size_preserved": False,
                "contact_report_detected": False,
                "contact_detected_or_inferred": False,
                "artifacts_written": True,
            },
            "notes": [
                "Docker runtime preflight failed before launching Isaac Sim.",
                f"runtime_docker_preflight={config.runtime_docker_preflight}",
                f"residual_processes={residual_count}",
            ],
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
            "replace_prim": config.replace_prim,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "external_runtime": {
                "runtime_docker_image": config.runtime_docker_image,
                "runtime_docker_container": config.runtime_docker_container,
                "preflight": preflight_payload,
            },
        }
        write_json(config.out_dir / "summary.json", summary_payload)
        write_json(config.out_dir / "runtime_report.json", report_payload)
        write_timeline_csv(config.out_dir, [])
        return summary_payload, 2

    command = (
        _build_docker_exec_command(script_path, config)
        if config.runtime_docker_container
        else _build_docker_run_command(script_path, config)
    )
    completed = subprocess.run(command, check=False)
    _make_docker_output_host_writable(config)
    payload = _load_summary_payload(config.out_dir)

    if payload is None:
        summary_payload = {
            "asset": str(config.asset),
            "test_type": _test_type_for_config(config),
            "result": "blocked",
            "frames": config.frames,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "checks": {
                "asset_loaded": False,
                "static_colliders_applied": False,
                "dynamic_box_created": False,
                "simulation_advanced": False,
                "hit_targeted": False,
                "size_preserved": False,
                "contact_report_detected": False,
                "contact_detected_or_inferred": False,
                "artifacts_written": True,
            },
            "notes": [
                f"Docker runtime command failed to produce summary.json: returncode={completed.returncode}",
                f"runtime_docker_image={config.runtime_docker_image}",
                f"runtime_docker_container={config.runtime_docker_container}",
            ],
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
            "replace_prim": config.replace_prim,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "external_runtime": {
                "runtime_docker_image": config.runtime_docker_image,
                "runtime_docker_container": config.runtime_docker_container,
                "preflight": preflight_payload,
                "command": command,
                "returncode": completed.returncode,
            },
        }
        write_json(config.out_dir / "summary.json", summary_payload)
        write_json(config.out_dir / "runtime_report.json", report_payload)
        write_timeline_csv(config.out_dir, [])
        payload = summary_payload
    else:
        payload.setdefault("notes", [])
        if config.runtime_docker_container:
            payload["notes"].append(f"external_runtime_docker_container={config.runtime_docker_container}")
        else:
            payload["notes"].append(f"external_runtime_docker_image={config.runtime_docker_image}")
        payload["notes"].append(
            f"runtime_docker_preflight={preflight_payload.get('action')} "
            f"residual_processes={len(preflight_payload.get('residual_processes') or [])}"
        )
        if completed.returncode != 0:
            payload["notes"].append(f"external_runtime_returncode={completed.returncode}")
        write_json(config.out_dir / "summary.json", payload)
        report_path = config.out_dir / "runtime_report.json"
        report_payload = _load_json_payload(report_path)
        if report_payload is not None:
            external_runtime = report_payload.setdefault("external_runtime", {})
            external_runtime.update(
                {
                    "runtime_docker_image": config.runtime_docker_image,
                    "runtime_docker_container": config.runtime_docker_container,
                    "preflight": preflight_payload,
                    "command": command,
                    "returncode": completed.returncode,
                }
            )
            write_json(report_path, report_payload)

    return payload, completed.returncode


def _read_box_position(stage: Usd.Stage, box_prim_path: str) -> tuple[float, float, float]:
    box_prim = stage.GetPrimAtPath(box_prim_path)
    xform_cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    transform = xform_cache.GetLocalToWorldTransform(box_prim)
    translation = transform.ExtractTranslation()
    return _as_tuple(translation)


def _read_box_velocity(stage: Usd.Stage, box_prim_path: str) -> tuple[float, float, float]:
    box_prim = stage.GetPrimAtPath(box_prim_path)
    velocity = UsdPhysics.RigidBodyAPI(box_prim).GetVelocityAttr().Get()
    if velocity is None:
        return (0.0, 0.0, 0.0)
    return _as_tuple(velocity)


def _sdf_path_from_contact_id(value: Any) -> str:
    if PhysicsSchemaTools is None:
        return ""
    try:
        return str(PhysicsSchemaTools.intToSdfPath(value))
    except Exception:
        return ""


def _path_is_or_under(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def _classify_contact_target(scene: SceneBuildResult, paths: list[str]) -> str:
    asset_root = scene.asset_prim_path
    if any(
        _path_is_or_under(path, asset_root) and not _path_is_or_under(path, scene.box_prim_path)
        for path in paths
    ):
        return "asset_subtree"
    if any(path == "/World/TopDropBBoxCollider" for path in paths):
        return "guide_bbox"
    if any(path in scene.collider_prim_paths for path in paths):
        return "registered_collider"
    return "other"


def _collect_box_contact_events(
    physx_simulation_interface: Any | None,
    scene: SceneBuildResult,
    frame: int,
    events: list[ContactEventSample],
    errors: list[str],
) -> None:
    if physx_simulation_interface is None or PhysicsSchemaTools is None:
        return

    try:
        contact_headers, _contact_data = physx_simulation_interface.get_contact_report()
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim runtime
        if len(errors) < 10:
            errors.append(f"frame={frame}: {type(exc).__name__}: {exc}")
        return

    for header in contact_headers:
        actor0 = _sdf_path_from_contact_id(header.actor0)
        actor1 = _sdf_path_from_contact_id(header.actor1)
        collider0 = _sdf_path_from_contact_id(header.collider0)
        collider1 = _sdf_path_from_contact_id(header.collider1)
        paths = [actor0, actor1, collider0, collider1]
        if not any(_path_is_or_under(path, scene.box_prim_path) for path in paths):
            continue

        target_kind = _classify_contact_target(scene, paths)
        events.append(
            ContactEventSample(
                frame=frame,
                event_type=int(header.type),
                actor0=actor0,
                actor1=actor1,
                collider0=collider0,
                collider1=collider1,
                num_contacts=int(header.num_contact_data),
                target_kind=target_kind,
            )
        )


def build_contact_report_summary(events: list[ContactEventSample], errors: list[str]) -> dict[str, Any]:
    target_events = [event for event in events if event.target_kind in {"asset_subtree", "registered_collider"}]
    asset_events = [event for event in events if event.target_kind == "asset_subtree"]
    guide_events = [event for event in events if event.target_kind == "guide_bbox"]
    other_events = [event for event in events if event.target_kind == "other"]

    return {
        "enabled": True,
        "method": "physx_contact_report",
        "event_count": len(events),
        "target_event_count": len(target_events),
        "asset_subtree_event_count": len(asset_events),
        "guide_bbox_event_count": len(guide_events),
        "other_box_event_count": len(other_events),
        "detected": len(target_events) > 0,
        "asset_subtree_detected": len(asset_events) > 0,
        "guide_bbox_detected": len(guide_events) > 0,
        "guide_bbox_is_pass_evidence": False,
        "first_target_event": asdict(target_events[0]) if target_events else None,
        "events": [asdict(event) for event in events[:20]],
        "errors": errors[:10],
    }


def _normalize_render_camera_presets(values: list[str]) -> list[str]:
    presets: list[str] = []
    for raw_value in values:
        for raw_item in str(raw_value).split(","):
            item = raw_item.strip().lower()
            if not item:
                continue
            if item not in RENDER_CAMERA_PRESETS:
                choices = ", ".join(sorted(RENDER_CAMERA_PRESETS))
                raise ValueError(f"Unsupported render camera preset '{item}'. Choices: {choices}")
            if item not in presets:
                presets.append(item)
    return presets or ["active"]


def _render_camera_name(preset: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in preset).strip("_") or "camera"


def _look_at_matrix(eye: Any, target: Any) -> Any:
    _ensure_pxr_loaded()
    direction = (target - eye).GetNormalized()
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    if abs(float(Gf.Dot(direction, up))) > 0.98:
        up = Gf.Vec3d(0.0, 1.0, 0.0)
    right = Gf.Cross(direction, up).GetNormalized()
    true_up = Gf.Cross(right, direction).GetNormalized()
    return Gf.Matrix4d(
        right[0],
        right[1],
        right[2],
        0.0,
        true_up[0],
        true_up[1],
        true_up[2],
        0.0,
        -direction[0],
        -direction[1],
        -direction[2],
        0.0,
        eye[0],
        eye[1],
        eye[2],
        1.0,
    )


def _camera_target_and_radius(stage: Any, scene: SceneBuildResult) -> tuple[Any, float]:
    _ensure_pxr_loaded()
    asset_min = Gf.Vec3d(*scene.asset_bbox_min)
    asset_max = Gf.Vec3d(*scene.asset_bbox_max)
    box_start = Gf.Vec3d(*scene.box_initial_position)
    # Template side-hit scenes reuse their authored dynamic actor and therefore
    # do not populate ``box_size`` (top-drop scenes do).  Camera framing is
    # diagnostic-only, so retain a conservative one-unit fallback instead of
    # failing the physics run before simulation begins.
    box_extent = max(float(scene.box_size) if scene.box_size is not None else 1.0, 1.0)

    view_range = Gf.Range3d()
    view_range.UnionWith(Gf.Range3d(asset_min, asset_max))
    if scene.replaced_bbox_min is not None and scene.replaced_bbox_max is not None:
        replaced_min = Gf.Vec3d(*scene.replaced_bbox_min)
        replaced_max = Gf.Vec3d(*scene.replaced_bbox_max)
        asset_span = asset_max - asset_min
        center_x = float(scene.drop_target_xy[0]) if scene.drop_target_xy is not None else float((asset_min[0] + asset_max[0]) * 0.5)
        center_y = float(scene.drop_target_xy[1]) if scene.drop_target_xy is not None else float((asset_min[1] + asset_max[1]) * 0.5)
        replaced_half_x = max(float(replaced_max[0] - replaced_min[0]) * 0.5, 1.0)
        replaced_half_y = max(float(replaced_max[1] - replaced_min[1]) * 0.5, 1.0)
        context_half_x = min(
            replaced_half_x,
            max(float(asset_span[0]) * 2.5, box_extent * 5.0, 35.0),
        )
        context_half_y = min(
            replaced_half_y,
            max(float(asset_span[1]) * 2.5, box_extent * 5.0, 35.0),
        )
        # Use the replacement/table prim for horizontal framing and contact
        # plane context, but do not let table legs or lower support geometry
        # pull the camera target below the asset/contact animation.
        view_range.UnionWith(
            Gf.Range3d(
                Gf.Vec3d(center_x - context_half_x, center_y - context_half_y, min(float(asset_min[2]), float(replaced_max[2]))),
                Gf.Vec3d(center_x + context_half_x, center_y + context_half_y, max(float(asset_max[2]), float(replaced_max[2]))),
            )
        )
    view_range.UnionWith(
        Gf.Range3d(
            box_start - Gf.Vec3d(box_extent, box_extent, box_extent),
            box_start + Gf.Vec3d(box_extent, box_extent, box_extent),
        )
    )
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    for collider_path in scene.collider_prim_paths:
        prim = stage.GetPrimAtPath(collider_path)
        if not prim:
            continue
        collider_range = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
        if not collider_range.IsEmpty():
            view_range.UnionWith(collider_range)

    view_min = view_range.GetMin()
    view_max = view_range.GetMax()
    target = (view_min + view_max) * 0.5
    size = view_max - view_min
    radius = max(
        float(size[0]) * 1.8,
        float(size[1]) * 1.8,
        float(size[2]) * 1.55,
        box_extent * 7.0,
        85.0,
    )
    return target, radius


def _camera_offset(preset: str, radius: float) -> Any:
    _ensure_pxr_loaded()
    if preset == "front":
        return Gf.Vec3d(0.0, -radius * 2.2, radius * 0.55)
    if preset == "back":
        return Gf.Vec3d(0.0, radius * 2.2, radius * 0.55)
    if preset == "left":
        return Gf.Vec3d(-radius * 2.2, 0.0, radius * 0.55)
    if preset in {"right", "side"}:
        return Gf.Vec3d(radius * 2.2, 0.0, radius * 0.55)
    if preset == "top":
        return Gf.Vec3d(0.0, -radius * 0.02, radius * 2.4)
    return Gf.Vec3d(radius * 1.75, -radius * 1.75, radius * 0.95)


def _configure_wide_camera(camera: Any, preset: str, radius: float) -> float:
    focal_length = 22.0 if preset == "top" else 24.0
    camera.CreateFocalLengthAttr(focal_length)
    camera.CreateHorizontalApertureAttr(60.0)
    camera.CreateVerticalApertureAttr(33.75)
    camera.CreateClippingRangeAttr(Gf.Vec2f(0.1, max(radius * 30.0, 1000.0)))
    return focal_length


def _prepare_render_cameras(stage: Any, scene: SceneBuildResult, config: RuntimeConfig) -> list[dict[str, str | None]]:
    presets = _normalize_render_camera_presets(config.render_camera_presets)
    specs: list[dict[str, str | None]] = []
    if presets == ["active"]:
        return [{"name": "active", "preset": "active", "camera_path": None}]

    target, radius = _camera_target_and_radius(stage, scene)
    old_target = stage.GetEditTarget()
    stage.SetEditTarget(stage.GetSessionLayer())
    try:
        root_path = Sdf.Path(RENDER_CAMERA_ROOT)
        if stage.GetPrimAtPath(root_path):
            stage.RemovePrim(root_path)
        UsdGeom.Xform.Define(stage, root_path)
        for index, preset in enumerate(presets):
            name = _render_camera_name(preset)
            if preset == "active":
                specs.append({"name": name, "preset": preset, "camera_path": None})
                continue
            camera_path = root_path.AppendChild(f"Camera_{name}")
            camera = UsdGeom.Camera.Define(stage, camera_path)
            eye = target + _camera_offset(preset, radius)
            _clear_xform_ops(camera.GetPrim())
            matrix = _look_at_matrix(eye, target)
            UsdGeom.Xformable(camera.GetPrim()).AddTransformOp().Set(matrix)
            focal_length = _configure_wide_camera(camera, preset, radius)
            capture_camera_path = str(camera_path)
            if index == 0:
                active_camera_path = Sdf.Path("/World/Camera")
                active_camera = UsdGeom.Camera.Define(stage, active_camera_path)
                _clear_xform_ops(active_camera.GetPrim())
                UsdGeom.Xformable(active_camera.GetPrim()).AddTransformOp().Set(matrix)
                _configure_wide_camera(active_camera, preset, radius)
                capture_camera_path = str(active_camera_path)
            specs.append({
                "name": name,
                "preset": preset,
                "camera_path": capture_camera_path,
                "target": str(tuple(round(float(value), 4) for value in target)),
                "eye": str(tuple(round(float(value), 4) for value in eye)),
                "radius": f"{radius:.4f}",
                "focal_length": f"{focal_length:.4f}",
            })
        return specs
    finally:
        stage.SetEditTarget(old_target)


def _set_viewport_camera(viewport: Any, camera_path: str | None) -> None:
    if not camera_path:
        return
    _ensure_pxr_loaded()
    path = Sdf.Path(camera_path)
    switched = False
    try:
        result = viewport.set_active_camera(path)
        switched = result is not False
    except Exception:
        pass
    if switched:
        return
    try:
        result = viewport.set_active_camera(camera_path)
        switched = result is not False
    except Exception:
        pass
    if switched:
        return
    for value in (path, camera_path):
        try:
            viewport.camera_path = value
            return
        except Exception:
            pass


def _replicator_pngs(directory: Path) -> set[Path]:
    return {path for path in directory.rglob("*.png") if path.is_file()}


def _prepare_replicator_capture(
    config: RuntimeConfig,
    render_camera_specs: list[dict[str, str | None]],
    simulation_app: Any,
) -> tuple[Any | None, list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        import omni.replicator.core as rep  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim replicator extension
        return None, [], [f"replicator_unavailable: {type(exc).__name__}: {exc}"]

    contexts: list[dict[str, Any]] = []
    rep_root = config.out_dir / "_replicator_render_product"
    rep_root.mkdir(parents=True, exist_ok=True)
    for camera_spec in render_camera_specs:
        camera_path = camera_spec.get("camera_path")
        camera_name = str(camera_spec["name"])
        if not camera_path:
            errors.append(f"camera={camera_name}: replicator backend requires an authored camera preset")
            continue
        rep_dir = rep_root / camera_name
        rep_dir.mkdir(parents=True, exist_ok=True)
        try:
            render_product = rep.create.render_product(
                camera_path,
                (max(int(config.render_width), 1), max(int(config.render_height), 1)),
            )
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=str(rep_dir), rgb=True)
            writer.attach([render_product])
            contexts.append(
                {
                    "camera": camera_name,
                    "camera_path": camera_path,
                    "rep_dir": rep_dir,
                    "render_product": render_product,
                    "writer": writer,
                }
            )
        except Exception as exc:  # pragma: no cover - depends on Isaac Sim replicator extension
            errors.append(f"camera={camera_name}: replicator_setup_failed: {type(exc).__name__}: {exc}")

    for _ in range(40):
        simulation_app.update()
    return rep, contexts, errors


def _capture_replicator_frames(
    rep: Any,
    contexts: list[dict[str, Any]],
    frame_paths: dict[str, Path],
    simulation_app: Any,
    config: RuntimeConfig,
) -> dict[str, str | None]:
    before = {context["camera"]: _replicator_pngs(context["rep_dir"]) for context in contexts}
    try:
        rep.orchestrator.step(rt_subframes=max(int(config.render_rt_subframes), 1))
        try:
            rep.orchestrator.wait_until_complete()
        except Exception:
            pass
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim replicator extension
        return {context["camera"]: f"{type(exc).__name__}: {exc}" for context in contexts}

    errors: dict[str, str | None] = {}
    pending = {context["camera"]: context for context in contexts}
    for _ in range(max(int(config.render_wait_updates), 1)):
        simulation_app.update()
        for camera_name, context in list(pending.items()):
            after = _replicator_pngs(context["rep_dir"])
            new_files = sorted(after - before[camera_name], key=lambda path: path.stat().st_mtime)
            if not new_files:
                continue
            shutil.copyfile(new_files[-1], frame_paths[camera_name])
            errors[camera_name] = None
            pending.pop(camera_name, None)
        if not pending:
            return errors

    for camera_name, context in pending.items():
        after = _replicator_pngs(context["rep_dir"])
        new_files = sorted(after - before[camera_name], key=lambda path: path.stat().st_mtime)
        if new_files:
            shutil.copyfile(new_files[-1], frame_paths[camera_name])
            errors[camera_name] = None
        else:
            errors[camera_name] = f"replicator did not write a png for {frame_paths[camera_name]}"
    return errors


def _progress(message: str) -> None:
    print(f"[omni-asset-cli] {message}", flush=True)


def _capture_viewport_frame(
    path: Path,
    camera_path: str | None = None,
    simulation_app: Any | None = None,
    wait_updates: int = 1,
) -> str | None:
    try:
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport  # type: ignore

        viewport = get_active_viewport()
        if viewport is None:
            return "No active viewport is available for capture."
        _set_viewport_camera(viewport, camera_path)
        if camera_path and simulation_app is not None:
            simulation_app.update()
        capture_viewport_to_file(viewport, str(path))
        if simulation_app is not None:
            for _ in range(max(int(wait_updates), 1)):
                simulation_app.update()
                if path.exists():
                    break
        return None
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim viewport extension
        return f"{type(exc).__name__}: {exc}"


def _maybe_capture_frame(
    config: RuntimeConfig,
    frame: int,
    *,
    simulation_app: Any,
    timeline: Any | None = None,
    render_camera_specs: list[dict[str, str | None]],
    render_captures: dict[str, dict[str, Any]],
    legacy_single_camera: bool,
    replicator: Any | None,
    replicator_contexts: list[dict[str, Any]],
) -> None:
    if not config.render_frames:
        return
    every = max(1, config.render_every_n_frames)
    if frame % every != 0:
        return

    if timeline is not None:
        try:
            if bool(timeline.is_playing()):
                timeline.pause()
        except Exception:
            pass

    frame_paths: dict[str, Path] = {}
    for camera_spec in render_camera_specs:
        camera_name = str(camera_spec["name"])
        camera_dir = config.out_dir / "render_frames"
        if not legacy_single_camera:
            camera_dir = camera_dir / camera_name
        camera_dir.mkdir(parents=True, exist_ok=True)
        frame_path = camera_dir / f"frame_{frame:04d}.png"
        frame_paths[camera_name] = frame_path

    if config.render_backend == "replicator" and replicator is not None and replicator_contexts:
        errors_by_camera = _capture_replicator_frames(
            replicator,
            replicator_contexts,
            frame_paths,
            simulation_app,
            config,
        )
        for camera_name, frame_path in frame_paths.items():
            capture = render_captures[camera_name]
            error = errors_by_camera.get(camera_name)
            if error:
                capture["errors"].append(f"frame={frame}: {error}")
                continue
            if not frame_path.exists():
                capture["errors"].append(f"frame={frame}: capture requested but file was not written: {frame_path}")
                continue
            capture["files"].append(str(frame_path))
    else:
        for camera_spec in render_camera_specs:
            camera_name = str(camera_spec["name"])
            frame_path = frame_paths[camera_name]
            error = _capture_viewport_frame(
                frame_path,
                camera_spec.get("camera_path"),
                simulation_app,
                config.render_wait_updates,
            )
            for _ in range(max(0, config.render_warmup_updates)):
                simulation_app.update()
            capture = render_captures[camera_name]
            if error:
                capture["errors"].append(f"frame={frame}: {error}")
                continue
            if not frame_path.exists():
                capture["errors"].append(f"frame={frame}: capture requested but file was not written: {frame_path}")
                continue
            capture["files"].append(str(frame_path))

    if timeline is not None:
        try:
            timeline.play()
        except Exception:
            pass


def _copy_video_frame_sequence(files: list[str], sequence_dir: Path) -> int:
    sequence_dir.mkdir(parents=True, exist_ok=True)
    for index, value in enumerate(files):
        source = Path(value)
        if not source.exists():
            continue
        shutil.copy2(source, sequence_dir / f"frame_{index:04d}.png")
    return len(list(sequence_dir.glob("frame_*.png")))


def _encode_render_videos(
    config: RuntimeConfig,
    render_captures: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not config.render_video:
        return [], []

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return [], ["ffmpeg was not found in PATH; render frame PNGs were written but mp4 encoding was skipped."]

    video_dir = config.out_dir / "render_videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_fps = config.render_video_fps or max(float(config.fps) / max(config.render_every_n_frames, 1), 1.0)
    videos: list[dict[str, Any]] = []
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="omni_asset_video_", dir=str(config.out_dir)) as tmp_dir:
        tmp_root = Path(tmp_dir)
        for camera_name, capture in render_captures.items():
            files = [str(path) for path in capture.get("files", [])]
            if not files:
                errors.append(f"camera={camera_name}: no rendered PNG frames were available for mp4 encoding")
                continue
            sequence_dir = tmp_root / camera_name
            frame_count = _copy_video_frame_sequence(files, sequence_dir)
            if frame_count == 0:
                errors.append(f"camera={camera_name}: no existing PNG frames were available for mp4 encoding")
                continue

            video_path = video_dir / f"{camera_name}.mp4"
            _progress(f"video-encode-start camera={camera_name} frames={frame_count} output={video_path}")
            command = [
                ffmpeg,
                "-y",
                "-framerate",
                f"{video_fps:g}",
                "-i",
                str(sequence_dir / "frame_%04d.png"),
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-crf",
                str(config.render_video_crf),
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(video_path),
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode != 0 or not video_path.exists():
                errors.append(
                    f"camera={camera_name}: ffmpeg failed returncode={completed.returncode}: "
                    f"{completed.stderr[-500:]}"
                )
                continue
            _progress(f"video-encode-done camera={camera_name} output={video_path}")
            videos.append(
                {
                    "camera": camera_name,
                    "path": str(video_path),
                    "frame_count": frame_count,
                    "fps": video_fps,
                    "codec": "libx264",
                    "crf": config.render_video_crf,
                }
            )
    return videos, errors


def run_simulation(
    config: RuntimeConfig,
    scene: SceneBuildResult,
    *,
    simulation_app_cls: Any,
    runtime_name: str | None,
    simulation_app: Any | None = None,
) -> tuple[str, list[TimelineSample], dict[str, Any], list[str]]:
    if simulation_app_cls is None:
        return (
            "blocked",
            [],
            {},
            [
                "Runtime physics requires Isaac Sim or Kit Python with SimulationApp support.",
                "Current interpreter exposes pxr and omni.asset_validator, but not a physics-capable Omniverse runtime.",
            ],
        )

    notes = [f"runtime={runtime_name or 'unavailable'}", f"host_platform={_host_platform()}"]
    samples: list[TimelineSample] = []
    final_state: dict[str, Any] = {}
    contact_events: list[ContactEventSample] = []
    contact_errors: list[str] = []
    render_camera_specs: list[dict[str, str | None]] = []
    render_captures: dict[str, dict[str, Any]] = {}
    replicator: Any | None = None
    replicator_contexts: list[dict[str, Any]] = []
    render_videos: list[dict[str, Any]] = []
    render_video_errors: list[str] = []
    physics_bbox_overlay_targets: list[str] = []
    owns_simulation_app = simulation_app is None
    if simulation_app is None:
        app_config: dict[str, Any] = {"headless": config.headless}
        if config.render_frames:
            app_config.update({"width": config.render_width, "height": config.render_height})
        _progress(
            "simulation-app-create "
            f"headless={config.headless} render_frames={config.render_frames} "
            f"resolution={config.render_width}x{config.render_height if config.render_frames else 'n/a'}"
        )
        simulation_app = simulation_app_cls(app_config)
        _progress("simulation-app-ready")

    try:
        import omni.timeline  # type: ignore
        import omni.usd  # type: ignore

        try:
            from omni.physx import get_physx_simulation_interface  # type: ignore

            physx_simulation_interface = get_physx_simulation_interface()
        except Exception as exc:  # pragma: no cover - depends on Isaac Sim runtime
            physx_simulation_interface = None
            contact_errors.append(f"contact_report_unavailable: {type(exc).__name__}: {exc}")

        usd_context = omni.usd.get_context()
        _progress(f"stage-open-start path={scene.stage_path}")
        opened = usd_context.open_stage(str(scene.stage_path))
        if opened is False:
            raise RuntimeError(f"Failed to open stage: {scene.stage_path}")

        for _ in range(8):
            simulation_app.update()

        stage = usd_context.get_stage()
        if stage is None:
            raise RuntimeError("Omniverse USD context did not return a stage.")
        _progress(f"stage-open-done path={scene.stage_path}")

        if config.render_frames:
            render_camera_specs = _prepare_render_cameras(stage, scene, config)
            _progress(
                "render-setup-start "
                f"backend={config.render_backend} cameras="
                f"{','.join(str(spec.get('name')) for spec in render_camera_specs)}"
            )
            legacy_single_camera = (
                len(render_camera_specs) == 1
                and render_camera_specs[0].get("name") == "active"
                and not config.render_camera_presets
            )
            for camera_spec in render_camera_specs:
                camera_name = str(camera_spec["name"])
                camera_dir = config.out_dir / "render_frames"
                if not legacy_single_camera:
                    camera_dir = camera_dir / camera_name
                render_captures[camera_name] = {
                    "name": camera_name,
                    "preset": camera_spec.get("preset"),
                    "camera_path": camera_spec.get("camera_path"),
                    "output_dir": str(camera_dir),
                    "files": [],
                    "errors": [],
                }
            if config.render_backend == "replicator":
                replicator, replicator_contexts, setup_errors = _prepare_replicator_capture(
                    config,
                    render_camera_specs,
                    simulation_app,
                )
                for error in setup_errors:
                    notes.append(error)
                    for capture in render_captures.values():
                        capture["errors"].append(error)
            _progress("render-setup-done")
        else:
            legacy_single_camera = True

        if config.render_physics_bboxes:
            physics_bbox_overlay_targets = add_physics_bbox_session_overlay(
                stage,
                collider_paths=scene.collider_prim_paths,
                fallback_prim_path=scene.asset_prim_path,
                fallback_default_prim=config.render_physics_bbox_fallback_default_prim,
                width=config.render_physics_bbox_width,
            )
            physics_bbox_overlay_targets.extend(
                add_dynamic_asset_bbox_session_overlay(
                    stage,
                    asset_root_path=scene.asset_prim_path,
                    width=config.render_physics_bbox_width,
                )
            )
            if physics_bbox_overlay_targets:
                notes.append(f"physics_bbox_overlay_targets={len(physics_bbox_overlay_targets)}")
            else:
                notes.append("physics_bbox_overlay_targets=0")

        timeline = omni.timeline.get_timeline_interface()
        timeline.set_current_time(0.0)
        timeline.play()
        _progress(f"simulation-start frames={config.frames} render_frames={config.render_frames}")

        for frame in range(config.frames):
            position = _read_box_position(stage, scene.box_prim_path)
            velocity = _read_box_velocity(stage, scene.box_prim_path)
            samples.append(
                TimelineSample(
                    frame=frame,
                    time=round(frame / config.fps, 6),
                    box_x=position[0],
                    box_y=position[1],
                    box_z=position[2],
                    vel_x=velocity[0],
                    vel_y=velocity[1],
                    vel_z=velocity[2],
                )
            )
            _maybe_capture_frame(
                config,
                frame,
                simulation_app=simulation_app,
                timeline=timeline,
                render_camera_specs=render_camera_specs,
                render_captures=render_captures,
                legacy_single_camera=legacy_single_camera,
                replicator=replicator,
                replicator_contexts=replicator_contexts,
            )
            try:
                timeline.play()
            except Exception:
                pass
            simulation_app.update()
            _collect_box_contact_events(
                physx_simulation_interface,
                scene,
                frame,
                contact_events,
                contact_errors,
            )
            if config.render_frames and (
                frame == 0
                or frame == config.frames - 1
                or (frame + 1) % max(config.render_every_n_frames * 10, 10) == 0
            ):
                captured_count = sum(len(capture.get("files", [])) for capture in render_captures.values())
                error_count = sum(len(capture.get("errors", [])) for capture in render_captures.values())
                _progress(
                    f"render-progress frame={frame + 1}/{config.frames} "
                    f"captured={captured_count} errors={error_count}"
                )

        timeline.stop()
        _progress("simulation-done")
        render_videos, render_video_errors = _encode_render_videos(config, render_captures)
        final_sample = samples[-1] if samples else None
        render_files = [
            path
            for capture in render_captures.values()
            for path in capture.get("files", [])
        ]
        render_errors = [
            error
            for capture in render_captures.values()
            for error in capture.get("errors", [])
        ]
        final_state = {
            "sample_count": len(samples),
            "last_frame": final_sample.frame if final_sample else None,
            "box_position": [final_sample.box_x, final_sample.box_y, final_sample.box_z] if final_sample else None,
            "box_velocity": [final_sample.vel_x, final_sample.vel_y, final_sample.vel_z] if final_sample else None,
            "render_capture": {
                "enabled": config.render_frames,
                "backend": config.render_backend,
                "resolution": [config.render_width, config.render_height] if config.render_frames else None,
                "frame_count": len(render_files),
                "output_dir": str(config.out_dir / "render_frames") if config.render_frames else None,
                "files": render_files[:10],
                "errors": render_errors[:10],
                "cameras": [
                    {
                        "name": capture.get("name"),
                        "preset": capture.get("preset"),
                        "camera_path": capture.get("camera_path"),
                        "output_dir": capture.get("output_dir"),
                        "frame_count": len(capture.get("files", [])),
                        "files": capture.get("files", [])[:10],
                        "errors": capture.get("errors", [])[:10],
                    }
                    for capture in render_captures.values()
                ],
                "video_enabled": config.render_video,
                "video_output_dir": str(config.out_dir / "render_videos") if config.render_video else None,
                "videos": render_videos,
                "video_errors": render_video_errors[:10],
                "physics_bbox_overlay_enabled": config.render_physics_bboxes,
                "physics_bbox_overlay_targets": physics_bbox_overlay_targets,
                "physics_bbox_overlay_session_root": DEBUG_PHYSICS_BBOX_ROOT if config.render_physics_bboxes else None,
            },
            "contact_report": build_contact_report_summary(contact_events, contact_errors),
        }
        return "passed", samples, final_state, notes
    finally:
        try:
            if config.render_physics_bboxes:
                import omni.usd  # type: ignore

                stage = omni.usd.get_context().get_stage()
                if stage is not None:
                    clear_physics_bbox_session_overlay(stage)
        except Exception:
            pass
        if owns_simulation_app:
            simulation_app.close()


def _xy_inside_asset_bbox(scene: SceneBuildResult, x: float, y: float, margin: float = 0.0) -> bool:
    min_x, min_y, _ = scene.asset_bbox_min
    max_x, max_y, _ = scene.asset_bbox_max
    return (min_x - margin) <= x <= (max_x + margin) and (min_y - margin) <= y <= (max_y + margin)


def analyze_hit(
    scene: SceneBuildResult,
    simulation_status: str,
    samples: list[TimelineSample],
    contact_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hit_targeted = True
    contact_detected = bool(contact_report and contact_report.get("detected"))
    contact_inferred = False
    box_descended = False
    min_box_z = None
    final_box_z = None
    initial_box_z = scene.box_initial_position[2] if scene.box_initial_position else None
    descent_delta = None

    if scene.hit_mode == "top-drop":
        if scene.drop_target_xy is None:
            hit_targeted = False
        else:
            hit_targeted = _xy_inside_asset_bbox(scene, scene.drop_target_xy[0], scene.drop_target_xy[1])

    if samples:
        first = samples[0]
        last = samples[-1]
        min_box_z = min(sample.box_z for sample in samples)
        final_box_z = last.box_z
        reference_box_z = initial_box_z if initial_box_z is not None else first.box_z
        descent_delta = reference_box_z - min_box_z
        box_descended = descent_delta > max(abs(reference_box_z) * 1e-5, 1e-4)

        if scene.hit_mode == "top-drop" and scene.box_size is not None:
            asset_top = scene.asset_bbox_max[2]
            contact_plane_z = asset_top + (scene.box_size / 2.0)
            z_reached_asset = min_box_z <= contact_plane_z + max(scene.box_size * 0.25, 0.02)
            xy_targeted = hit_targeted and _xy_inside_asset_bbox(scene, last.box_x, last.box_y, margin=scene.box_size)
            contact_inferred = simulation_status == "passed" and box_descended and z_reached_asset and xy_targeted
        else:
            contact_inferred = simulation_status == "passed" and len(samples) > 0

    evidence_method = "physx_contact_report" if contact_detected else "bbox_motion_heuristic"
    return {
        "hit_targeted": hit_targeted,
        "size_preserved": scene.asset_bbox_preserved,
        "contact_detected": contact_detected,
        "contact_inferred": contact_inferred,
        "contact_detected_or_inferred": contact_detected or contact_inferred,
        "contact_evidence_level": "detected" if contact_detected else "inferred" if contact_inferred else "none",
        "box_descended": box_descended,
        "initial_box_z": initial_box_z,
        "descent_delta": descent_delta,
        "min_box_z": min_box_z,
        "final_box_z": final_box_z,
        "method": evidence_method,
    }


def build_checks(
    scene: SceneBuildResult,
    simulation_status: str,
    samples: list[TimelineSample],
    hit_analysis: dict[str, Any],
) -> dict[str, bool]:
    return {
        "asset_loaded": bool(scene.asset_prim_path),
        "static_colliders_applied": len(scene.collider_prim_paths) > 0,
        "dynamic_box_created": bool(scene.box_prim_path),
        "simulation_advanced": simulation_status == "passed" and len(samples) > 0,
        "hit_targeted": bool(hit_analysis.get("hit_targeted")),
        "size_preserved": bool(hit_analysis.get("size_preserved")),
        "contact_report_detected": bool(hit_analysis.get("contact_detected")),
        "contact_detected_or_inferred": bool(hit_analysis.get("contact_detected_or_inferred")),
        "artifacts_written": True,
    }


def write_timeline_csv(out_dir: Path, samples: list[TimelineSample]) -> Path:
    path = out_dir / "timeline.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frame", "time", "box_x", "box_y", "box_z", "vel_x", "vel_y", "vel_z"])
        for sample in samples:
            writer.writerow(
                [
                    sample.frame,
                    sample.time,
                    sample.box_x,
                    sample.box_y,
                    sample.box_z,
                    sample.vel_x,
                    sample.vel_y,
                    sample.vel_z,
                ]
            )
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except PermissionError:
        if path.exists():
            path.unlink()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")


def execute_hit_test(config: RuntimeConfig) -> tuple[dict[str, Any], int]:
    return execute_hit_test_entry(config, script_path=None, allow_external_runtime=False)


def execute_hit_test_entry(
    config: RuntimeConfig,
    *,
    script_path: Path | None,
    allow_external_runtime: bool,
) -> tuple[dict[str, Any], int]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    if config.render_video:
        config.render_frames = True
    if config.render_video_fps is not None and config.render_video_fps <= 0:
        raise ValueError("--render-video-fps must be greater than zero")
    if config.render_backend not in {"replicator", "viewport"}:
        raise ValueError("--render-backend must be 'replicator' or 'viewport'")
    if config.render_camera_presets:
        config.render_camera_presets = _normalize_render_camera_presets(config.render_camera_presets)
    elif config.render_frames and config.render_backend == "replicator":
        config.render_camera_presets = ["iso"]

    try:
        if not config.asset.exists():
            raise FileNotFoundError(f"Input asset does not exist: {config.asset}")

        simulation_app_cls, runtime_name = _load_simulation_app()
        if allow_external_runtime and script_path is not None:
            external_result = run_external_runtime(script_path, config)
            if external_result is not None:
                return external_result
            summary_payload = {
                "asset": str(config.asset),
                "test_type": _test_type_for_config(config),
                "result": "blocked",
                "frames": config.frames,
                "hit_mode": config.hit_mode,
                "size_policy": config.size_policy,
                "checks": {
                    "asset_loaded": False,
                    "static_colliders_applied": False,
                    "dynamic_box_created": False,
                    "simulation_advanced": False,
                    "hit_targeted": False,
                    "size_preserved": False,
                    "contact_report_detected": False,
                    "contact_detected_or_inferred": False,
                    "artifacts_written": True,
                },
                "notes": [
                    "Runtime physics validation is authoritative only on Linux with Isaac Sim Docker.",
                    "Pass --runtime-docker-image or --runtime-docker-container; non-Docker runtime dispatch is disabled.",
                ],
            }
            report_payload = {
                "input_usd_path": str(config.asset),
                "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
                "replace_prim": config.replace_prim,
                "hit_mode": config.hit_mode,
                "size_policy": config.size_policy,
                "runtime_policy": "linux_docker_only",
            }
            write_json(config.out_dir / "summary.json", summary_payload)
            write_json(config.out_dir / "runtime_report.json", report_payload)
            write_timeline_csv(config.out_dir, [])
            return summary_payload, 2

        simulation_app = None
        if simulation_app_cls is not None:
            app_config: dict[str, Any] = {"headless": config.headless}
            if config.render_frames:
                app_config.update({"width": config.render_width, "height": config.render_height})
            _progress(
                "simulation-app-create "
                f"headless={config.headless} render_frames={config.render_frames} "
                f"resolution={config.render_width}x{config.render_height if config.render_frames else 'n/a'}"
            )
            simulation_app = simulation_app_cls(app_config)
            _progress("simulation-app-ready")

        _ensure_pxr_loaded()
        scene = build_template_hit_test_stage(config) if config.template_scene is not None else build_hit_test_stage(config)
        _progress(
            "scene-build-done "
            f"test_type={scene.test_type} asset_prim={scene.asset_prim_path} "
            f"box_prim={scene.box_prim_path} box_size={scene.box_size}"
        )
        simulation_status, samples, final_state, notes = run_simulation(
            config,
            scene,
            simulation_app_cls=simulation_app_cls,
            runtime_name=runtime_name,
            simulation_app=simulation_app,
        )
        contact_report = final_state.get("contact_report") if isinstance(final_state, dict) else None
        hit_analysis = analyze_hit(scene, simulation_status, samples, contact_report)
        checks = build_checks(scene, simulation_status, samples, hit_analysis)
        timeline_path = write_timeline_csv(config.out_dir, samples)

        summary_payload = {
            "asset": str(config.asset),
            "test_type": scene.test_type,
            "result": simulation_status,
            "frames": config.frames,
            "hit_mode": scene.hit_mode,
            "size_policy": scene.size_policy,
            "checks": checks,
            "contact_evidence_level": hit_analysis.get("contact_evidence_level"),
            "notes": notes,
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(scene.template_scene_path) if scene.template_scene_path is not None else None,
            "asset_slot_path": scene.asset_prim_path if scene.template_scene_path is not None else None,
            "replaced_prim_path": scene.replaced_prim_path,
            "asset_prim_path": scene.asset_prim_path,
            "box_prim_path": scene.box_prim_path,
            "box_initial_position": list(scene.box_initial_position),
            "box_initial_velocity": list(scene.box_initial_velocity),
            "box_size": scene.box_size,
            "hit_mode": scene.hit_mode,
            "size_policy": scene.size_policy,
            "asset_rotation_y_deg": scene.asset_rotation_y_deg,
            "asset_rotation_z_deg": scene.asset_rotation_z_deg,
            "drop_target_xy": list(scene.drop_target_xy) if scene.drop_target_xy is not None else None,
            "asset_bbox_preserved": scene.asset_bbox_preserved,
            "asset_unit_scale": scene.asset_unit_scale,
            "fit_mode": scene.fit_mode,
            "fit_scale": scene.fit_scale,
            "replaced_bbox_min": list(scene.replaced_bbox_min) if scene.replaced_bbox_min is not None else None,
            "replaced_bbox_max": list(scene.replaced_bbox_max) if scene.replaced_bbox_max is not None else None,
            "asset_bbox_before_align_min": list(scene.asset_bbox_before_align_min),
            "asset_bbox_before_align_max": list(scene.asset_bbox_before_align_max),
            "asset_bbox_min": list(scene.asset_bbox_min),
            "asset_bbox_max": list(scene.asset_bbox_max),
            "ground_prim_path": scene.ground_prim_path,
            "collider_prim_paths": scene.collider_prim_paths,
            "frames": config.frames,
            "fps": config.fps,
            "timeline_csv": str(timeline_path),
            "sampling_summary": {
                "sample_count": len(samples),
                "first_sample": asdict(samples[0]) if samples else None,
                "last_sample": asdict(samples[-1]) if samples else None,
            },
            "final_state": final_state,
            "hit_analysis": hit_analysis,
            "stage_path": str(scene.stage_path),
        }

        write_json(config.out_dir / "summary.json", summary_payload)
        write_json(config.out_dir / "runtime_report.json", report_payload)

        if simulation_app is not None:
            simulation_app.close()

        if simulation_status == "passed":
            return summary_payload, 0
        return summary_payload, 2
    except Exception as exc:  # pragma: no cover - defensive path for runtime env mismatches
        notes = [f"{type(exc).__name__}: {exc}", traceback.format_exc(limit=5)]
        summary_payload = {
            "asset": str(config.asset),
            "test_type": _test_type_for_config(config),
            "result": "error",
            "frames": config.frames,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "checks": {
                "asset_loaded": False,
                "static_colliders_applied": False,
                "dynamic_box_created": False,
                "simulation_advanced": False,
                "hit_targeted": False,
                "size_preserved": False,
                "contact_report_detected": False,
                "contact_detected_or_inferred": False,
                "artifacts_written": True,
            },
            "notes": notes,
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
            "replace_prim": config.replace_prim,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(limit=20),
            },
        }
        write_json(config.out_dir / "summary.json", summary_payload)
        write_json(config.out_dir / "runtime_report.json", report_payload)
        write_timeline_csv(config.out_dir, [])
        return summary_payload, 1
