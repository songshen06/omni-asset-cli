#!/usr/bin/env python3
"""Minimal runtime physics harness for dynamic-box-vs-static-asset hit tests."""

from __future__ import annotations

import csv
import json
import os
import platform
import shutil
import subprocess
import tempfile
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
except ImportError:  # Allows host-side Docker dispatch without local USD Python packages.
    Gf = None  # type: ignore[assignment]
    Usd = None  # type: ignore[assignment]
    UsdGeom = None  # type: ignore[assignment]
    UsdPhysics = None  # type: ignore[assignment]


def _ensure_pxr_loaded() -> None:
    global Gf, Usd, UsdGeom, UsdPhysics
    if all(module is not None for module in (Gf, Usd, UsdGeom, UsdPhysics)):
        return
    from pxr import Gf as _Gf
    from pxr import Usd as _Usd
    from pxr import UsdGeom as _UsdGeom
    from pxr import UsdPhysics as _UsdPhysics

    Gf = _Gf
    Usd = _Usd
    UsdGeom = _UsdGeom
    UsdPhysics = _UsdPhysics


@dataclass
class RuntimeConfig:
    asset: Path
    out_dir: Path
    template_scene: Path | None = None
    replace_prim: str | None = "/World/roomScene/colliders/table"
    hit_mode: str = "side-hit"
    size_policy: str = "template-fit"
    frames: int = 240
    fps: float = 60.0
    headless: bool = True
    runtime_python: str | None = None
    runtime_platform: str = "auto"
    runtime_docker_image: str | None = None
    runtime_docker_container: str | None = None
    docker_workspace: str = "/workspace/omni-asset-cli"
    docker_python: str = "/isaac-sim/python.sh"


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
    drop_target_xy: tuple[float, float] | None
    asset_bbox_preserved: bool
    fit_mode: str | None
    fit_scale: float | None
    replaced_bbox_min: tuple[float, float, float] | None
    replaced_bbox_max: tuple[float, float, float] | None
    asset_bbox_before_align_min: tuple[float, float, float]
    asset_bbox_before_align_max: tuple[float, float, float]
    asset_bbox_min: tuple[float, float, float]
    asset_bbox_max: tuple[float, float, float]


def default_out_dir(asset_path: Path) -> Path:
    return Path("out") / f"{asset_path.stem}_physics_hit"


def _host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    return "linux"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))


def _is_windows_runtime_path(path_value: str) -> bool:
    lower = path_value.lower()
    return lower.endswith(".bat") or lower.endswith(".exe") or ":\\" in path_value or ":/" in path_value


def normalize_runtime_python_path(raw_path: str) -> str:
    if _host_platform() == "linux" and _is_windows_runtime_path(raw_path):
        windows_style = raw_path.replace("/", "\\")
        drive, _, tail = windows_style.partition(":\\")
        if drive and tail:
            return f"/mnt/{drive.lower()}/{tail.replace(chr(92), '/')}"
    return raw_path


