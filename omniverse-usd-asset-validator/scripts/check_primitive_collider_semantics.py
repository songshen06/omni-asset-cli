#!/usr/bin/env python3
"""Detect ambiguous mesh-collision schemas authored on USD primitives."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from foundation_common import sha256_file, write_json


RULE_ID = "RB.COL.002"
REPAIR_ACTION = "remove_non_mesh_mesh_collision_api_and_approximation"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asset = args.asset.resolve()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "policy": "primitive-collider-semantics",
        "asset": {"path": str(asset), "sha256": sha256_file(asset)},
        "status": "blocked",
        "checks": {},
        "findings": [],
    }
    try:
        from pxr import Usd, UsdGeom, UsdPhysics  # type: ignore
    except ModuleNotFoundError as exc:
        report["reason"] = f"OpenUSD runtime unavailable: {exc}"
        write_json(args.out.resolve() / "primitive_collider_audit.json", report)
        return 2
    stage = Usd.Stage.Open(str(asset))
    if not stage:
        report["reason"] = "USD stage could not be opened."
        write_json(args.out.resolve() / "primitive_collider_audit.json", report)
        return 2

    collider_count = 0
    conflicts: list[dict[str, Any]] = []
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            collider_count += 1
        if not prim.HasAPI(UsdPhysics.MeshCollisionAPI) or prim.IsA(UsdGeom.Mesh):
            continue
        approximation = prim.GetAttribute("physics:approximation").Get()
        conflicts.append({
            "rule_id": RULE_ID,
            "severity": "error",
            "prim": str(prim.GetPath()),
            "prim_type": prim.GetTypeName(),
            "mesh_collision_api": True,
            "physics_approximation": str(approximation) if approximation is not None else None,
            "repairability": "safe",
            "repair": {
                "owner": "usd-simready-inspector",
                "action": REPAIR_ACTION,
                "preserves": ["PhysicsCollisionAPI", "geometry", "transforms", "materials", "rigid_bodies", "joints"],
            },
        })
    report["checks"] = {
        "collision_api_count": collider_count,
        "non_mesh_mesh_collision_conflict_count": len(conflicts),
    }
    report["findings"] = conflicts
    report["status"] = "passed" if not conflicts else "failed"
    write_json(args.out.resolve() / "primitive_collider_audit.json", report)
    print(args.out.resolve() / "primitive_collider_audit.json")
    return 0 if not conflicts else 2


if __name__ == "__main__":
    raise SystemExit(main())
