#!/usr/bin/env python3
"""Render an asset setup orbit with bbox, collider bbox, and center marker overlays."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any


DEBUG_ROOT = "/__OmniAssetSetupOverlay"
ASSET_PATH = "/World/Asset"
CAMERA_PATH = "/World/OrbitCamera"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render 360-degree setup evidence for a USD asset with bbox and center overlays.",
    )
    parser.add_argument("asset", type=Path, help="USD asset to reference into the debug render stage")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for frames and summary")
    parser.add_argument("--frames", type=int, default=120, help="Number of orbit frames to render")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--camera-elevation-deg", type=float, default=24.0)
    parser.add_argument("--camera-distance-scale", type=float, default=2.7)
    parser.add_argument("--initial-azimuth-deg", type=float, default=0.0, help="Orbit angle of the first rendered frame.")
    parser.add_argument("--line-width", type=float, default=0.0, help="Overlay line width; 0 chooses automatic width")
    parser.add_argument("--hide-center-marker", action="store_true", help="Do not draw the diagnostic center marker and axes.")
    parser.add_argument("--hide-bbox-overlays", action="store_true", help="Do not draw asset or collider AABB reference lines.")
    parser.add_argument("--hide-stage-probe", action="store_true", help="Hide the original test-stage probe; use with --contact-report.")
    parser.add_argument("--collider-only", action="store_true", help="Hide non-collider visual geometry and render CollisionAPI Gprims only.")
    parser.add_argument(
        "--contact-report",
        type=Path,
        help="sphere_probe.json; draw the probe sphere at its first PhysX contact position.",
    )
    parser.add_argument(
        "--target-prim",
        default=ASSET_PATH,
        help="Prim whose geometry and colliders are measured by overlays (default: /World/Asset).",
    )
    parser.add_argument(
        "--center-source",
        choices=["auto", "mass-api", "geometry-centroid", "bbox-center"],
        default="auto",
        help="How to place the center marker. auto prefers authored MassAPI, then geometry centroid.",
    )
    parser.add_argument("--keep-debug-usd", action="store_true", help="Keep the generated debug USD stage")
    return parser.parse_args()


def _as_tuple3(value: Any) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _range_tuple(value: Any) -> dict[str, list[float]] | None:
    if value.IsEmpty():
        return None
    return {
        "min": list(_as_tuple3(value.GetMin())),
        "max": list(_as_tuple3(value.GetMax())),
        "size": list(_as_tuple3(value.GetSize())),
    }


def _bbox_diagonal(value: Any) -> float:
    if value.IsEmpty():
        return 1.0
    size = value.GetSize()
    return max(math.sqrt(float(size[0]) ** 2 + float(size[1]) ** 2 + float(size[2]) ** 2), 1.0)


def _line_width(bbox: Any, requested: float) -> float:
    if requested > 0:
        return requested
    return max(_bbox_diagonal(bbox) * 0.004, 0.01)


def _compute_world_bbox(stage: Any, prim: Any) -> Any:
    from pxr import UsdGeom

    cache = UsdGeom.BBoxCache(
        stage.GetTimeCodesPerSecond() if stage.GetTimeCodesPerSecond() else 0,
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
        useExtentsHint=True,
    )
    return cache.ComputeWorldBound(prim).ComputeAlignedRange()


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
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.72)
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(float(opacity))
    if emissive:
        shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _bind(
    stage: Any,
    prim: Any,
    material_path: str,
    color: tuple[float, float, float],
    emissive: bool = False,
    opacity: float = 1.0,
) -> None:
    from pxr import UsdShade

    material = _material(stage, material_path, color, emissive=emissive, opacity=opacity)
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)


def _bind_ghost_asset_material(stage: Any, asset_prim: Any) -> int:
    from pxr import UsdGeom, UsdShade

    material = _material(
        stage,
        f"{DEBUG_ROOT}/Materials/GhostAsset",
        (0.16, 0.72, 1.0),
        emissive=True,
        opacity=0.82,
    )
    bound = 0
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        # Cart_v2's frame is authored as Cylinder primitives, not Meshes.
        # Binding all Gprims keeps diagnostic captures readable without
        # touching the referenced asset or its collision configuration.
        if prim.IsA(UsdGeom.Gprim):
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)
            bound += 1
    return bound


def _bind_collider_material(stage: Any, collider_prims: list[Any]) -> int:
    """Highlight the actual collision Gprims, never their enclosing AABBs."""
    from pxr import UsdGeom, UsdShade

    material = _material(
        stage,
        f"{DEBUG_ROOT}/Materials/PhysicsCollider",
        (0.90, 0.04, 0.42),
        emissive=True,
        opacity=1.0,
    )
    bound = 0
    for prim in collider_prims:
        if not prim.IsA(UsdGeom.Gprim):
            continue
        # This replaces the diagnostic visual binding on precisely the prim
        # that owns CollisionAPI.  It does not manufacture an enclosing box,
        # convex hull, or any new collision geometry.
        UsdShade.MaterialBindingAPI.Apply(prim).Bind(material)
        bound += 1
    return bound


def _add_contact_probe(stage: Any, report_path: Path | None) -> dict[str, Any] | None:
    """Add a visual-only sphere at the recorded first-contact sample."""
    if report_path is None:
        return None
    from pxr import Gf, UsdGeom

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    first = payload.get("first_contact") or {}
    frame = first.get("frame")
    samples = payload.get("samples") or []
    sample = next((item for item in samples if item.get("frame") == frame), None)
    if sample is None or not isinstance(sample.get("position"), list):
        raise ValueError(f"No sample at first-contact frame in {report_path}")
    radius = float((payload.get("sphere") or {}).get("radius_m") or 0.04)
    position = Gf.Vec3d(*[float(value) for value in sample["position"]])
    sphere = UsdGeom.Sphere.Define(stage, f"{DEBUG_ROOT}/FirstContactProbe")
    sphere.CreateRadiusAttr(radius)
    sphere.AddTranslateOp().Set(position)
    _bind(stage, sphere.GetPrim(), f"{DEBUG_ROOT}/Materials/FirstContactProbe", (1.0, 0.72, 0.02), emissive=True)
    return {"frame": frame, "position": list(_as_tuple3(position)), "radius_m": radius}


def _add_cross(stage: Any, path: str, center: Any, radius: float, color: tuple[float, float, float], width: float) -> None:
    from pxr import Gf

    for axis, vector in (("X", Gf.Vec3d(radius, 0, 0)), ("Y", Gf.Vec3d(0, radius, 0)), ("Z", Gf.Vec3d(0, 0, radius))):
        _add_axis_line(stage, f"{path}/{axis}", [center - vector, center + vector], color, width)


def _rigid_body_prims(asset_prim: Any) -> list[Any]:
    from pxr import UsdPhysics

    return [
        prim for prim in asset_prim.GetStage().Traverse()
        if str(prim.GetPath()).startswith(str(asset_prim.GetPath())) and prim.HasAPI(UsdPhysics.RigidBodyAPI)
    ]


def _add_articulation_overlay(stage: Any, asset_prim: Any, diagonal: float, width: float) -> dict[str, Any]:
    """Add one readable marker per rigid body plus one axis per revolute joint."""
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics

    body_paths: dict[str, Any] = {}
    body_markers: list[dict[str, Any]] = []
    colors = ((0.15, 0.65, 1.0), (0.25, 1.0, 0.45), (0.95, 0.25, 0.35), (0.85, 0.45, 1.0))
    marker_radius = max(diagonal * 0.018, 0.008)
    for index, prim in enumerate(_rigid_body_prims(asset_prim)):
        bbox = _compute_world_bbox(stage, prim)
        if bbox.IsEmpty():
            continue
        center = (bbox.GetMin() + bbox.GetMax()) * 0.5
        color = colors[index % len(colors)]
        marker = UsdGeom.Sphere.Define(stage, Sdf.Path(f"{DEBUG_ROOT}/RigidBodies/Body_{index:02d}"))
        marker.CreateRadiusAttr(marker_radius)
        marker.AddTranslateOp().Set(center)
        _bind(stage, marker.GetPrim(), f"{DEBUG_ROOT}/Materials/Rigid_{index:02d}", color, emissive=True)
        _add_cross(stage, f"{DEBUG_ROOT}/RigidBodies/Axes_{index:02d}", center, marker_radius * 1.8, color, width * 0.8)
        body_paths[str(prim.GetPath())] = center
        body_markers.append({"prim": str(prim.GetPath()), "center": list(_as_tuple3(center)), "color": color})

    joint_axes: list[dict[str, Any]] = []
    axis_color = {"X": (1.0, 0.2, 0.2), "Y": (0.2, 1.0, 0.25), "Z": (0.2, 0.55, 1.0)}
    for index, prim in enumerate(stage.Traverse()):
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())) or not prim.IsA(UsdPhysics.RevoluteJoint):
            continue
        joint = UsdPhysics.RevoluteJoint(prim)
        body0 = [str(value) for value in joint.GetBody0Rel().GetTargets()]
        body1 = [str(value) for value in joint.GetBody1Rel().GetTargets()]
        if len(body0) != 1 or len(body1) != 1 or body0[0] not in body_paths or body1[0] not in body_paths:
            continue
        center = (body_paths[body0[0]] + body_paths[body1[0]]) * 0.5
        axis = str(joint.GetAxisAttr().Get() or "X").upper()
        direction = {"X": Gf.Vec3d(1, 0, 0), "Y": Gf.Vec3d(0, 1, 0), "Z": Gf.Vec3d(0, 0, 1)}.get(axis, Gf.Vec3d(1, 0, 0))
        length = max(diagonal * 0.075, 0.03)
        _add_axis_line(stage, f"{DEBUG_ROOT}/JointAxes/Joint_{index:02d}", [center - direction * length, center + direction * length], axis_color[axis], width * 1.8)
        joint_axes.append({"prim": str(prim.GetPath()), "axis": axis, "center": list(_as_tuple3(center)), "color": axis_color[axis]})
    return {"rigid_body_markers": body_markers, "revolute_joint_axes": joint_axes}


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

    colliders = []
    for prim in asset_prim.GetStage().Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            colliders.append(prim)
    return colliders


def _authored_mass_center(stage: Any, asset_prim: Any) -> tuple[Any | None, str | None]:
    from pxr import UsdGeom, UsdPhysics

    xform_cache = UsdGeom.XformCache()
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if not prim.HasAPI(UsdPhysics.MassAPI):
            continue
        mass_api = UsdPhysics.MassAPI(prim)
        center = mass_api.GetCenterOfMassAttr().Get()
        if center is None:
            continue
        matrix = xform_cache.GetLocalToWorldTransform(prim)
        return matrix.Transform(center), str(prim.GetPath())
    return None, None


def _geometry_centroid(stage: Any, asset_prim: Any) -> tuple[Any | None, int]:
    from pxr import Gf, UsdGeom

    xform_cache = UsdGeom.XformCache()
    total = Gf.Vec3d(0.0, 0.0, 0.0)
    count = 0
    for prim in stage.Traverse():
        if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
            continue
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        points = mesh.GetPointsAttr().Get() or []
        matrix = xform_cache.GetLocalToWorldTransform(prim)
        for point in points:
            total += matrix.Transform(Gf.Vec3d(point))
            count += 1
    if count == 0:
        return None, 0
    return total / count, count


def _choose_center(stage: Any, asset_prim: Any, bbox: Any, source: str) -> tuple[Any, str, str | None, int]:
    if source in {"auto", "mass-api"}:
        center, prim_path = _authored_mass_center(stage, asset_prim)
        if center is not None:
            return center, "authored_mass_api_center_of_mass", prim_path, 0
        if source == "mass-api":
            raise ValueError("No authored MassAPI centerOfMass was found.")

    if source in {"auto", "geometry-centroid"}:
        center, point_count = _geometry_centroid(stage, asset_prim)
        if center is not None:
            return center, "estimated_geometry_vertex_centroid", None, point_count
        if source == "geometry-centroid":
            raise ValueError("No mesh points were found for geometry centroid estimation.")

    if bbox.IsEmpty():
        from pxr import Gf

        return Gf.Vec3d(0.0, 0.0, 0.0), "fallback_origin", None, 0
    return (bbox.GetMin() + bbox.GetMax()) * 0.5, "bbox_center", None, 0


def _look_at_matrix(eye: Any, target: Any) -> Any:
    from pxr import Gf

    direction = (target - eye).GetNormalized()
    up = Gf.Vec3d(0.0, 0.0, 1.0)
    if abs(Gf.Dot(direction, up)) > 0.98:
        up = Gf.Vec3d(0.0, 1.0, 0.0)
    right = Gf.Cross(direction, up).GetNormalized()
    true_up = Gf.Cross(right, direction).GetNormalized()
    return Gf.Matrix4d(
        right[0], right[1], right[2], 0.0,
        true_up[0], true_up[1], true_up[2], 0.0,
        -direction[0], -direction[1], -direction[2], 0.0,
        eye[0], eye[1], eye[2], 1.0,
    )


def _set_camera(camera: Any, matrix_op: Any, eye: Any, target: Any, radius: float) -> None:
    from pxr import Gf

    matrix_op.Set(_look_at_matrix(eye, target))
    camera.CreateFocalLengthAttr(42.0)
    camera.CreateClippingRangeAttr(Gf.Vec2f(max(radius * 0.01, 0.01), radius * 30.0))


def build_debug_stage(asset: Path, out_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

    out_dir.mkdir(parents=True, exist_ok=True)
    stage_path = out_dir / "cup_setup_orbit_debug.usda"
    stage = Usd.Stage.CreateNew(str(stage_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    world = UsdGeom.Xform.Define(stage, "/World")
    asset_xform = UsdGeom.Xform.Define(stage, ASSET_PATH)
    # Keep the debug stage relocatable inside a Docker-mounted staging package.
    # An absolute host path would be invalid when the stage is reopened in Isaac Sim.
    reference_path = os.path.relpath(asset.resolve(), start=stage_path.parent.resolve())
    asset_xform.GetPrim().GetReferences().AddReference(reference_path)
    stage.SetDefaultPrim(world.GetPrim())
    stage.Load(asset_xform.GetPrim().GetPath())

    UsdLux.DomeLight.Define(stage, "/World/DomeLight").CreateIntensityAttr(2400.0)
    key = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
    key.CreateIntensityAttr(5200.0)
    key.CreateAngleAttr(0.35)

    asset_prim = stage.GetPrimAtPath(args.target_prim)
    if not asset_prim.IsValid():
        raise ValueError(f"Target prim does not exist after composing the asset: {args.target_prim}")
    if args.hide_stage_probe:
        probe = stage.GetPrimAtPath(f"{ASSET_PATH}/ProbeSphere")
        if probe.IsValid():
            UsdGeom.Imageable(probe).MakeInvisible()
    asset_bbox = _compute_world_bbox(stage, asset_prim)
    diagonal = _bbox_diagonal(asset_bbox)
    width = _line_width(asset_bbox, args.line_width)

    overlay = UsdGeom.Xform.Define(stage, DEBUG_ROOT)
    overlay.GetPrim().SetSpecifier(Sdf.SpecifierDef)

    asset_bbox_path = None
    if not args.hide_bbox_overlays:
        asset_bbox_path = _add_bbox_curves(stage, f"{DEBUG_ROOT}/AssetBBox", asset_bbox, (0.1, 0.55, 1.0), width)

    collider_prims = _find_collider_prims(asset_prim)
    collider_paths = []
    collider_bbox_union = Gf.Range3d()
    # 82 fine-grained collider boxes are unreadable as a single dense wire cloud.
    # Retain representative bounds for review, while the JSON summary keeps all 82.
    representative = collider_prims[: min(12, len(collider_prims))] if not args.hide_bbox_overlays else []
    for index, prim in enumerate(representative):
        bbox = _compute_world_bbox(stage, prim)
        if bbox.IsEmpty():
            continue
        collider_bbox_union.UnionWith(bbox)
        curve_path = _add_bbox_curves(
            stage,
            f"{DEBUG_ROOT}/ColliderBBox_{index:02d}",
            bbox,
            (0.78, 0.20, 1.0),
            width * 1.25,
        )
        if curve_path:
            collider_paths.append({"prim": str(prim.GetPath()), "overlay": curve_path, "bbox": _range_tuple(bbox)})

    ghost_mesh_count = 0
    if args.collider_only:
        collider_path_set = {str(prim.GetPath()) for prim in collider_prims}
        for prim in stage.Traverse():
            if not str(prim.GetPath()).startswith(str(asset_prim.GetPath())):
                continue
            if prim.IsA(UsdGeom.Gprim) and str(prim.GetPath()) not in collider_path_set:
                UsdGeom.Imageable(prim).MakeInvisible()
    else:
        ghost_mesh_count = _bind_ghost_asset_material(stage, asset_prim)
    highlighted_collider_count = _bind_collider_material(stage, collider_prims)
    contact_probe = _add_contact_probe(stage, args.contact_report.resolve() if args.contact_report else None)
    center, center_method, center_prim, center_point_count = _choose_center(stage, asset_prim, asset_bbox, args.center_source)
    articulation = _add_articulation_overlay(stage, asset_prim, diagonal, width)

    if not args.hide_center_marker:
        marker_radius = max(diagonal * 0.06, 0.1)
        marker = UsdGeom.Sphere.Define(stage, f"{DEBUG_ROOT}/CenterMarker")
        marker.CreateRadiusAttr(marker_radius)
        marker.AddTranslateOp().Set(center)
        _bind(stage, marker.GetPrim(), f"{DEBUG_ROOT}/Materials/CenterMarker", (1.0, 0.9, 0.05), emissive=True)

    if not args.hide_center_marker and not asset_bbox.IsEmpty():
        min_z = float(asset_bbox.GetMin()[2])
        max_z = float(asset_bbox.GetMax()[2])
        _add_axis_line(
            stage,
            f"{DEBUG_ROOT}/CenterVerticalAxis",
            [Gf.Vec3f(center[0], center[1], min_z), Gf.Vec3f(center[0], center[1], max_z)],
            (1.0, 0.9, 0.05),
            width * 0.75,
        )
        cross = diagonal * 0.12
        _add_axis_line(
            stage,
            f"{DEBUG_ROOT}/CenterCrossX",
            [Gf.Vec3f(center[0] - cross, center[1], center[2]), Gf.Vec3f(center[0] + cross, center[1], center[2])],
            (1.0, 0.95, 0.15),
            width * 1.1,
        )
        _add_axis_line(
            stage,
            f"{DEBUG_ROOT}/CenterCrossY",
            [Gf.Vec3f(center[0], center[1] - cross, center[2]), Gf.Vec3f(center[0], center[1] + cross, center[2])],
            (1.0, 0.95, 0.15),
            width * 1.1,
        )
        _add_axis_line(
            stage,
            f"{DEBUG_ROOT}/CenterCrossZ",
            [Gf.Vec3f(center[0], center[1], center[2] - cross), Gf.Vec3f(center[0], center[1], center[2] + cross)],
            (1.0, 0.95, 0.15),
            width * 1.1,
        )

    bbox_center = (asset_bbox.GetMin() + asset_bbox.GetMax()) * 0.5 if not asset_bbox.IsEmpty() else Gf.Vec3d(0, 0, 0)
    camera = UsdGeom.Camera.Define(stage, CAMERA_PATH)
    camera_op = camera.AddTransformOp()
    _set_camera(
        camera,
        camera_op,
        bbox_center + Gf.Vec3d(diagonal * args.camera_distance_scale, -diagonal * args.camera_distance_scale, diagonal),
        bbox_center,
        diagonal,
    )

    stage.GetRootLayer().Save()
    return {
        "debug_stage": str(stage_path),
        "asset": str(asset.resolve()),
        "asset_prim_path": str(asset_prim.GetPath()),
        "asset_bbox": _range_tuple(asset_bbox),
        "asset_bbox_overlay": asset_bbox_path,
        "collider_count": len(collider_prims),
        "rendered_representative_collider_count": len(collider_paths),
        "collider_bbox_overlays": collider_paths,
        "collider_bbox_union": _range_tuple(collider_bbox_union),
        "center_marker": {
            "position": list(_as_tuple3(center)),
            "method": center_method,
            "source_prim": center_prim,
            "geometry_point_count": center_point_count,
            "overlay": f"{DEBUG_ROOT}/CenterMarker",
        },
        "ghost_material_bound_mesh_count": ghost_mesh_count,
        "highlighted_actual_collider_count": highlighted_collider_count,
        "first_contact_probe": contact_probe,
        "articulation_overlay": articulation,
        "camera_path": CAMERA_PATH,
        "frame_count": args.frames,
        "width": args.width,
        "height": args.height,
    }


def render_orbit(summary: dict[str, Any], args: argparse.Namespace, app: Any) -> list[str]:
    errors: list[str] = []
    try:
        import omni.usd  # type: ignore
        from omni.kit.viewport.utility import capture_viewport_to_file, get_active_viewport  # type: ignore
        from pxr import Gf, Sdf, UsdGeom

        context = omni.usd.get_context()
        context.open_stage(summary["debug_stage"])
        # A first clean headless capture needs a substantial settle period; otherwise
        # the asset can appear black even though its USD composition is valid.
        for _ in range(180):
            app.update()

        stage = context.get_stage()
        viewport = get_active_viewport()
        if viewport is None:
            return ["No active viewport is available."]
        viewport.camera_path = CAMERA_PATH

        camera = UsdGeom.Camera(stage.GetPrimAtPath(Sdf.Path(CAMERA_PATH)))
        xformable = UsdGeom.Xformable(camera.GetPrim())
        ops = xformable.GetOrderedXformOps()
        matrix_op = ops[0] if ops else camera.AddTransformOp()

        bbox = summary.get("asset_bbox") or {}
        bbox_min = bbox.get("min") or [-1.0, -1.0, -1.0]
        bbox_max = bbox.get("max") or [1.0, 1.0, 1.0]
        minimum = Gf.Vec3d(*bbox_min)
        maximum = Gf.Vec3d(*bbox_max)
        target = (minimum + maximum) * 0.5
        size = maximum - minimum
        diagonal = max(math.sqrt(float(size[0]) ** 2 + float(size[1]) ** 2 + float(size[2]) ** 2), 1.0)
        radius = diagonal * args.camera_distance_scale
        elevation = math.radians(args.camera_elevation_deg)
        z = math.sin(elevation) * radius
        xy_radius = math.cos(elevation) * radius

        frames_dir = args.out / "orbit_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        expected_frames = []
        for index in range(max(args.frames, 1)):
            angle = math.radians(args.initial_azimuth_deg) + (math.tau * index) / max(args.frames, 1)
            eye = target + Gf.Vec3d(math.cos(angle) * xy_radius, math.sin(angle) * xy_radius, z)
            _set_camera(camera, matrix_op, eye, target, diagonal)
            for _ in range(4):
                app.update()
            frame_path = frames_dir / f"frame_{index:04d}.png"
            expected_frames.append(frame_path)
            capture_viewport_to_file(viewport, str(frame_path))
            for _ in range(8):
                app.update()
        for _ in range(90):
            app.update()
        for index, frame_path in enumerate(expected_frames):
            if not frame_path.exists():
                errors.append(f"frame={index}: capture requested but file was not written: {frame_path}")
    except Exception as exc:  # pragma: no cover - depends on Isaac Sim runtime
        errors.append(f"{type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    args = parse_args()
    # The debug layer references the input relatively.  Keep both layer
    # identifiers absolute so omni.usd does not resolve that relative path a
    # second time when the freshly-authored stage is reopened for capture.
    args.asset = args.asset.resolve()
    args.out = args.out.resolve()
    if args.contact_report is not None:
        args.contact_report = args.contact_report.resolve()
    from isaacsim import SimulationApp  # type: ignore

    app = SimulationApp({"headless": True, "width": args.width, "height": args.height})
    try:
        summary = build_debug_stage(args.asset, args.out, args)
        errors = render_orbit(summary, args, app)
        summary["render_errors"] = errors
        summary_path = args.out / "setup_orbit_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        if not args.keep_debug_usd:
            # Keep it by default in practice because it is useful evidence; this flag is reserved for compatibility.
            pass
        print(json.dumps({"summary": str(summary_path), "errors": errors, "frames": args.frames}, indent=2))
        return 0 if not errors else 1
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
