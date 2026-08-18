#!/usr/bin/env python3
"""Validate articulated-cart topology and scoped physics authoring rules."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from foundation_common import sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expected-rigid-bodies", type=int, default=13)
    parser.add_argument("--expected-joints", type=int, default=12)
    parser.add_argument(
        "--scope",
        choices=["topology", "physics-structure"],
        default="topology",
        help="physics-structure additionally enforces RB.006 and RB.COL.002 equivalents.",
    )
    args = parser.parse_args()
    asset = args.asset.resolve()
    report: dict[str, Any] = {
        "schema_version": "1.0", "policy": "articulated-cart", "asset": {"path": str(asset), "sha256": sha256_file(asset)},
        "status": "blocked", "checks": {}, "findings": [],
    }
    try:
        from pxr import Usd, UsdGeom, UsdPhysics  # type: ignore
    except ModuleNotFoundError as exc:
        report["reason"] = f"OpenUSD runtime unavailable: {exc}"
        write_json(args.out.resolve() / "articulated_policy.json", report)
        return 2
    stage = Usd.Stage.Open(str(asset))
    if not stage:
        report["reason"] = "USD stage could not be opened."
        write_json(args.out.resolve() / "articulated_policy.json", report)
        return 2
    bodies: set[str] = set()
    joints: list[dict[str, Any]] = []
    colliders = 0
    nested_without_reset: list[str] = []
    non_mesh_mesh_colliders: list[str] = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            bodies.add(path)
            ancestor = prim.GetParent()
            while ancestor and ancestor.IsValid() and not ancestor.HasAPI(UsdPhysics.RigidBodyAPI):
                ancestor = ancestor.GetParent()
            if ancestor and ancestor.IsValid() and ancestor.HasAPI(UsdPhysics.RigidBodyAPI):
                order = prim.GetAttribute("xformOpOrder").Get() or []
                if "!resetXformStack!" not in order:
                    nested_without_reset.append(path)
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            colliders += 1
        if prim.HasAPI(UsdPhysics.MeshCollisionAPI) and not prim.IsA(UsdGeom.Mesh):
            non_mesh_mesh_colliders.append(path)
        if prim.IsA(UsdPhysics.Joint):
            body0 = [str(target) for target in UsdPhysics.Joint(prim).GetBody0Rel().GetTargets()]
            body1 = [str(target) for target in UsdPhysics.Joint(prim).GetBody1Rel().GetTargets()]
            joints.append({"path": path, "body0": body0, "body1": body1, "type": prim.GetTypeName()})
    invalid = [joint for joint in joints if len(joint["body0"]) != 1 or len(joint["body1"]) != 1 or joint["body0"] == joint["body1"] or joint["body0"][0] not in bodies or joint["body1"][0] not in bodies]
    adjacency: dict[str, set[str]] = {body: set() for body in bodies}
    for joint in joints:
        if len(joint["body0"]) == len(joint["body1"]) == 1 and joint["body0"][0] in adjacency and joint["body1"][0] in adjacency:
            adjacency[joint["body0"][0]].add(joint["body1"][0]); adjacency[joint["body1"][0]].add(joint["body0"][0])
    reachable: set[str] = set()
    if bodies:
        todo = [next(iter(bodies))]
        while todo:
            node = todo.pop()
            if node not in reachable:
                reachable.add(node); todo.extend(adjacency[node] - reachable)
    report["checks"] = {"rigid_body_count": len(bodies), "joint_count": len(joints), "collider_count": colliders, "invalid_joint_count": len(invalid), "isolated_rigid_bodies": sorted(bodies - reachable), "nested_rigid_bodies_without_reset": nested_without_reset, "non_mesh_mesh_colliders": non_mesh_mesh_colliders}
    if len(bodies) != args.expected_rigid_bodies: report["findings"].append({"severity": "error", "message": f"Expected {args.expected_rigid_bodies} rigid bodies, found {len(bodies)}.", "repairability": "manual"})
    if len(joints) != args.expected_joints: report["findings"].append({"severity": "error", "message": f"Expected {args.expected_joints} joints, found {len(joints)}.", "repairability": "manual"})
    if invalid: report["findings"].append({"severity": "error", "message": "One or more joint body relationships are invalid.", "repairability": "manual", "joints": invalid})
    if bodies - reachable: report["findings"].append({"severity": "error", "message": "Rigid-body graph contains isolated bodies.", "repairability": "manual"})
    if args.scope == "physics-structure" and nested_without_reset:
        report["findings"].append({"requirement_id": "RB.006", "severity": "error", "message": "Nested rigid bodies require !resetXformStack! or a flat body hierarchy.", "repairability": "manual", "prims": nested_without_reset})
    if args.scope == "physics-structure" and non_mesh_mesh_colliders:
        report["findings"].append({"requirement_id": "RB.COL.002", "severity": "error", "message": "PhysicsMeshCollisionAPI is only valid on UsdGeomMesh prims.", "repairability": "safe", "prims": non_mesh_mesh_colliders})
    report["status"] = "passed" if not report["findings"] else "failed"
    write_json(args.out.resolve() / "articulated_policy.json", report)
    print(args.out.resolve() / "articulated_policy.json")
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
