#!/usr/bin/env python3
"""Static mesh topology health check for a USD asset.

Writes mesh_topology_report.json (machine-readable), an optional Markdown
companion, and normalized findings compatible with the repair-plan model.
Read-only: the source asset is never modified.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from mesh_topology_common import (
    analyze_mesh_arrays,
    build_findings,
    list_mesh_prims,
    read_mesh_arrays,
    resolve_tolerance,
    sha256_file,
)
from foundation_common import default_out, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--out", type=Path, help="Output directory (default out/<stem>_mesh_topology)")
    parser.add_argument("--tolerance", type=float, help="Absolute weld-detection tolerance (default 5e-7 x bbox diagonal)")
    parser.add_argument("--mesh-path", help="Only analyze the mesh prim at this USD path")
    parser.add_argument("--output-md", type=Path, help="Optional Markdown report path")
    return parser.parse_args()


def report_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Mesh Topology Report", ""]
    lines.append(f"- Asset: `{payload['asset']['path']}`")
    lines.append(f"- Status: **{payload['status']}**")
    lines.append(f"- Meshes analyzed: {payload['summary']['mesh_count']}")
    lines.append("")
    for mesh in payload["meshes"]:
        metrics = mesh["metrics"]
        lines.append(f"## `{mesh['prim_path']}`")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        for key in ("points", "faces", "boundary_edges", "nonmanifold_edges", "nonmanifold_vertices",
                    "coincident_groups", "redundant_points", "degenerate_repeated_corner_faces",
                    "zero_area_faces", "duplicate_faces", "inconsistent_winding_edges",
                    "unreferenced_points", "components"):
            lines.append(f"| {key} | {metrics[key]} |")
        lines.append("")
    if payload["findings"]:
        lines.append("## Findings")
        lines.append("")
        lines.append("| Severity | Rule | Prim | Message |")
        lines.append("|---|---|---|---|")
        for finding in payload["findings"]:
            lines.append(f"| {finding['severity']} | {finding['rule']} | `{finding['prim_path']}` | {finding['message']} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    from pxr import Usd, UsdGeom

    asset = args.asset.resolve()
    out_dir = (args.out or default_out(asset, "mesh_topology")).resolve()
    if not asset.is_file():
        payload = {
            "schema_version": "1.0", "kind": "mesh_topology_report", "status": "blocked",
            "reason": "Input asset does not exist.",
            "asset": {"path": str(asset), "sha256": None},
            "meshes": [], "findings": [],
            "summary": {"mesh_count": 0, "error_count": 0, "warning_count": 0, "info_count": 0},
        }
        write_json(out_dir / "mesh_topology_report.json", payload)
        print(out_dir / "mesh_topology_report.json")
        return 2

    stage = Usd.Stage.Open(str(asset))
    if stage is None:
        payload = {
            "schema_version": "1.0", "kind": "mesh_topology_report", "status": "blocked",
            "reason": "Stage could not be opened.",
            "asset": {"path": str(asset), "sha256": sha256_file(asset)},
            "meshes": [], "findings": [],
            "summary": {"mesh_count": 0, "error_count": 0, "warning_count": 0, "info_count": 0},
        }
        write_json(out_dir / "mesh_topology_report.json", payload)
        print(out_dir / "mesh_topology_report.json")
        return 2

    time = Usd.TimeCode.Default()
    meshes: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    for prim in list_mesh_prims(stage):
        if args.mesh_path and str(prim.GetPath()) != args.mesh_path:
            continue
        data = read_mesh_arrays(UsdGeom.Mesh(prim), time)
        if data is None:
            meshes.append({"prim_path": str(prim.GetPath()), "status": "skipped", "reason": "animated or malformed mesh arrays"})
            continue
        tolerance = resolve_tolerance(data["points"], args.tolerance)
        metrics = analyze_mesh_arrays(data["points"], data["face_vertex_counts"], data["face_vertex_indices"], tolerance)
        meshes.append({"prim_path": str(prim.GetPath()), "status": "analyzed", "metrics": metrics})
        findings.extend(build_findings(str(prim.GetPath()), metrics))

    severities = [f["severity"] for f in findings]
    status = "failed" if "error" in severities else ("warning" if "warning" in severities else "passed")
    payload = {
        "schema_version": "1.0",
        "kind": "mesh_topology_report",
        "status": status,
        "asset": {"path": str(asset), "sha256": sha256_file(asset)},
        "tool": "check_mesh_topology.py",
        "meshes": meshes,
        "findings": findings,
        "summary": {
            "mesh_count": len(meshes),
            "error_count": severities.count("error"),
            "warning_count": severities.count("warning"),
            "info_count": severities.count("info"),
        },
        "note": "Read-only analysis. Boundary edges and high component counts can be legitimate design features.",
    }
    write_json(out_dir / "mesh_topology_report.json", payload)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report_markdown(payload), encoding="utf-8")
    print(out_dir / "mesh_topology_report.json")
    return 0 if status in ("passed", "warning") else 2


if __name__ == "__main__":
    raise SystemExit(main())
