#!/usr/bin/env python3
"""Run one zero-gravity sphere-to-cart side-collider probe in Isaac Sim."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--side", choices=("pos_x", "neg_x", "pos_y", "neg_y"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=240)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--radius-m", type=float, default=0.04)
    parser.add_argument("--speed-mps", type=float, default=0.50)
    args = parser.parse_args()
    asset = args.asset.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"schema_version": "1.0", "test": "cart-side-sphere-probe", "side": args.side, "asset": str(asset), "status": "blocked"}
    if not asset.is_file():
        report["reason"] = "asset does not exist"
        (out / "sphere_probe.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 2

    from isaacsim import SimulationApp  # type: ignore

    app = SimulationApp({"headless": True})
    try:
        from pxr import Gf, PhysicsSchemaTools, UsdGeom, UsdPhysics  # type: ignore
        from runtime_physics_harness import (  # type: ignore
            _as_tuple,
            _read_prim_position,
            _read_box_velocity,
            _sdf_path_from_contact_id,
            _strip_dynamic_physics_apis,
            align_asset_to_ground,
            apply_contact_report,
            collect_collision_paths,
            compute_world_bbox,
            create_base_stage,
            create_input_asset_prim,
        )
        import omni.timeline  # type: ignore
        import omni.usd  # type: ignore
        from omni.physx import get_physx_simulation_interface  # type: ignore

        stage_path = out / f"cart_side_sphere_{args.side}.usda"
        stage = create_base_stage(stage_path, args.fps)
        UsdPhysics.Scene(stage.GetPrimAtPath("/World/PhysicsScene")).CreateGravityMagnitudeAttr().Set(0.0)
        cart = create_input_asset_prim(stage, asset)
        cart_range = align_asset_to_ground(stage, cart)
        authored_collider_paths = collect_collision_paths(cart)
        # This diagnostic isolates the authored collider set.  Do not use
        # apply_static_colliders here: that helper is appropriate when an
        # unprepared visual asset needs temporary collision, but it would add
        # CollisionAPI to every Gprim and conceal an air-wall authoring defect.
        _strip_dynamic_physics_apis(cart)
        collider_paths = collect_collision_paths(cart)
        if not collider_paths:
            raise RuntimeError("No authored CollisionAPI paths remain after freezing the cart")
        minimum, maximum = cart_range.GetMin(), cart_range.GetMax()
        bbox_cache = UsdGeom.BBoxCache(stage.GetTimeCodesPerSecond(), [UsdGeom.Tokens.default_], useExtentsHint=True)
        radius = float(args.radius_m)
        clearance = max(radius * 3.0, 0.08)
        directions = {
            "pos_x": (Gf.Vec3d(1, 0, 0), Gf.Vec3f(-1, 0, 0)),
            "neg_x": (Gf.Vec3d(-1, 0, 0), Gf.Vec3f(1, 0, 0)),
            "pos_y": (Gf.Vec3d(0, 1, 0), Gf.Vec3f(0, -1, 0)),
            "neg_y": (Gf.Vec3d(0, -1, 0), Gf.Vec3f(0, 1, 0)),
        }
        outward, velocity_direction = directions[args.side]
        # Cart_v2 is an open frame.  Aim at an authored outer collider rather
        # than its AABB centre, which can be a real empty opening.
        candidate_paths = [path for path in authored_collider_paths if "/Frame/" in path] or authored_collider_paths
        axis = 0 if outward[0] else 1
        ranked: list[tuple[float, str, Any]] = []
        for path in candidate_paths:
            prim = stage.GetPrimAtPath(path)
            bounds = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
            if bounds.IsEmpty():
                continue
            collider_center = (bounds.GetMin() + bounds.GetMax()) * 0.5
            signed_extent = float(collider_center[axis]) * (1.0 if outward[axis] > 0 else -1.0)
            ranked.append((signed_extent, path, collider_center))
        if not ranked:
            raise RuntimeError("No authored collider bounds available for side probe")
        _extent, target_collider, target_center = max(ranked, key=lambda item: item[0])
        boundary = float(maximum[axis] if outward[axis] > 0 else minimum[axis])
        start = Gf.Vec3d(target_center)
        start[axis] = boundary + float(outward[axis]) * (clearance + radius)
        sphere_path = "/World/ProbeSphere"
        sphere = UsdGeom.Sphere.Define(stage, sphere_path)
        sphere.CreateRadiusAttr(radius)
        sphere.CreateExtentAttr([Gf.Vec3f(-radius, -radius, -radius), Gf.Vec3f(radius, radius, radius)])
        sphere.AddTranslateOp().Set(start)
        sphere_prim = sphere.GetPrim()
        UsdPhysics.CollisionAPI.Apply(sphere_prim)
        body = UsdPhysics.RigidBodyAPI.Apply(sphere_prim)
        velocity = velocity_direction * float(args.speed_mps)
        body.CreateVelocityAttr().Set(velocity)
        body.CreateAngularVelocityAttr().Set(Gf.Vec3f(0, 0, 0))
        UsdPhysics.MassAPI.Apply(sphere_prim).CreateMassAttr().Set(1.0)
        apply_contact_report(sphere_prim)
        stage.GetRootLayer().Save()

        context = omni.usd.get_context()
        context.open_stage(str(stage_path))
        for _ in range(8):
            app.update()
        runtime_stage = context.get_stage()
        if runtime_stage is None:
            raise RuntimeError("Isaac Sim did not open generated probe stage")
        timeline = omni.timeline.get_timeline_interface()
        physx = get_physx_simulation_interface()
        timeline.set_current_time(0.0)
        timeline.play()
        samples: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        cart_root = "/World/InputAsset"
        for frame in range(args.frames):
            position = _read_prim_position(runtime_stage, sphere_path)
            current_velocity = _read_box_velocity(runtime_stage, sphere_path)
            samples.append({"frame": frame, "position": list(position), "velocity": list(current_velocity)})
            app.update()
            headers, _points = physx.get_contact_report()
            for header in headers:
                paths = [_sdf_path_from_contact_id(value) for value in (header.actor0, header.actor1, header.collider0, header.collider1)]
                if sphere_path not in paths or not any(path == cart_root or path.startswith(cart_root + "/") for path in paths):
                    continue
                events.append({"frame": frame, "actor0": paths[0], "actor1": paths[1], "collider0": paths[2], "collider1": paths[3], "num_contacts": int(header.num_contact_data)})
        timeline.stop()
        first = events[0] if events else None
        report.update({
            "status": "passed" if first else "failed",
            "method": "Isaac Sim PhysX contact report",
            "gravity_magnitude": 0.0,
            "sphere": {"path": sphere_path, "radius_m": radius, "start_position": list(_as_tuple(start)), "initial_velocity_mps": list(_as_tuple(velocity))},
            "cart": {"root": cart_root, "bbox_min": list(_as_tuple(minimum)), "bbox_max": list(_as_tuple(maximum)), "authored_collider_count": len(authored_collider_paths), "active_collider_count": len(collider_paths), "collider_policy": "preserve authored CollisionAPI only; do not add colliders to visual Gprims", "target_collider": target_collider, "target_center": list(_as_tuple(target_center)), "joint_and_rigid_body_policy": "disabled only in generated probe stage"},
            "frames": args.frames, "fps": args.fps, "contact_detected": bool(first), "first_contact": first,
            "contact_event_count": len(events), "last_sample": samples[-1] if samples else None, "samples": samples, "contact_events": events[:50],
        })
    except Exception as exc:
        report.update({"status": "blocked", "reason": f"{type(exc).__name__}: {exc}"})
    finally:
        # Isaac Sim may terminate the Python process as part of app.close().
        # Persist the probe evidence first so a completed simulation is never
        # reported as an empty output directory.
        (out / "sphere_probe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        app.close()
    print(out / "sphere_probe.json")
    return 0 if report.get("status") == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
