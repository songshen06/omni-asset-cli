#!/usr/bin/env python3
"""Create a non-destructive RB.COL.002 repair candidate from a focused policy report."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from foundation_common import load_json, sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.asset.resolve()
    policy = load_json(args.policy)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": "1.0", "status": "blocked",
        "source": {"path": str(source), "sha256": sha256_file(source) if source.is_file() else None},
        "candidate": None, "applied": [],
        "deferred": {"requirement_id": "RB.006", "reason": "Nested rigid-body hierarchy and joint-frame changes require approval."},
    }
    if not source.is_file():
        report["reason"] = "Input asset does not exist."
        write_json(out / "safe_repair.json", report)
        return 2
    try:
        from pxr import Usd, UsdPhysics  # type: ignore
    except ModuleNotFoundError as exc:
        report["reason"] = f"OpenUSD runtime unavailable: {exc}"
        write_json(out / "safe_repair.json", report)
        return 2
    targets: list[str] = []
    for finding in policy.get("findings", []):
        if isinstance(finding, dict) and finding.get("requirement_id") == "RB.COL.002":
            targets.extend(item for item in finding.get("prims", []) if isinstance(item, str))
    candidate = out / f"{source.stem}.rb_col_002_candidate{source.suffix}"
    shutil.copy2(source, candidate)
    stage = Usd.Stage.Open(str(candidate))
    if not stage:
        report["reason"] = "Candidate stage could not be opened."
        write_json(out / "safe_repair.json", report)
        return 2
    for path in sorted(set(targets)):
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid() or not prim.HasAPI(UsdPhysics.MeshCollisionAPI):
            continue
        prim.RemoveAPI(UsdPhysics.MeshCollisionAPI)
        prim.RemoveProperty("physics:approximation")
        report["applied"].append({"requirement_id": "RB.COL.002", "prim": path, "action": "Removed PhysicsMeshCollisionAPI and physics:approximation; kept PhysicsCollisionAPI and visual geometry."})
    stage.GetRootLayer().Save()
    report["candidate"] = {"path": str(candidate), "sha256": sha256_file(candidate)}
    report["status"] = "applied_safe" if report["applied"] else "no_targets"
    report["rollback"] = f"Delete {candidate}; source asset remains unchanged."
    write_json(out / "safe_repair.json", report)
    print(out / "safe_repair.json")
    return 0 if report["status"] == "applied_safe" else 2


if __name__ == "__main__":
    raise SystemExit(main())
