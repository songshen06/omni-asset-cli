#!/usr/bin/env python3
"""Measure authored collider envelopes against visual geometry per rigid body.

This is a static authoring audit.  It can show whether collision prims extend
outside the visual geometry that belongs to the same rigid body, but it cannot
measure PhysX contact offsets, cooked SDF/HACD shapes, or motion-time joint
pose errors.  Those need an Isaac Sim runtime probe.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from foundation_common import sha256_file, write_json


def _range_to_bounds(value: Any) -> list[list[float]] | None:
    if value.IsEmpty():
        return None
    minimum = value.GetMin()
    maximum = value.GetMax()
    return [[float(minimum[index]) for index in range(3)], [float(maximum[index]) for index in range(3)]]


def _union(bounds: list[list[list[float]]]) -> list[list[float]] | None:
    if not bounds:
        return None
    return [
        [min(item[0][axis] for item in bounds) for axis in range(3)],
        [max(item[1][axis] for item in bounds) for axis in range(3)],
    ]


def _owner_path(prim: Any, rigid_body_api: Any) -> str | None:
    current = prim
    while current and current.IsValid():
        if current.HasAPI(rigid_body_api):
            return str(current.GetPath())
        current = current.GetParent()
    return None


def _extent(bounds: list[list[float]]) -> list[float]:
    return [bounds[1][axis] - bounds[0][axis] for axis in range(3)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=0.002, help="World-unit envelope tolerance (default: 2 mm).")
    args = parser.parse_args()
    asset = args.asset.resolve()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "audit": "rigid-body-geometry-fidelity",
        "evidence_level": "static-authored-geometry",
        "asset": {"path": str(asset), "sha256": sha256_file(asset) if asset.is_file() else None},
        "tolerance_world_units": args.tolerance,
        "status": "blocked",
        "limitations": [
            "This compares authored world-space AABBs only; it is not a runtime contact-distance measurement.",
            "It cannot observe PhysX cooking, SDF/HACD approximation, contactOffset/restOffset, or joint-motion pose drift.",
        ],
        "bodies": [],
        "findings": [],
    }
    try:
        from pxr import Usd, UsdGeom, UsdPhysics  # type: ignore
    except ModuleNotFoundError as exc:
        report["reason"] = f"OpenUSD runtime unavailable: {exc}"
        write_json(args.out.resolve() / "rigid_body_geometry_fidelity.json", report)
        return 2
    stage = Usd.Stage.Open(str(asset))
    if not stage:
        report["reason"] = "USD stage could not be opened."
        write_json(args.out.resolve() / "rigid_body_geometry_fidelity.json", report)
        return 2

    bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_], useExtentsHint=True)
    body_paths = sorted(str(prim.GetPath()) for prim in stage.Traverse() if prim.HasAPI(UsdPhysics.RigidBodyAPI))
    visual_bounds: dict[str, list[list[list[float]]]] = {path: [] for path in body_paths}
    collider_bounds: dict[str, list[list[list[float]]]] = {path: [] for path in body_paths}
    visual_paths: dict[str, list[str]] = {path: [] for path in body_paths}
    collider_paths: dict[str, list[str]] = {path: [] for path in body_paths}
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Boundable):
            continue
        owner = _owner_path(prim, UsdPhysics.RigidBodyAPI)
        if owner not in visual_bounds:
            continue
        bounds = _range_to_bounds(bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange())
        if bounds is None:
            continue
        path = str(prim.GetPath())
        visual_bounds[owner].append(bounds)
        visual_paths[owner].append(path)
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            collider_bounds[owner].append(bounds)
            collider_paths[owner].append(path)

    overflow_total = 0
    uncovered_total = 0
    for body_path in body_paths:
        visual = _union(visual_bounds[body_path])
        collider = _union(collider_bounds[body_path])
        body: dict[str, Any] = {
            "path": body_path,
            "visual_prim_count": len(visual_paths[body_path]),
            "collider_prim_count": len(collider_paths[body_path]),
            "visual_bounds_world": visual,
            "collider_bounds_world": collider,
            "visual_paths": visual_paths[body_path],
            "collider_paths": collider_paths[body_path],
            "classification": "not-measurable",
        }
        if visual is None or collider is None:
            body["classification"] = "incomplete-authored-coverage"
            report["findings"].append({"requirement_id": "RB.GEO.002", "severity": "warning", "body": body_path, "message": "Rigid body has visual geometry or colliders missing from the static comparison.", "repairability": "manual"})
            uncovered_total += 1
        else:
            overflow = [max(0.0, visual[0][axis] - collider[0][axis], collider[1][axis] - visual[1][axis]) for axis in range(3)]
            undercoverage = [max(0.0, collider[0][axis] - visual[0][axis], visual[1][axis] - collider[1][axis]) for axis in range(3)]
            body.update({"visual_extent_world": _extent(visual), "collider_extent_world": _extent(collider), "collider_overflow_world": overflow, "visual_undercoverage_world": undercoverage})
            if any(value > args.tolerance for value in overflow):
                body["classification"] = "collider-envelope-larger-than-visual"
                report["findings"].append({"requirement_id": "RB.GEO.001", "severity": "error", "body": body_path, "overflow_world": overflow, "message": "Collider union extends outside this rigid body's visual AABB beyond tolerance; candidate air-wall authoring evidence.", "repairability": "manual"})
                overflow_total += 1
            elif any(value > args.tolerance for value in undercoverage):
                body["classification"] = "visual-geometry-outside-collider-union"
                report["findings"].append({"requirement_id": "RB.GEO.002", "severity": "warning", "body": body_path, "undercoverage_world": undercoverage, "message": "Visual geometry extends beyond collider union; may be intentional simplified collision, but needs owner confirmation.", "repairability": "manual"})
                uncovered_total += 1
            else:
                body["classification"] = "aabb-aligned-within-tolerance"
        report["bodies"].append(body)
    report["summary"] = {"rigid_body_count": len(body_paths), "collider_overflow_body_count": overflow_total, "undercoverage_body_count": uncovered_total}
    report["status"] = "failed" if overflow_total else "passed"
    write_json(args.out.resolve() / "rigid_body_geometry_fidelity.json", report)
    print(args.out.resolve() / "rigid_body_geometry_fidelity.json")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
