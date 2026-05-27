#!/usr/bin/env python3
"""Render a corrected dynamic asset drop onto the mini test table."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ASSET_PATH = "/World/FallingAsset"
ASSET_REFERENCE_PATH = f"{ASSET_PATH}/ReferencedAsset"
BBOX_DEBUG_PATH = f"{ASSET_PATH}/DebugBBox"
CAMERA_PATH = "/World/DropCamera"
CAMERA_ROOT_PATH = "/World/DropCameras"
TABLE_PATH = "/World/roomScene/colliders/table/tableTopActor"
CAMERA_PRESETS = ("drop", "front", "back", "left", "right", "side", "top", "iso")
MATERIAL_MODES = ("material", "transparent")
PROGRESS_LOG_PATH: Path | None = None


def _progress(message: str) -> None:
    print(f"[asset-table-drop] {message}", flush=True)
    if PROGRESS_LOG_PATH is not None:
        try:
            with PROGRESS_LOG_PATH.open("a", encoding="utf-8") as stream:
                stream.write(f"progress {message}\n")
        except Exception:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a dynamic USD asset falling onto the mini test table.")
    parser.add_argument("asset", type=Path, help="USD asset to drop")
    parser.add_argument("--template-scene", type=Path, default=Path("examples/mini_test.usda"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--drop-height", type=float, default=50.0, help="Distance above table top in stage units")
    parser.add_argument("--asset-scale", type=float, default=1.5, help="Display scale applied to the corrected asset wrapper")
    parser.add_argument(
        "--asset-rotation-y-deg",
        type=float,
        default=0.0,
        help="Initial local Y-axis rotation applied to the referenced asset before rendering.",
    )
    parser.add_argument(
        "--asset-rotation-z-deg",
        type=float,
        default=0.0,
        help="Initial local Z-axis rotation applied to the referenced asset before rendering.",
    )
    parser.add_argument("--render-every-n-frames", type=int, default=1)
    parser.add_argument("--camera-distance-scale", type=float, default=1.75)
    parser.add_argument("--camera-elevation-deg", type=float, default=14.0)
    parser.add_argument(
        "--camera-azimuth-deg",
        type=float,
        default=None,
        help="Optional camera orbit azimuth in degrees; omitted preserves the original drop-camera angle",
    )
    parser.add_argument(
        "--camera-preset",
        action="append",
        default=[],
        help="Camera preset to render. Repeat or pass comma-separated values. Choices: all, drop, front, back, left, right, side, top, iso.",
    )
    parser.add_argument("--camera-focal-length", type=float, default=28.0)
    parser.add_argument("--render-rt-subframes", type=int, default=4)
    parser.add_argument("--render-wait-updates", type=int, default=20)
    parser.add_argument("--render-video", action="store_true", help="Encode rendered PNG frames to mp4")
    parser.add_argument("--render-video-fps", type=float, default=None)
    parser.add_argument("--render-video-crf", type=int, default=23)
    parser.add_argument("--gravity-magnitude", type=float, default=981.0)
    parser.add_argument(
        "--initial-angular-velocity",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        default=None,
        help="Initial rigid-body angular velocity in stage units per second; defaults to template /World/boxActor",
    )
    parser.add_argument(
        "--initial-linear-velocity",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        default=None,
        help="Initial rigid-body linear velocity in stage units per second; defaults to template /World/boxActor",
    )
    parser.add_argument("--physics-driven", action="store_true", help="Use live PhysX stepping instead of deterministic kinematic video motion")
    parser.add_argument(
        "--physics-updates-per-frame",
        type=int,
        default=0,
        help="Isaac app updates to advance before each rendered physics frame; 0 chooses an fps-based default",
    )
    parser.add_argument("--keep-stage", action="store_true")
    parser.add_argument(
        "--render-material-mode",
        action="append",
        default=[],
        help="Visual material mode to render. Repeat or pass comma-separated values. Choices: all, material, transparent.",
    )
    parser.add_argument("--override-preview-material", action="store_true")
    parser.add_argument(
        "--bbox-only-material",
        action="store_true",
        help="Hide the asset render geometry and render a translucent bbox that follows the same PhysX motion",
    )
    return parser.parse_args()


def _as_tuple3(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _read_vec3_attr(attr: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        value = attr.Get()
    except Exception:
        value = None
    if value is None:
        return default
    return _as_tuple3(value)


def _bbox_tuple(value: Any) -> dict[str, list[float]] | None:
    if value.IsEmpty():
        return None
    return {
        "min": list(_as_tuple3(value.GetMin())),
        "max": list(_as_tuple3(value.GetMax())),
        "size": list(_as_tuple3(value.GetSize())),
    }


def _clear_xform_ops(prim: Any) -> Any:
    from pxr import UsdGeom

    xformable = UsdGeom.Xformable(prim)
    if hasattr(xformable, "RemoveXformOp"):
        for op in list(xformable.GetOrderedXformOps()):
            xformable.RemoveXformOp(op)
    else:
        xformable.SetXformOpOrder([])
    return xformable


def _bbox_diagonal(value: Any) -> float:
    if value.IsEmpty():
        return 1.0
    size = value.GetSize()
    return math.sqrt(float(size[0]) ** 2 + float(size[1]) ** 2 + float(size[2]) ** 2)


def _line_width(bbox: Any) -> float:
    return max(_bbox_diagonal(bbox) * 0.004, 0.01)


def _compute_world_bbox(stage: Any, prim: Any) -> Any:
    from pxr import UsdGeom

    cache = UsdGeom.BBoxCache(
        0,
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    return cache.ComputeWorldBound(prim).ComputeAlignedRange()


def _asset_units_to_stage_scale(asset_path: Path, target_stage: Any) -> float:
    from pxr import Usd, UsdGeom

    asset_stage = Usd.Stage.Open(str(asset_path.resolve()))
    if asset_stage is None:
        return 1.0
    asset_meters_per_unit = UsdGeom.GetStageMetersPerUnit(asset_stage)
    target_meters_per_unit = UsdGeom.GetStageMetersPerUnit(target_stage)
    if asset_meters_per_unit <= 0 or target_meters_per_unit <= 0:
        return 1.0
    return float(asset_meters_per_unit / target_meters_per_unit)


def _compute_relative_bbox(stage: Any, prim: Any, ancestor: Any) -> Any:
    from pxr import UsdGeom

    cache = UsdGeom.BBoxCache(
        0,
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    return cache.ComputeRelativeBound(prim, ancestor).ComputeAlignedRange()


def _look_at_matrix(eye: Any, target: Any) -> Any:
    from pxr import Gf

    direction = (target - eye).GetNormalized()
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    right = Gf.Cross(direction, up).GetNormalized()
    if right.GetLength() == 0:
        up = Gf.Vec3d(0.0, 1.0, 0.0)
        right = Gf.Cross(direction, up).GetNormalized()
    true_up = Gf.Cross(right, direction).GetNormalized()
    return Gf.Matrix4d(
        right[0], right[1], right[2], 0.0,
        true_up[0], true_up[1], true_up[2], 0.0,
        -direction[0], -direction[1], -direction[2], 0.0,
        eye[0], eye[1], eye[2], 1.0,
    )


def _normalize_camera_presets(values: list[str]) -> list[str]:
    presets: list[str] = []
    for raw_value in values:
        for raw_item in str(raw_value).split(","):
            item = raw_item.strip().lower()
            if not item:
                continue
            if item == "all":
                for preset in CAMERA_PRESETS:
                    if preset not in presets:
                        presets.append(preset)
                continue
            if item not in CAMERA_PRESETS:
                raise ValueError(f"Unsupported camera preset: {item}")
            if item not in presets:
                presets.append(item)
    return presets or ["drop"]


def _normalize_material_modes(values: list[str]) -> list[str]:
    modes: list[str] = []
    for raw_value in values:
        for raw_item in str(raw_value).split(","):
            item = raw_item.strip().lower()
            if not item:
                continue
            if item == "all":
                for mode in MATERIAL_MODES:
                    if mode not in modes:
                        modes.append(mode)
                continue
            if item not in MATERIAL_MODES:
                raise ValueError(f"Unsupported material mode: {item}")
            if item not in modes:
                modes.append(item)
    return modes or ["material"]


def _camera_name_for_preset(preset: str) -> str:
    return "drop_camera" if preset == "drop" else preset


def _camera_offset(preset: str, radius: float, args: argparse.Namespace) -> Any:
    from pxr import Gf

    elevation = math.radians(args.camera_elevation_deg)
    distance = radius * args.camera_distance_scale
    horizontal_distance = distance * math.hypot(0.85, 1.05)
    z = math.sin(elevation) * distance + radius * 0.08
    if preset == "drop":
        if args.camera_azimuth_deg is None:
            return Gf.Vec3d(distance * 0.85, -distance * 1.05, z)
        azimuth = math.radians(args.camera_azimuth_deg)
        return Gf.Vec3d(math.cos(azimuth) * horizontal_distance, math.sin(azimuth) * horizontal_distance, z)
    if preset == "front":
        return Gf.Vec3d(0.0, -horizontal_distance, z)
    if preset == "back":
        return Gf.Vec3d(0.0, horizontal_distance, z)
    if preset == "left":
        return Gf.Vec3d(-horizontal_distance, 0.0, z)
    if preset in {"right", "side"}:
        return Gf.Vec3d(horizontal_distance, 0.0, z)
    if preset == "top":
        return Gf.Vec3d(0.0, -max(radius * 0.02, 0.5), max(distance * 1.65, radius))
    return Gf.Vec3d(horizontal_distance * 0.72, -horizontal_distance * 0.72, z + radius * 0.22)


def _add_camera(stage: Any, target: Any, radius: float, args: argparse.Namespace, preset: str, index: int) -> dict[str, str]:
    from pxr import Gf, Sdf, UsdGeom

    eye_offset = _camera_offset(preset, radius, args)
    eye = target + eye_offset
    matrix = _look_at_matrix(eye, target)
    clipping = Gf.Vec2f(0.1, max(radius * 30.0, 1000.0))

    camera_name = _camera_name_for_preset(preset)
    camera_path = CAMERA_PATH if index == 0 else f"{CAMERA_ROOT_PATH}/{camera_name}"
    for path_value in (camera_path, "/World/Camera") if index == 0 else (camera_path,):
        camera = UsdGeom.Camera.Define(stage, Sdf.Path(path_value))
        _clear_xform_ops(camera.GetPrim()).AddTransformOp().Set(matrix)
        camera.CreateFocalLengthAttr(float(args.camera_focal_length))
        camera.CreateClippingRangeAttr(clipping)
    return {"name": camera_name, "preset": preset, "camera_path": camera_path}


def _add_cameras(stage: Any, target: Any, radius: float, args: argparse.Namespace) -> list[dict[str, str]]:
    return [
        _add_camera(stage, target, radius, args, preset, index)
        for index, preset in enumerate(_normalize_camera_presets(args.camera_preset))
    ]


def _set_gravity(stage: Any, magnitude: float) -> None:
    from pxr import Sdf, UsdPhysics

    physics_scene = UsdPhysics.Scene.Get(stage, Sdf.Path("/World/physicsScene"))
    if physics_scene:
        physics_scene.CreateGravityMagnitudeAttr().Set(float(magnitude))


def _remove_non_test_render_geometry(stage: Any) -> list[str]:
    remove_roots = (
        "/World/roomScene/colliders/floor",
        "/World/roomScene/colliders/walls",
        "/World/roomScene/colliders/windows",
        "/World/roomScene/renderables",
        "/World/originGuide",
        "/World/DomeLightRoom",
    )
    removed: list[str] = []
    for raw_root in remove_roots:
        root = stage.GetPrimAtPath(raw_root)
        if not root or not root.IsValid():
            continue
        stage.RemovePrim(root.GetPath())
        removed.append(raw_root)

    room_scene = stage.GetPrimAtPath("/World/roomScene")
    if room_scene and room_scene.IsValid():
        for child in list(room_scene.GetChildren()):
            child_path = str(child.GetPath())
            if child_path == "/World/roomScene/colliders":
                continue
            stage.RemovePrim(child.GetPath())
            removed.append(child_path)

    colliders = stage.GetPrimAtPath("/World/roomScene/colliders")
    if colliders and colliders.IsValid():
        for child in list(colliders.GetChildren()):
            child_path = str(child.GetPath())
            if child_path == "/World/roomScene/colliders/table":
                continue
            stage.RemovePrim(child.GetPath())
            removed.append(child_path)
    return removed


def _hide_non_test_render_geometry(stage: Any) -> list[str]:
    # Kept as a compatibility wrapper for existing summary field names.
    return _remove_non_test_render_geometry(stage)


def _prepare_clean_tabletop(stage: Any) -> list[str]:
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    removed: list[str] = []
    table_root = stage.GetPrimAtPath("/World/roomScene/colliders/table")
    if table_root and table_root.IsValid():
        for child in list(table_root.GetChildren()):
            if str(child.GetPath()) == TABLE_PATH:
                continue
            stage.RemovePrim(child.GetPath())
            removed.append(str(child.GetPath()))

    table_top = stage.GetPrimAtPath(TABLE_PATH)
    if table_top and table_top.IsValid():
        material = UsdShade.Material.Define(stage, Sdf.Path("/World/Looks/WarmWoodTableTop"))
        shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/Looks/WarmWoodTableTop/PreviewSurface"))
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.64, 0.46, 0.27))
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.82)
        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI.Apply(table_top).Bind(material)

        grain_root_path = Sdf.Path("/World/CleanTableWoodGrain")
        if stage.GetPrimAtPath(grain_root_path):
            stage.RemovePrim(grain_root_path)
        UsdGeom.Xform.Define(stage, grain_root_path)

        grain_material = UsdShade.Material.Define(stage, Sdf.Path("/World/Looks/WarmWoodGrain"))
        grain_shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/Looks/WarmWoodGrain/PreviewSurface"))
        grain_shader.CreateIdAttr("UsdPreviewSurface")
        grain_shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.24, 0.14, 0.07))
        grain_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.9)
        grain_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        grain_material.CreateSurfaceOutput().ConnectToSource(grain_shader.ConnectableAPI(), "surface")

        bbox = _compute_world_bbox(stage, table_top)
        if not bbox.IsEmpty():
            minimum = bbox.GetMin()
            maximum = bbox.GetMax()
            min_x = float(minimum[0]) + 8.0
            max_x = float(maximum[0]) - 8.0
            min_y = float(minimum[1]) + 7.0
            max_y = float(maximum[1]) - 7.0
            top_z = float(maximum[2]) + 0.08
            line_count = 18
            point_count = 9
            for line_index in range(line_count):
                t = line_index / max(line_count - 1, 1)
                base_y = min_y + (max_y - min_y) * t
                points = []
                for point_index in range(point_count):
                    u = point_index / max(point_count - 1, 1)
                    x = min_x + (max_x - min_x) * u
                    wave = math.sin(u * math.pi * 4.0 + line_index * 0.73) * 1.6
                    drift = math.sin(u * math.pi * 1.5 + line_index * 0.31) * 0.8
                    y = base_y + wave + drift
                    points.append(Gf.Vec3f(x, y, top_z))
                curve = UsdGeom.BasisCurves.Define(stage, grain_root_path.AppendChild(f"Grain_{line_index:02d}"))
                curve.CreateTypeAttr("linear")
                curve.CreateCurveVertexCountsAttr([len(points)])
                curve.CreatePointsAttr(points)
                curve.CreateWidthsAttr([0.38 + (line_index % 3) * 0.08])
                curve.GetPrim().CreateAttribute("primvars:doNotCastShadows", Sdf.ValueTypeNames.Bool).Set(True)
                UsdShade.MaterialBindingAPI.Apply(curve.GetPrim()).Bind(grain_material)
    return removed


def _disable_asset_lights(stage: Any, asset_prim: Any) -> list[str]:
    from pxr import Usd, UsdLux

    disabled: list[str] = []
    for prim in Usd.PrimRange(asset_prim):
        if prim == asset_prim:
            continue
        is_light = False
        try:
            is_light = bool(prim.IsA(UsdLux.LightAPI))
        except Exception:
            is_light = False
        if not is_light and prim.GetTypeName() not in {"DomeLight", "DistantLight", "RectLight", "SphereLight", "DiskLight"}:
            continue
        prim.SetActive(False)
        disabled.append(str(prim.GetPath()))
    return disabled


def _ensure_clean_lighting(stage: Any) -> None:
    from pxr import Gf, Sdf, UsdGeom, UsdLux

    dome = UsdLux.DomeLight.Define(stage, Sdf.Path("/World/CleanRenderDomeLight"))
    dome.CreateIntensityAttr(350.0)
    dome.CreateColorAttr(Gf.Vec3f(1.0, 1.0, 1.0))

    key = UsdLux.DistantLight.Define(stage, Sdf.Path("/World/CleanRenderKeyLight"))
    key.CreateIntensityAttr(450.0)
    key.CreateAngleAttr(0.45)
    xform = UsdGeom.Xformable(key.GetPrim())
    if not xform.GetOrderedXformOps():
        xform.AddRotateXYZOp().Set(Gf.Vec3f(-45.0, 0.0, 35.0))


def _wait_for_stage_ready(context: Any, stage_path: Path, app: Any, max_updates: int = 240) -> Any:
    expected = str(stage_path)
    last_identifier = ""
    for _ in range(max_updates):
        app.update()
        stage = context.get_stage()
        if stage is None:
            continue
        try:
            last_identifier = str(stage.GetRootLayer().identifier)
        except Exception:
            last_identifier = ""
        asset = stage.GetPrimAtPath(ASSET_PATH)
        table = stage.GetPrimAtPath(TABLE_PATH)
        if asset and asset.IsValid() and table and table.IsValid():
            return stage
    raise RuntimeError(f"Stage did not become ready for render: {expected} last_identifier={last_identifier}")


def _clean_live_render_stage(stage: Any) -> dict[str, Any]:
    removed_background = _hide_non_test_render_geometry(stage)
    removed_table = _prepare_clean_tabletop(stage)
    remaining_room_children: list[str] = []
    room_scene = stage.GetPrimAtPath("/World/roomScene")
    if room_scene and room_scene.IsValid():
        remaining_room_children = [str(child.GetPath()) for child in room_scene.GetChildren()]
    remaining_collider_children: list[str] = []
    colliders = stage.GetPrimAtPath("/World/roomScene/colliders")
    if colliders and colliders.IsValid():
        remaining_collider_children = [str(child.GetPath()) for child in colliders.GetChildren()]
    return {
        "removed_background_paths": removed_background,
        "removed_table_paths": removed_table,
        "remaining_room_children": remaining_room_children,
        "remaining_collider_children": remaining_collider_children,
    }


def _strip_dynamic_physics_apis(asset_prim: Any) -> list[str]:
    from pxr import Usd, UsdPhysics

    try:
        from pxr import PhysxSchema
    except Exception:
        PhysxSchema = None  # type: ignore[assignment]

    stripped: list[str] = []
    for prim in Usd.PrimRange(asset_prim):
        if not prim.IsActive() or not prim.IsDefined():
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


def _apply_dynamic_physics(stage: Any, asset_prim: Any, args: argparse.Namespace) -> list[str]:
    from pxr import Gf, UsdGeom, UsdPhysics

    stripped_dynamic_paths = _strip_dynamic_physics_apis(asset_prim)
    rigid_body = UsdPhysics.RigidBodyAPI.Apply(asset_prim)
    rigid_body.CreateVelocityAttr().Set(Gf.Vec3f(*[float(value) for value in args.initial_linear_velocity]))
    rigid_body.CreateAngularVelocityAttr().Set(Gf.Vec3f(*[float(value) for value in args.initial_angular_velocity]))
    try:
        from pxr import PhysxSchema

        physx_body = PhysxSchema.PhysxRigidBodyAPI.Apply(asset_prim)
        physx_body.CreateLinearDampingAttr().Set(0.0)
        physx_body.CreateAngularDampingAttr().Set(0.0)
        physx_body.CreateSleepThresholdAttr().Set(0.0)
        physx_body.CreateStabilizationThresholdAttr().Set(0.0)
        physx_body.CreateMaxAngularVelocityAttr().Set(10000.0)
        physx_body.CreateEnableGyroscopicForcesAttr().Set(True)
    except Exception:
        pass
    mass = UsdPhysics.MassAPI.Apply(asset_prim)
    mass.CreateMassAttr().Set(0.25)
    mass.CreateCenterOfMassAttr().Set(Gf.Vec3f(0.0, 0.0, 0.0))
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if prim.IsA(UsdGeom.Mesh):
            UsdPhysics.CollisionAPI.Apply(prim)
            try:
                mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
                mesh_collision.CreateApproximationAttr().Set("convexDecomposition")
            except Exception:
                pass
    return stripped_dynamic_paths


def _bind_asset_preview_material(stage: Any, asset_prim: Any) -> int:
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    material = UsdShade.Material.Define(stage, Sdf.Path("/World/Looks/FallingAssetRed"))
    shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/Looks/FallingAssetRed/PreviewSurface"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0, 0.12, 0.05))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.35)
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    bound = 0
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if prim.IsA(UsdGeom.Mesh):
            binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants, UsdShade.Tokens.full)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants, UsdShade.Tokens.preview)
            bound += 1
    return bound


def _material(
    stage: Any,
    path: str,
    color: tuple[float, float, float],
    emissive: bool = False,
    opacity: float = 1.0,
) -> Any:
    from pxr import Gf, Sdf, UsdShade

    material = UsdShade.Material.Define(stage, Sdf.Path(path))
    shader = UsdShade.Shader.Define(stage, Sdf.Path(path).AppendChild("PreviewSurface"))
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.28)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(float(opacity))
    if emissive:
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _bind_ghost_asset_material(stage: Any, asset_prim: Any) -> int:
    from pxr import Sdf, Usd, UsdGeom, UsdShade

    material = _material(stage, "/World/Looks/FallingAssetGhost", (0.16, 0.68, 1.0), opacity=0.42)
    bound = 0
    for prim in Usd.PrimRange(asset_prim):
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        for prop in list(prim.GetProperties()):
            if prop.GetName().startswith("material:binding"):
                prim.RemoveProperty(prop.GetName())
        if prim.IsA(UsdGeom.Mesh) or prim.GetTypeName() == "GeomSubset":
            prim.CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray).Set([(0.16, 0.68, 1.0)])
            prim.CreateAttribute("primvars:displayOpacity", Sdf.ValueTypeNames.FloatArray).Set([0.42])
            binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants, UsdShade.Tokens.full)
            binding_api.Bind(material, UsdShade.Tokens.strongerThanDescendants, UsdShade.Tokens.preview)
            bound += 1
    return bound


def _bbox_edge_points(minimum: Any, maximum: Any) -> list[Any]:
    from pxr import Gf

    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    corners = [
        Gf.Vec3f(x0, y0, z0),
        Gf.Vec3f(x1, y0, z0),
        Gf.Vec3f(x1, y1, z0),
        Gf.Vec3f(x0, y1, z0),
        Gf.Vec3f(x0, y0, z1),
        Gf.Vec3f(x1, y0, z1),
        Gf.Vec3f(x1, y1, z1),
        Gf.Vec3f(x0, y1, z1),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    return [corners[index] for edge in edges for index in edge]


def _add_bbox_curves(
    stage: Any,
    path: str,
    bbox: Any,
    color: tuple[float, float, float],
    width: float,
) -> str | None:
    from pxr import Gf, Sdf, UsdGeom

    if bbox.IsEmpty():
        return None
    curves = UsdGeom.BasisCurves.Define(stage, Sdf.Path(path))
    curves.CreateTypeAttr("linear")
    curves.CreateCurveVertexCountsAttr([2] * 12)
    curves.CreatePointsAttr(_bbox_edge_points(bbox.GetMin(), bbox.GetMax()))
    curves.CreateWidthsAttr([width])
    curves.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    return str(curves.GetPath())


def _add_axis_line(
    stage: Any,
    path: str,
    points: list[Any],
    color: tuple[float, float, float],
    width: float,
) -> None:
    from pxr import Gf, Sdf, UsdGeom

    curves = UsdGeom.BasisCurves.Define(stage, Sdf.Path(path))
    curves.CreateTypeAttr("linear")
    curves.CreateCurveVertexCountsAttr([len(points)])
    curves.CreatePointsAttr(points)
    curves.CreateWidthsAttr([width])
    curves.CreateDisplayColorAttr([Gf.Vec3f(*color)])


def _find_collider_prims(asset_prim: Any) -> list[Any]:
    from pxr import UsdPhysics

    colliders: list[Any] = []
    for prim in asset_prim.GetStage().Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            colliders.append(prim)
    return colliders


def _add_bbox_debug_geometry(stage: Any, asset_prim: Any, referenced_asset_prim: Any) -> dict[str, Any]:
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    bbox = _compute_relative_bbox(stage, referenced_asset_prim, asset_prim)
    if bbox.IsEmpty():
        raise RuntimeError("Could not compute referenced asset bbox for debug geometry.")

    overlay = UsdGeom.Xform.Define(stage, Sdf.Path(BBOX_DEBUG_PATH))
    overlay.GetPrim().SetSpecifier(Sdf.SpecifierDef)

    width = _line_width(bbox)
    asset_bbox_path = _add_bbox_curves(stage, f"{BBOX_DEBUG_PATH}/AssetBBox", bbox, (0.1, 0.55, 1.0), width)
    collider_paths = []
    collider_bbox_union = Gf.Range3d()
    for index, prim in enumerate(_find_collider_prims(referenced_asset_prim)):
        collider_bbox = _compute_relative_bbox(stage, prim, asset_prim)
        if collider_bbox.IsEmpty():
            continue
        collider_bbox_union.UnionWith(collider_bbox)
        curve_path = _add_bbox_curves(
            stage,
            f"{BBOX_DEBUG_PATH}/ColliderBBox_{index:02d}",
            collider_bbox,
            (1.0, 0.55, 0.05),
            width * 1.25,
        )
        if curve_path:
            collider_paths.append({"prim": str(prim.GetPath()), "overlay": curve_path, "bbox": _bbox_tuple(collider_bbox)})

    bbox_center = (bbox.GetMin() + bbox.GetMax()) * 0.5
    diagonal = _bbox_diagonal(bbox)
    marker_radius = max(diagonal * 0.085, 0.16)
    marker = UsdGeom.Sphere.Define(stage, f"{BBOX_DEBUG_PATH}/CenterMarker")
    marker.CreateRadiusAttr(marker_radius)
    marker.AddTranslateOp().Set(bbox_center)
    marker_material = _material(stage, "/World/Looks/FallingAssetCenterMarker", (1.0, 0.92, 0.02), emissive=True)
    UsdShade.MaterialBindingAPI.Apply(marker.GetPrim()).Bind(marker_material)

    min_z = float(bbox.GetMin()[2])
    max_z = float(bbox.GetMax()[2])
    cross = diagonal * 0.16
    marker_width = width * 2.2
    _add_axis_line(
        stage,
        f"{BBOX_DEBUG_PATH}/CenterVerticalAxis",
        [Gf.Vec3f(bbox_center[0], bbox_center[1], min_z), Gf.Vec3f(bbox_center[0], bbox_center[1], max_z)],
        (1.0, 0.92, 0.02),
        marker_width,
    )
    _add_axis_line(
        stage,
        f"{BBOX_DEBUG_PATH}/CenterCrossX",
        [
            Gf.Vec3f(bbox_center[0] - cross, bbox_center[1], bbox_center[2]),
            Gf.Vec3f(bbox_center[0] + cross, bbox_center[1], bbox_center[2]),
        ],
        (1.0, 0.96, 0.12),
        marker_width,
    )
    _add_axis_line(
        stage,
        f"{BBOX_DEBUG_PATH}/CenterCrossY",
        [
            Gf.Vec3f(bbox_center[0], bbox_center[1] - cross, bbox_center[2]),
            Gf.Vec3f(bbox_center[0], bbox_center[1] + cross, bbox_center[2]),
        ],
        (1.0, 0.96, 0.12),
        marker_width,
    )
    _add_axis_line(
        stage,
        f"{BBOX_DEBUG_PATH}/CenterCrossZ",
        [
            Gf.Vec3f(bbox_center[0], bbox_center[1], bbox_center[2] - cross),
            Gf.Vec3f(bbox_center[0], bbox_center[1], bbox_center[2] + cross),
        ],
        (1.0, 0.96, 0.12),
        marker_width,
    )

    ghost_mesh_count = _bind_ghost_asset_material(stage, asset_prim)
    return {
        "bbox_debug_path": BBOX_DEBUG_PATH,
        "bbox_debug_local_bbox": _bbox_tuple(bbox),
        "bbox_debug_style": "setup_orbit_ghost_mesh_with_bbox_curves",
        "bbox_debug_ghost_opacity": 0.52,
        "bbox_debug_ghost_mesh_count": ghost_mesh_count,
        "bbox_debug_asset_bbox_overlay": asset_bbox_path,
        "bbox_debug_collider_bbox_overlays": collider_paths,
        "bbox_debug_collider_bbox_union": _bbox_tuple(collider_bbox_union),
        "bbox_debug_center_marker": {
            "path": f"{BBOX_DEBUG_PATH}/CenterMarker",
            "position": list(_as_tuple3(bbox_center)),
            "radius": float(marker_radius),
            "method": "local_bbox_center",
        },
    }


def _open_or_build_stage(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

    args.out.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix="omni_asset_cli_cup_drop_"))
    stage_path = stage_dir / "cup_table_drop_stage.usda"
    shutil.copyfile(args.template_scene, stage_path)

    stage = Usd.Stage.Open(str(stage_path))
    if stage is None:
        raise RuntimeError(f"Failed to open template stage: {stage_path}")
    stage.SetTimeCodesPerSecond(args.fps)

    old_box = stage.GetPrimAtPath("/World/boxActor")
    template_linear_velocity = (0.0, 0.0, 0.0)
    template_angular_velocity = (0.0, 0.0, 0.0)
    if old_box and old_box.IsValid():
        rigid_body = UsdPhysics.RigidBodyAPI(old_box)
        template_linear_velocity = _read_vec3_attr(rigid_body.GetVelocityAttr(), template_linear_velocity)
        template_angular_velocity = _read_vec3_attr(rigid_body.GetAngularVelocityAttr(), template_angular_velocity)
    if args.initial_linear_velocity is None:
        args.initial_linear_velocity = template_linear_velocity
    else:
        args.initial_linear_velocity = tuple(float(value) for value in args.initial_linear_velocity)
    if args.initial_angular_velocity is None:
        args.initial_angular_velocity = template_angular_velocity
    else:
        args.initial_angular_velocity = tuple(float(value) for value in args.initial_angular_velocity)
    if old_box and old_box.IsValid():
        stage.RemovePrim(old_box.GetPath())

    asset = UsdGeom.Xform.Define(stage, ASSET_PATH)
    asset_prim = asset.GetPrim()
    _clear_xform_ops(asset_prim)

    referenced_asset = UsdGeom.Xform.Define(stage, ASSET_REFERENCE_PATH)
    referenced_prim = referenced_asset.GetPrim()
    _clear_xform_ops(referenced_prim)
    if abs(float(args.asset_rotation_y_deg)) > 1e-9:
        referenced_xform = UsdGeom.Xformable(referenced_prim)
        referenced_xform.AddRotateYOp(UsdGeom.XformOp.PrecisionFloat).Set(float(args.asset_rotation_y_deg))
    if abs(float(args.asset_rotation_z_deg)) > 1e-9:
        referenced_xform = UsdGeom.Xformable(referenced_prim)
        referenced_xform.AddRotateZOp(UsdGeom.XformOp.PrecisionFloat).Set(float(args.asset_rotation_z_deg))
    unit_scale = _asset_units_to_stage_scale(args.asset, stage)
    if abs(unit_scale - 1.0) > 1e-9:
        referenced_xform = UsdGeom.Xformable(referenced_prim)
        referenced_xform.AddScaleOp().Set(Gf.Vec3f(unit_scale, unit_scale, unit_scale))
    referenced_prim.GetReferences().AddReference(str(args.asset.resolve()))
    stage.Load(referenced_prim.GetPath())
    disabled_asset_light_paths = _disable_asset_lights(stage, asset_prim)

    initial_bbox = _compute_world_bbox(stage, asset_prim)
    table_bbox = _compute_world_bbox(stage, stage.GetPrimAtPath(TABLE_PATH))
    if initial_bbox.IsEmpty() or table_bbox.IsEmpty():
        raise RuntimeError("Could not compute asset or table bbox.")
    table_center = (table_bbox.GetMin() + table_bbox.GetMax()) * 0.5
    table_top_z = float(table_bbox.GetMax()[2])
    _set_gravity(stage, args.gravity_magnitude)
    hidden_render_geometry_paths = _hide_non_test_render_geometry(stage)
    removed_table_geometry_paths = _prepare_clean_tabletop(stage)
    _ensure_clean_lighting(stage)

    xformable = UsdGeom.Xformable(asset_prim)
    translate_op = xformable.AddTranslateOp()
    scale_op = xformable.AddScaleOp()
    scale_op.Set(Gf.Vec3f(args.asset_scale, args.asset_scale, args.asset_scale))

    scaled_bbox = _compute_world_bbox(stage, asset_prim)
    scaled_min = scaled_bbox.GetMin()
    scaled_max = scaled_bbox.GetMax()
    scaled_center = (scaled_min + scaled_max) * 0.5
    scaled_half_height = float(scaled_max[2] - scaled_min[2]) * 0.5
    start_center = Gf.Vec3d(
        float(table_center[0]),
        float(table_center[1]),
        table_top_z + args.drop_height + scaled_half_height,
    )
    translate_op.Set(start_center - scaled_center)

    stripped_dynamic_paths = _apply_dynamic_physics(stage, asset_prim, args)
    preview_material_bind_count = _bind_asset_preview_material(stage, asset_prim) if args.override_preview_material else 0
    bbox_debug_summary = _add_bbox_debug_geometry(stage, asset_prim, referenced_asset.GetPrim()) if args.bbox_only_material else {}
    final_bbox = _compute_world_bbox(stage, asset_prim)
    asset_size = final_bbox.GetSize()
    target_height = (args.drop_height + float(asset_size[2])) * 0.5
    target = Gf.Vec3d(float(table_center[0]), float(table_center[1]), table_top_z + target_height)
    radius = max(
        float(asset_size[0]) * 1.35,
        float(asset_size[1]) * 1.35,
        (float(asset_size[2]) + args.drop_height) * 1.45,
        85.0,
    )
    camera_specs = _add_cameras(stage, target, radius, args)

    stage.GetRootLayer().Save()
    summary = {
        "stage_path": str(stage_path),
        "asset": str(args.asset.resolve()),
        "asset_path": ASSET_PATH,
        "asset_reference_path": ASSET_REFERENCE_PATH,
        "table_path": TABLE_PATH,
        "camera_path": camera_specs[0]["camera_path"] if camera_specs else CAMERA_PATH,
        "cameras": camera_specs,
        "table_bbox": _bbox_tuple(table_bbox),
        "asset_initial_bbox": _bbox_tuple(initial_bbox),
        "asset_scaled_bbox": _bbox_tuple(scaled_bbox),
        "asset_start_bbox": _bbox_tuple(final_bbox),
        "asset_scale": args.asset_scale,
        "asset_rotation_y_deg": args.asset_rotation_y_deg,
        "asset_rotation_z_deg": args.asset_rotation_z_deg,
        "asset_unit_scale": unit_scale,
        "preview_material_bind_count": preview_material_bind_count,
        "bbox_only_material": bool(args.bbox_only_material),
        "hidden_non_test_render_geometry_count": len(hidden_render_geometry_paths),
        "hidden_non_test_render_geometry_paths": hidden_render_geometry_paths[:50],
        "removed_table_geometry_paths": removed_table_geometry_paths,
        "disabled_asset_light_paths": disabled_asset_light_paths,
        **bbox_debug_summary,
        "drop_height": args.drop_height,
        "gravity_magnitude": args.gravity_magnitude,
        "initial_linear_velocity": [float(value) for value in args.initial_linear_velocity],
        "initial_angular_velocity": [float(value) for value in args.initial_angular_velocity],
        "stripped_dynamic_physics_paths": stripped_dynamic_paths,
        "frames": args.frames,
        "fps": args.fps,
    }
    return stage_path, summary


def _capture(path: Path, viewport: Any) -> str | None:
    try:
        from omni.kit.viewport.utility import capture_viewport_to_file  # type: ignore

        if viewport is None:
            return "No active viewport is available."
        viewport.camera_path = CAMERA_PATH
        capture_viewport_to_file(viewport, str(path))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


def _wait_for_capture(path: Path, app: Any, max_updates: int = 160) -> str | None:
    stable_updates = 0
    last_size = -1
    for _ in range(max_updates):
        app.update()
        if not path.exists():
            stable_updates = 0
            last_size = -1
            continue
        size = path.stat().st_size
        if size > 0 and size == last_size:
            stable_updates += 1
            if stable_updates >= 4:
                return None
        else:
            stable_updates = 0
            last_size = size
    return f"capture did not finish writing: {path}"


def _replicator_pngs(directory: Path) -> set[Path]:
    return {path for path in directory.rglob("*.png") if path.is_file()}


def _capture_render_product(rep: Any, app: Any, rep_dir: Path, frame_path: Path, args: argparse.Namespace) -> str | None:
    before = _replicator_pngs(rep_dir)
    try:
        rep.orchestrator.step(rt_subframes=max(args.render_rt_subframes, 1))
        try:
            rep.orchestrator.wait_until_complete()
        except Exception:
            pass
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"

    for _ in range(max(args.render_wait_updates, 1)):
        app.update()
        after = _replicator_pngs(rep_dir)
        new_files = sorted(after - before, key=lambda path: path.stat().st_mtime)
        if new_files:
            shutil.copyfile(new_files[-1], frame_path)
            return None

    after = _replicator_pngs(rep_dir)
    new_files = sorted(after - before, key=lambda path: path.stat().st_mtime)
    if not new_files:
        return f"replicator did not write a png for {frame_path}"
    shutil.copyfile(new_files[-1], frame_path)
    return None


def _shift_asset_center_z(stage: Any, asset_prim: Any, center_z: float) -> None:
    from pxr import Gf, UsdGeom

    bbox = _compute_world_bbox(stage, asset_prim)
    if bbox.IsEmpty():
        return
    current_center = (bbox.GetMin() + bbox.GetMax()) * 0.5
    delta_z = float(center_z) - float(current_center[2])
    xformable = UsdGeom.Xformable(asset_prim)
    for op in xformable.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            value = op.Get() or Gf.Vec3d(0.0, 0.0, 0.0)
            op.Set(Gf.Vec3d(value[0], value[1], value[2] + delta_z))
            return
    xformable.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, delta_z))


def _kinematic_center_z(frame: int, frames: int, start_z: float, settle_z: float) -> float:
    fall_frames = max(min(int(frames * 0.45), 54), 1)
    if frame >= fall_frames:
        return settle_z
    t = frame / fall_frames
    return start_z - (start_z - settle_z) * (t * t)


def _physics_updates_per_frame(args: argparse.Namespace) -> int:
    if args.physics_updates_per_frame > 0:
        return args.physics_updates_per_frame
    if args.fps <= 0:
        return 1
    return max(1, int(round(60.0 / args.fps)))


def _advance_physics_frame(timeline: Any, app: Any, updates: int) -> None:
    timeline.play()
    for _ in range(max(updates, 1)):
        app.update()
    timeline.pause()
    for _ in range(2):
        app.update()


def _asset_world_matrix(asset_prim: Any) -> Any:
    from pxr import UsdGeom

    return UsdGeom.Xformable(asset_prim).ComputeLocalToWorldTransform(0)


def _set_asset_matrix(asset_prim: Any, matrix: Any) -> None:
    _clear_xform_ops(asset_prim).AddTransformOp().Set(matrix)


def _sample_asset(stage: Any, asset_prim: Any, frame: int, fps: float, matrix: Any | None = None) -> dict[str, Any]:
    bbox = _compute_world_bbox(stage, asset_prim)
    center = (bbox.GetMin() + bbox.GetMax()) * 0.5 if not bbox.IsEmpty() else None
    return {
        "frame": frame,
        "time": round(frame / fps, 6),
        "center": list(_as_tuple3(center)) if center is not None else None,
        "bbox": _bbox_tuple(bbox),
        "matrix": matrix,
    }


def _record_physx_motion(stage: Any, asset_prim: Any, timeline: Any, app: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    updates = _physics_updates_per_frame(args)
    timeline.stop()
    for _ in range(8):
        app.update()
    timeline.play()
    for frame in range(args.frames):
        if frame > 0:
            for _ in range(updates):
                app.update()
        samples.append(_sample_asset(stage, asset_prim, frame, args.fps, _asset_world_matrix(asset_prim)))
    timeline.pause()
    for _ in range(4):
        app.update()
    return samples


def render_drop(stage_path: Path, args: argparse.Namespace, app: Any) -> dict[str, Any]:
    errors: list[str] = []
    samples: list[dict[str, Any]] = []
    camera_rendered_files: dict[str, list[str]] = {}
    live_stage_cleanups: list[dict[str, Any]] = []
    try:
        import omni.timeline  # type: ignore
        import omni.usd  # type: ignore
        import omni.replicator.core as rep  # type: ignore

        context = omni.usd.get_context()
        try:
            context.close_stage()
            for _ in range(20):
                app.update()
        except Exception:
            pass
        _progress(f"stage-open-start path={stage_path}")
        context.open_stage(str(stage_path))
        stage = _wait_for_stage_ready(context, stage_path, app)
        cleanup = _clean_live_render_stage(stage)
        live_stage_cleanups.append({"phase": "initial_open", **cleanup})
        _progress(
            "stage-ready "
            f"removed_background={len(cleanup['removed_background_paths'])} "
            f"remaining_room={','.join(cleanup['remaining_room_children']) or 'none'}"
        )

        timeline = omni.timeline.get_timeline_interface()
        physics_updates = _physics_updates_per_frame(args) if args.physics_driven else None
        physx_samples: list[dict[str, Any]] | None = None
        if args.physics_driven:
            stage = context.get_stage()
            asset_prim = stage.GetPrimAtPath(ASSET_PATH)
            physx_samples = _record_physx_motion(stage, asset_prim, timeline, app, args)
            timeline.stop()
            _progress("physics-record-done")
            context.open_stage(str(stage_path))
            stage = _wait_for_stage_ready(context, stage_path, app)
            cleanup = _clean_live_render_stage(stage)
            live_stage_cleanups.append({"phase": "render_reload", **cleanup})
            _progress(
                "stage-reloaded-for-render "
                f"removed_background={len(cleanup['removed_background_paths'])} "
                f"remaining_room={','.join(cleanup['remaining_room_children']) or 'none'}"
            )

        camera_specs = [
            {"name": _camera_name_for_preset(preset), "preset": preset, "camera_path": CAMERA_PATH if index == 0 else f"{CAMERA_ROOT_PATH}/{_camera_name_for_preset(preset)}"}
            for index, preset in enumerate(_normalize_camera_presets(args.camera_preset))
        ]
        legacy_single_camera = len(camera_specs) == 1 and camera_specs[0]["name"] == "drop_camera"
        render_contexts: list[dict[str, Any]] = []
        for camera_spec in camera_specs:
            camera_name = camera_spec["name"]
            _progress(f"render-product-create-start camera={camera_name} path={camera_spec['camera_path']}")
            rep_dir = args.out / "_replicator_render_product"
            if not legacy_single_camera:
                rep_dir = rep_dir / camera_name
            rep_dir.mkdir(parents=True, exist_ok=True)
            render_product = rep.create.render_product(camera_spec["camera_path"], (args.width, args.height))
            writer = rep.WriterRegistry.get("BasicWriter")
            writer.initialize(output_dir=str(rep_dir), rgb=True)
            writer.attach([render_product])
            _progress(f"render-product-create-done camera={camera_name} output={rep_dir}")
            render_contexts.append(
                {
                    "camera": camera_spec,
                    "rep_dir": rep_dir,
                }
            )
            camera_rendered_files[camera_name] = []
        _progress(f"render-warmup-start cameras={len(render_contexts)}")
        for _ in range(40):
            app.update()
        _progress("render-warmup-done")

        timeline.pause()
        frames_dir = args.out / "render_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        expected_paths: list[Path] = []
        stage = context.get_stage()
        asset_prim = stage.GetPrimAtPath(ASSET_PATH)
        start_bbox = _compute_world_bbox(stage, asset_prim)
        table_bbox = _compute_world_bbox(stage, stage.GetPrimAtPath(TABLE_PATH))
        start_center_z = float(((start_bbox.GetMin() + start_bbox.GetMax()) * 0.5)[2])
        settle_center_z = float(table_bbox.GetMax()[2]) + float(start_bbox.GetSize()[2]) * 0.5

        for frame in range(args.frames):
            if args.physics_driven:
                sample = physx_samples[frame] if physx_samples and frame < len(physx_samples) else None
                if sample and sample.get("matrix") is not None:
                    _set_asset_matrix(asset_prim, sample["matrix"])
                timeline.pause()
                for _ in range(2):
                    app.update()
            else:
                timeline.pause()
                _shift_asset_center_z(
                    stage,
                    asset_prim,
                    _kinematic_center_z(frame, args.frames, start_center_z, settle_center_z),
                )
            for _ in range(2):
                app.update()
            sample_for_summary = _sample_asset(stage, asset_prim, frame, args.fps)
            sample_for_summary.pop("matrix", None)
            samples.append(sample_for_summary)
            if frame % max(args.render_every_n_frames, 1) == 0:
                for render_context in render_contexts:
                    camera_name = render_context["camera"]["name"]
                    camera_frames_dir = frames_dir if legacy_single_camera else frames_dir / camera_name
                    camera_frames_dir.mkdir(parents=True, exist_ok=True)
                    frame_path = camera_frames_dir / f"frame_{frame:04d}.png"
                    if frame_path.exists():
                        frame_path.unlink()
                    expected_paths.append(frame_path)
                    if frame == 0:
                        _progress(f"capture-first-frame-start camera={camera_name} path={frame_path}")
                    error = _capture_render_product(rep, app, render_context["rep_dir"], frame_path, args)
                    if error:
                        errors.append(f"camera={camera_name} frame={frame}: {error}")
                    elif frame == 0:
                        _progress(f"capture-first-frame-done camera={camera_name} path={frame_path}")
                if frame == 0 or frame == args.frames - 1 or frame % max(args.render_every_n_frames * 10, 10) == 0:
                    captured_count = len(expected_paths) - len(errors)
                    _progress(f"render-progress frame={frame + 1}/{args.frames} requested={len(expected_paths)} approx_ok={captured_count}")

        timeline.stop()
        for _ in range(80):
            app.update()
        for frame_path in expected_paths:
            if frame_path.exists():
                if frame_path.parent == frames_dir:
                    camera_rendered_files.setdefault("drop_camera", []).append(str(frame_path))
                else:
                    camera_rendered_files.setdefault(frame_path.parent.name, []).append(str(frame_path))
            else:
                errors.append(f"missing_frame={frame_path}")

        timeline_path = args.out / "timeline.csv"
        with timeline_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["frame", "time", "center_x", "center_y", "center_z"])
            writer.writeheader()
            for sample in samples:
                center = sample.get("center") or [None, None, None]
                writer.writerow(
                    {
                        "frame": sample["frame"],
                        "time": sample["time"],
                        "center_x": center[0],
                        "center_y": center[1],
                        "center_z": center[2],
                    }
                )
        camera_renders = [
            {
                "name": render_context["camera"]["name"],
                "preset": render_context["camera"]["preset"],
                "camera_path": render_context["camera"]["camera_path"],
                "rendered_frame_count": len(camera_rendered_files.get(render_context["camera"]["name"], [])),
                "rendered_files": camera_rendered_files.get(render_context["camera"]["name"], [])[:10],
            }
            for render_context in render_contexts
        ]
        all_rendered_files = [
            value
            for files in camera_rendered_files.values()
            for value in files
        ]
        return {
            "rendered_frame_count": len(all_rendered_files),
            "rendered_files": all_rendered_files[:10],
            "camera_renders": camera_renders,
            "render_videos": _encode_videos(camera_rendered_files, args, legacy_single_camera=legacy_single_camera),
            "timeline_csv": str(timeline_path),
            "first_sample": samples[0] if samples else None,
            "last_sample": samples[-1] if samples else None,
            "physics_driven": bool(args.physics_driven),
            "physics_driven_forced_for_video": bool(getattr(args, "physics_driven_forced_for_video", False)),
            "physics_updates_per_frame": physics_updates,
            "live_stage_cleanups": live_stage_cleanups,
            "errors": errors,
        }
    finally:
        pass


def _encode_videos(
    camera_rendered_files: dict[str, list[str]],
    args: argparse.Namespace,
    *,
    legacy_single_camera: bool,
) -> list[dict[str, Any]]:
    if not args.render_video:
        return []
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return [{"error": "ffmpeg was not found in PATH; mp4 encoding skipped"}]

    video_dir = args.out / "render_videos"
    sequence_dir = args.out / "_video_sequence"
    video_dir.mkdir(parents=True, exist_ok=True)
    sequence_dir.mkdir(parents=True, exist_ok=True)
    video_fps = args.render_video_fps or max(float(args.fps) / max(args.render_every_n_frames, 1), 1.0)
    videos: list[dict[str, Any]] = []
    for camera_name, rendered_files in camera_rendered_files.items():
        if not rendered_files:
            continue
        camera_sequence_dir = sequence_dir / camera_name
        camera_sequence_dir.mkdir(parents=True, exist_ok=True)
        for old_file in camera_sequence_dir.glob("frame_*.png"):
            old_file.unlink()
        for index, value in enumerate(rendered_files):
            source = Path(value)
            if source.exists():
                shutil.copy2(source, camera_sequence_dir / f"frame_{index:04d}.png")

        video_name = "drop_camera.mp4" if legacy_single_camera and camera_name == "drop_camera" else f"{camera_name}.mp4"
        video_path = video_dir / video_name
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            f"{video_fps:g}",
            "-i",
            str(camera_sequence_dir / "frame_%04d.png"),
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v",
            "libx264",
            "-crf",
            str(args.render_video_crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0 or not video_path.exists():
            videos.append({"camera": camera_name, "error": f"ffmpeg failed returncode={completed.returncode}: {completed.stderr[-500:]}"})
            continue
        videos.append(
            {
                "camera": camera_name,
                "path": str(video_path),
                "fps": video_fps,
                "frame_count": len(rendered_files),
                "codec": "libx264",
            }
        )
    return videos


def main() -> int:
    global PROGRESS_LOG_PATH

    args = parse_args()
    args.physics_driven_forced_for_video = bool(args.render_video and not args.physics_driven)
    if args.physics_driven_forced_for_video:
        args.physics_driven = True
    args.out.mkdir(parents=True, exist_ok=True)
    debug_log = args.out / "cup_table_drop_debug.log"
    PROGRESS_LOG_PATH = debug_log

    def note(message: str) -> None:
        with debug_log.open("a", encoding="utf-8") as stream:
            stream.write(f"{message}\n")

    note("parsed_args")
    from isaacsim import SimulationApp  # type: ignore

    note("imported_simulation_app")
    _progress(f"simulation-app-create resolution={args.width}x{args.height} headless=true")
    app = SimulationApp({"headless": True, "width": args.width, "height": args.height})
    note("created_simulation_app")
    _progress("simulation-app-ready")
    try:
        try:
            modes = _normalize_material_modes(args.render_material_mode)
            if len(modes) == 1 and modes[0] == "material" and not args.bbox_only_material:
                stage_path, summary = _open_or_build_stage(args)
                note("built_stage")
                _progress(f"stage-built path={stage_path}")
                render_summary = render_drop(stage_path, args, app)
                note("rendered_drop")
                summary.update(render_summary)
                summary["render_material_mode"] = "material"
                output = args.out / "cup_table_drop_summary.json"
                output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                if args.keep_stage:
                    shutil.copyfile(stage_path, args.out / "cup_table_drop_stage.usda")
                print(json.dumps({"summary": str(output), "errors": summary["errors"], "frames": summary["rendered_frame_count"]}, indent=2))
                return 0 if not summary["errors"] else 1

            variants: list[dict[str, Any]] = []
            root_errors: list[str] = []
            for mode in modes:
                mode_args = copy.copy(args)
                mode_args.out = args.out / mode
                mode_args.out.mkdir(parents=True, exist_ok=True)
                mode_args.render_material_mode = ["material"]
                mode_args.bbox_only_material = mode == "transparent"
                stage_path, summary = _open_or_build_stage(mode_args)
                note(f"built_stage mode={mode}")
                _progress(f"stage-built mode={mode} path={stage_path}")
                render_summary = render_drop(stage_path, mode_args, app)
                note(f"rendered_drop mode={mode}")
                summary.update(render_summary)
                summary["render_material_mode"] = mode
                output = mode_args.out / "cup_table_drop_summary.json"
                output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
                if mode_args.keep_stage:
                    shutil.copyfile(stage_path, mode_args.out / "cup_table_drop_stage.usda")
                root_errors.extend([f"{mode}: {error}" for error in summary["errors"]])
                variants.append(
                    {
                        "mode": mode,
                        "summary": str(output),
                        "out": str(mode_args.out),
                        "rendered_frame_count": summary["rendered_frame_count"],
                        "camera_renders": summary.get("camera_renders", []),
                        "render_videos": summary.get("render_videos", []),
                        "errors": summary["errors"],
                    }
                )

            root_summary = {
                "asset": str(args.asset.resolve()),
                "template_scene": str(args.template_scene.resolve()),
                "frames": args.frames,
                "fps": args.fps,
                "camera_presets": _normalize_camera_presets(args.camera_preset),
                "render_material_modes": modes,
                "render_variants": variants,
                "rendered_frame_count": sum(int(variant["rendered_frame_count"]) for variant in variants),
                "render_videos": [
                    {**video, "mode": variant["mode"]}
                    for variant in variants
                    for video in variant.get("render_videos", [])
                ],
                "errors": root_errors,
            }
            output = args.out / "cup_table_drop_summary.json"
            output.write_text(json.dumps(root_summary, indent=2), encoding="utf-8")
            print(json.dumps({"summary": str(output), "errors": root_errors, "frames": root_summary["rendered_frame_count"]}, indent=2))
            return 0 if not root_errors else 1
        except BaseException as exc:
            note(f"exception: {type(exc).__name__}: {exc}")
            raise
    finally:
        note("closing_simulation_app")
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