def default_windows_runtime_python_wsl() -> str | None:
    if not is_wsl():
        return None

    for candidate in (
        Path("/mnt/c/isaacsim/python.bat"),
        Path("/mnt/c/isaacsim/python.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _wsl_path_convert(path: Path, mode: str) -> str | None:
    try:
        completed = subprocess.run(
            ["wslpath", mode, str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None

    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _convert_path_for_target(path: Path, target_platform: str) -> str:
    resolved = path.resolve()
    host_platform = _host_platform()
    if target_platform == host_platform:
        return str(resolved)
    if host_platform == "linux" and target_platform == "windows":
        converted = _wsl_path_convert(resolved, "-w")
        if converted:
            return converted
    return str(resolved)


def _infer_runtime_platform(runtime_python: str | None, requested_platform: str) -> str:
    if requested_platform in {"linux", "windows"}:
        return requested_platform
    if runtime_python and _is_windows_runtime_path(runtime_python):
        return "windows"
    return _host_platform()


def _candidate_runtime_paths() -> list[str]:
    candidates: list[str] = []

    for env_name in ("OMNI_ASSET_CLI_RUNTIME_PYTHON", "ISAACSIM_PYTHON", "ISAACSIM_PYTHON_EXE"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(value)

    home = Path.home()
    for path in sorted(home.glob(".local/share/ov/pkg/isaac-sim-*/python.sh"), reverse=True):
        candidates.append(str(path))
    for path in sorted(home.glob("isaacsim/python.sh"), reverse=True):
        candidates.append(str(path))

    wsl_windows_runtime = default_windows_runtime_python_wsl()
    if wsl_windows_runtime:
        candidates.append(wsl_windows_runtime)

    # Do not auto-switch from WSL/Linux into Windows Isaac Sim.
    # Cross-platform dispatch stays opt-in through --runtime-python.
    if _host_platform() == "windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            for path in sorted(Path(local_app_data).glob("ov/pkg/isaac-sim-*/python.bat"), reverse=True):
                candidates.append(str(path))
        for path in (
            Path("C:/isaacsim/python.bat"),
            Path("C:/isaacsim/python.exe"),
            Path("C:/Program Files/NVIDIA Corporation/Isaac Sim/python.bat"),
        ):
            if path.exists():
                candidates.append(str(path))

    deduped: list[str] = []
    for value in candidates:
        if value not in deduped:
            deduped.append(value)
    return deduped


def discover_runtime_python(config: RuntimeConfig) -> str | None:
    if config.runtime_python:
        candidate = normalize_runtime_python_path(config.runtime_python)
        if Path(candidate).exists():
            return candidate
        return config.runtime_python

    for candidate in _candidate_runtime_paths():
        if Path(candidate).exists():
            return candidate
    return None


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


def create_input_asset_prim(stage: Usd.Stage, asset_path: Path) -> Usd.Prim:
    asset_root = UsdGeom.Xform.Define(stage, "/World/InputAsset")
    asset_root.GetPrim().GetReferences().AddReference(str(asset_path.resolve()))
    stage.Load(asset_root.GetPrim().GetPath())
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


def _is_gprim(prim: Usd.Prim) -> bool:
    return prim.IsA(UsdGeom.Gprim)


def apply_static_colliders(asset_root: Usd.Prim) -> list[str]:
    collider_paths: list[str] = []

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

    if asset_range.IsEmpty():
        asset_min = Gf.Vec3d(-0.25, -0.25, 0.0)
        asset_max = Gf.Vec3d(0.25, 0.25, 0.5)
    else:
        asset_min = asset_range.GetMin()
        asset_max = asset_range.GetMax()

    span = asset_max - asset_min
    span_x = max(float(span[0]), 0.5)
    span_y = max(float(span[1]), 0.5)
    span_z = max(float(span[2]), 0.5)
    max_span = max(span_x, span_y, span_z)
    cube_size = max(0.2, min(max_span * 0.25, 0.75))
    half_extent = cube_size / 2.0

    start_position = Gf.Vec3d(
        float(asset_min[0]) - cube_size * 3.0,
        float((asset_min[1] + asset_max[1]) / 2.0),
        float(max(cube_size, asset_min[2] + span_z * 0.5)),
    )
    start_velocity = Gf.Vec3f(max(1.5, span_x * 2.0), 0.0, 0.0)

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

    return str(box_prim.GetPath()), _as_tuple(start_position), _as_tuple(start_velocity)


def _asset_span(asset_range: Gf.Range3d) -> tuple[Gf.Vec3d, Gf.Vec3d, Gf.Vec3d]:
    if asset_range.IsEmpty():
        asset_min = Gf.Vec3d(-0.25, -0.25, 0.0)
        asset_max = Gf.Vec3d(0.25, 0.25, 0.5)
    else:
        asset_min = asset_range.GetMin()
        asset_max = asset_range.GetMax()
    return asset_min, asset_max, asset_max - asset_min


def compute_top_drop_box_size(asset_range: Gf.Range3d) -> float:
    _, _, span = _asset_span(asset_range)
    footprint_min = max(min(float(span[0]), float(span[1])), 1e-6)
    max_span = max(float(span[0]), float(span[1]), float(span[2]), 0.1)
    return max(0.08, min(footprint_min * 0.45, max_span * 0.25, 0.75))


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
    cube_size = compute_top_drop_box_size(asset_range)
    half_extent = cube_size / 2.0
    target_x = float((asset_min[0] + asset_max[0]) / 2.0)
    target_y = float((asset_min[1] + asset_max[1]) / 2.0)
    clearance = max(cube_size * 2.0, min(max(float(span[2]), cube_size) * 0.35, 1.5))

    start_position = Gf.Vec3d(
        target_x,
        target_y,
        float(asset_max[2]) + clearance + half_extent,
    )
    start_velocity = Gf.Vec3f(0.0, 0.0, -max(0.2, cube_size * 0.5))

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

    return str(box_prim.GetPath()), _as_tuple(start_position), _as_tuple(start_velocity), cube_size, (target_x, target_y)


def build_hit_test_stage(config: RuntimeConfig) -> SceneBuildResult:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix="omni_asset_cli_physics_hit_"))
    stage_path = stage_dir / "physics_hit_test_stage.usda"
    stage = create_base_stage(stage_path, config.fps)
    ground_prim_path = create_ground_plane(stage)
    asset_prim = create_input_asset_prim(stage, config.asset)
    asset_range_before_align = compute_world_bbox(stage, asset_prim)
    asset_range = align_asset_to_ground(stage, asset_prim)
    collider_paths = apply_static_colliders(asset_prim)
    if config.hit_mode == "top-drop":
        bbox_collider_path = create_bbox_collider(stage, asset_range)
        if bbox_collider_path and bbox_collider_path not in collider_paths:
            collider_paths.append(bbox_collider_path)
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
        drop_target_xy=drop_target_xy,
        asset_bbox_preserved=True,
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
    injection_path = config.replace_prim or slot_path
    box_prim_path = "/World/boxActor"
    replace_target = stage.GetPrimAtPath(injection_path)
    if config.replace_prim is not None and (not replace_target or not replace_target.IsValid()):
        raise RuntimeError(f"Template replacement prim does not exist: {config.replace_prim}")
    replaced_range = compute_world_bbox(stage, replace_target) if config.replace_prim is not None else Gf.Range3d()

    stage.RemovePrim(injection_path)
    injected = UsdGeom.Xform.Define(stage, injection_path)
    injected_prim = injected.GetPrim()
    _clear_xform_ops(injected_prim)
    injected_prim.GetReferences().AddReference(str(config.asset.resolve()))
    stage.Load(injected_prim.GetPath())

    asset_range_before_align = compute_world_bbox(stage, injected_prim)
    asset_bbox_preserved = True
    if config.replace_prim is not None and not replaced_range.IsEmpty() and config.size_policy == "template-fit":
        asset_range, fit_scale = fit_asset_to_replaced_footprint(stage, injected_prim, replaced_range)
        fit_mode = "uniform_footprint_to_replaced_prim"
        asset_bbox_preserved = False
    elif config.replace_prim is not None and not replaced_range.IsEmpty():
        asset_range = place_asset_on_replaced_prim_preserving_size(stage, injected_prim, replaced_range)
        fit_scale = None
        fit_mode = "preserve_size_on_replaced_prim"
    else:
        asset_range = align_asset_to_ground(stage, injected_prim)
        fit_scale = None
        fit_mode = "ground_align"
    collider_paths = apply_static_colliders(injected_prim)

    if config.hit_mode == "top-drop":
        bbox_collider_path = create_bbox_collider(stage, asset_range)
        if bbox_collider_path and bbox_collider_path not in collider_paths:
            collider_paths.append(bbox_collider_path)
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
        box_initial_position = _read_prim_position(stage, box_prim_path)
        box_initial_velocity = _read_box_velocity(stage, box_prim_path)
        box_size = None
        drop_target_xy = None
        test_type = "template_scene_dynamic_box_hits_asset"
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
        asset_prim_path=injection_path,
        replaced_prim_path=config.replace_prim,
        box_prim_path=box_prim_path,
        ground_prim_path="",
        collider_prim_paths=collider_paths,
        box_initial_position=box_initial_position,
        box_initial_velocity=box_initial_velocity,
        box_size=box_size,
        hit_mode=config.hit_mode,
        size_policy=config.size_policy,
        drop_target_xy=drop_target_xy,
        asset_bbox_preserved=asset_bbox_preserved,
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


def _build_external_runtime_command(runtime_python: str, script_path: Path, config: RuntimeConfig) -> list[str]:
    target_platform = _infer_runtime_platform(runtime_python, config.runtime_platform)
    asset_arg = _convert_path_for_target(config.asset, target_platform)
    out_arg = _convert_path_for_target(config.out_dir, target_platform)
    script_arg = _convert_path_for_target(script_path, target_platform)
    template_arg = (
        _convert_path_for_target(config.template_scene, target_platform)
        if config.template_scene is not None
        else None
    )

    command = [
        script_arg,
        asset_arg,
        "--frames",
        str(config.frames),
        "--fps",
        str(config.fps),
        "--out",
        out_arg,
        "--runtime-platform",
        target_platform,
        "--external-runtime-child",
    ]
    if template_arg is not None:
        command.extend(["--template-scene", template_arg])
    if config.replace_prim:
        command.extend(["--replace-prim", config.replace_prim])
    command.extend(["--hit-mode", config.hit_mode])
    command.extend(["--size-policy", config.size_policy])
    if not config.headless:
        command.append("--no-headless")

    if target_platform == "windows":
        runtime_arg = runtime_python
        if _host_platform() == "linux":
            runtime_arg = _convert_path_for_target(Path(runtime_python), "windows")
        return ["cmd.exe", "/C", runtime_arg, *command]

    return [runtime_python, *command]


def _path_in_docker(path: Path, config: RuntimeConfig) -> str:
    resolved = path.resolve()
    root = repo_root().resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Docker runtime paths must be inside the repository mount: path={resolved}, repo={root}"
        ) from exc
    return str(Path(config.docker_workspace) / relative)


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
        "--runtime-platform",
        "linux",
        "--external-runtime-child",
    ]
    if config.template_scene is not None:
        command.extend(["--template-scene", _path_in_docker(config.template_scene, config)])
    if config.replace_prim:
        command.extend(["--replace-prim", config.replace_prim])
    command.extend(["--hit-mode", config.hit_mode])
    command.extend(["--size-policy", config.size_policy])
    if not config.headless:
        command.append("--no-headless")
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


def _prepare_docker_output_dir(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        out_dir.chmod(0o777)
    except PermissionError:
        pass


def _load_summary_payload(out_dir: Path) -> dict[str, Any] | None:
    summary_path = out_dir / "summary.json"
    if not summary_path.exists():
        return None
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _test_type_for_config(config: RuntimeConfig) -> str:
    if config.template_scene is not None and config.hit_mode == "top-drop":
        return "template_scene_top_drop_box_hits_asset"
    if config.template_scene is not None:
        return "template_scene_dynamic_box_hits_asset"
    if config.hit_mode == "top-drop":
        return "top_drop_box_hits_static_asset"
    return "dynamic_box_hits_static_asset"
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _clear_runtime_artifacts(out_dir: Path) -> None:
    for name in ("summary.json", "runtime_report.json", "timeline.csv"):
        path = out_dir / name
        if path.exists():
            path.unlink()


def run_external_runtime(script_path: Path, config: RuntimeConfig) -> tuple[dict[str, Any], int] | None:
    if config.runtime_docker_container or config.runtime_docker_image:
        _prepare_docker_output_dir(config.out_dir)
        _clear_runtime_artifacts(config.out_dir)
        command = (
            _build_docker_exec_command(script_path, config)
            if config.runtime_docker_container
            else _build_docker_run_command(script_path, config)
        )
        completed = subprocess.run(command, check=False)
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

        return payload, completed.returncode

    runtime_python = discover_runtime_python(config)
    if runtime_python is None:
        return None

    _clear_runtime_artifacts(config.out_dir)
    command = _build_external_runtime_command(runtime_python, script_path, config)
    completed = subprocess.run(command, check=False)
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
                "contact_detected_or_inferred": False,
                "artifacts_written": True,
            },
            "notes": [
                f"External runtime command failed to produce summary.json: returncode={completed.returncode}",
                f"runtime_python={runtime_python}",
            ],
        }
        report_payload = {
            "input_usd_path": str(config.asset),
            "template_scene_path": str(config.template_scene) if config.template_scene is not None else None,
            "replace_prim": config.replace_prim,
            "hit_mode": config.hit_mode,
            "size_policy": config.size_policy,
            "external_runtime": {
                "runtime_python": runtime_python,
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
        payload["notes"].append(f"external_runtime_python={runtime_python}")

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
    owns_simulation_app = simulation_app is None
    if simulation_app is None:
        simulation_app = simulation_app_cls({"headless": config.headless})

    try:
        import omni.timeline  # type: ignore
        import omni.usd  # type: ignore

        usd_context = omni.usd.get_context()
        opened = usd_context.open_stage(str(scene.stage_path))
        if opened is False:
            raise RuntimeError(f"Failed to open stage: {scene.stage_path}")

        for _ in range(8):
            simulation_app.update()

        stage = usd_context.get_stage()
        if stage is None:
            raise RuntimeError("Omniverse USD context did not return a stage.")

        timeline = omni.timeline.get_timeline_interface()
        timeline.set_current_time(0.0)
        timeline.play()

        for frame in range(config.frames):
            simulation_app.update()
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

        timeline.stop()
        final_sample = samples[-1] if samples else None
        final_state = {
            "sample_count": len(samples),
            "last_frame": final_sample.frame if final_sample else None,
            "box_position": [final_sample.box_x, final_sample.box_y, final_sample.box_z] if final_sample else None,
            "box_velocity": [final_sample.vel_x, final_sample.vel_y, final_sample.vel_z] if final_sample else None,
        }
        return "passed", samples, final_state, notes
    finally:
        if owns_simulation_app:
            simulation_app.close()


def _xy_inside_asset_bbox(scene: SceneBuildResult, x: float, y: float, margin: float = 0.0) -> bool:
    min_x, min_y, _ = scene.asset_bbox_min
    max_x, max_y, _ = scene.asset_bbox_max
    return (min_x - margin) <= x <= (max_x + margin) and (min_y - margin) <= y <= (max_y + margin)


def analyze_hit(scene: SceneBuildResult, simulation_status: str, samples: list[TimelineSample]) -> dict[str, Any]:
    hit_targeted = True
    contact_inferred = False
    box_descended = False
    min_box_z = None
    final_box_z = None

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
        box_descended = min_box_z < first.box_z

        if scene.hit_mode == "top-drop" and scene.box_size is not None:
            asset_top = scene.asset_bbox_max[2]
            contact_plane_z = asset_top + (scene.box_size / 2.0)
            z_reached_asset = min_box_z <= contact_plane_z + max(scene.box_size * 0.25, 0.02)
            xy_targeted = hit_targeted and _xy_inside_asset_bbox(scene, last.box_x, last.box_y, margin=scene.box_size)
            contact_inferred = simulation_status == "passed" and box_descended and z_reached_asset and xy_targeted
        else:
            contact_inferred = simulation_status == "passed" and len(samples) > 0

    return {
        "hit_targeted": hit_targeted,
        "size_preserved": scene.asset_bbox_preserved,
        "contact_detected_or_inferred": contact_inferred,
        "box_descended": box_descended,
        "min_box_z": min_box_z,
        "final_box_z": final_box_z,
        "method": "bbox_motion_heuristic",
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
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def execute_hit_test(config: RuntimeConfig) -> tuple[dict[str, Any], int]:
    return execute_hit_test_entry(config, script_path=None, allow_external_runtime=False)


def execute_hit_test_entry(
    config: RuntimeConfig,
    *,
    script_path: Path | None,
    allow_external_runtime: bool,
) -> tuple[dict[str, Any], int]:
    config.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if not config.asset.exists():
            raise FileNotFoundError(f"Input asset does not exist: {config.asset}")

        simulation_app_cls, runtime_name = _load_simulation_app()
        if simulation_app_cls is None and allow_external_runtime and script_path is not None:
            external_result = run_external_runtime(script_path, config)
            if external_result is not None:
                return external_result

        simulation_app = None
        if simulation_app_cls is not None:
            simulation_app = simulation_app_cls({"headless": config.headless})

        _ensure_pxr_loaded()
        scene = build_template_hit_test_stage(config) if config.template_scene is not None else build_hit_test_stage(config)
        simulation_status, samples, final_state, notes = run_simulation(
            config,
            scene,
            simulation_app_cls=simulation_app_cls,
            runtime_name=runtime_name,
            simulation_app=simulation_app,
        )
        hit_analysis = analyze_hit(scene, simulation_status, samples)
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
            "drop_target_xy": list(scene.drop_target_xy) if scene.drop_target_xy is not None else None,
            "asset_bbox_preserved": scene.asset_bbox_preserved,
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
