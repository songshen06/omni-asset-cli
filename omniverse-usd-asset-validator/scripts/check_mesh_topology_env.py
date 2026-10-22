#!/usr/bin/env python3
"""Report whether the current environment can run mesh-check and mesh-weld.

mesh-check and mesh-weld require only the OpenUSD Python bindings (pxr) and
numpy. Both are already installed by the `validator` extra
(`pip install -e ".[validator]"` via omniverse-asset-validator[usd,numpy]).
scipy is intentionally NOT required: connected components use a numpy
label-propagation implementation.

This checker also runs an in-memory smoke test: it builds a synthetic mesh
with coincident vertices, analyzes it, welds it, and re-verifies the result.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from typing import Any

MESH_COMMANDS = ("mesh-check", "mesh-weld")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a JSON payload instead of plain text")
    return parser.parse_args()


def probe_imports() -> tuple[dict[str, Any], bool]:
    checks: dict[str, Any] = {}
    ok = True
    try:
        import numpy

        checks["numpy"] = {"installed": True, "version": numpy.__version__}
    except ImportError:
        checks["numpy"] = {"installed": False}
        ok = False
    try:
        from pxr import Usd, UsdGeom  # noqa: F401

        checks["pxr"] = {"installed": True, "usd_version": str(Usd.GetVersion())}
    except ImportError as error:
        checks["pxr"] = {"installed": False, "error": str(error)}
        ok = False
    try:
        import scipy  # noqa: F401

        checks["scipy"] = {"installed": True, "required": False}
    except ImportError:
        checks["scipy"] = {"installed": False, "required": False}
    return checks, ok


def smoke_test() -> dict[str, Any]:
    """Build a two-triangle strip with split coincident vertices, then weld it."""
    import numpy as np
    from pxr import Usd, UsdGeom

    from mesh_topology_common import (
        analyze_mesh_arrays,
        read_mesh_arrays,
        resolve_tolerance,
        weld_mesh_arrays,
        write_mesh_arrays,
    )

    result: dict[str, Any] = {}
    points = np.array(
        [
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0 + 1e-9], [1.0, 1.0, 1e-9 + 0.0], [2.0, 0.0, 0.0], [2.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    fvc = np.array([3, 3, 3, 3], dtype=np.int64)
    fvi = np.array([0, 1, 2, 0, 2, 3, 4, 6, 7, 4, 7, 5], dtype=np.int64)

    tolerance = resolve_tolerance(points, None)
    before = analyze_mesh_arrays(points, fvc, fvi, tolerance)
    result["before"] = {
        "points": before["points"],
        "coincident_groups": before["coincident_groups"],
        "components": before["components"],
    }
    result["analysis_ok"] = before["coincident_groups"] > 0 and before["components"] > 1

    welded = weld_mesh_arrays(
        {"points": points, "face_vertex_counts": fvc, "face_vertex_indices": fvi, "primvars": []}, tolerance
    )
    if welded is None:
        result["weld_ok"] = False
        result["reason"] = "weld_mesh_arrays returned None on a supported layout"
        return result
    new_data, stats = welded
    after = analyze_mesh_arrays(new_data["points"], new_data["face_vertex_counts"], new_data["face_vertex_indices"], tolerance)
    result["after"] = {
        "points": after["points"],
        "coincident_groups": after["coincident_groups"],
        "components": after["components"],
    }
    result["weld_ok"] = (
        after["coincident_groups"] == 0
        and after["components"] == 1
        and stats["faces_removed"] == 0
        and after["faces"] == 4
    )

    stage = Usd.Stage.CreateInMemory()
    prim = UsdGeom.Mesh.Define(stage, "/SmokeTest/mesh")
    write_mesh_arrays(prim, new_data, Usd.TimeCode.Default())
    reread = read_mesh_arrays(prim, Usd.TimeCode.Default())
    result["roundtrip_ok"] = reread is not None and len(reread["points"]) == int(after["points"]) and len(reread["face_vertex_indices"]) == 12
    result["ok"] = bool(result["analysis_ok"] and result["weld_ok"] and result["roundtrip_ok"])
    return result


def main() -> int:
    args = parse_args()
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "kind": "mesh_topology_env_check",
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "commands": list(MESH_COMMANDS),
    }
    py = sys.version_info
    payload["python_supported"] = (3, 10) <= (py.major, py.minor) <= (3, 12)

    checks, imports_ok = probe_imports()
    payload["dependencies"] = checks
    payload["install_hint"] = 'python3 -m pip install -e ".[validator]"  # provides pxr + numpy'

    smoke: dict[str, Any] = {"ok": False, "reason": "skipped: pxr or numpy missing"}
    if imports_ok:
        try:
            smoke = smoke_test()
        except Exception as error:  # noqa: BLE001 - env check must report, not crash
            smoke = {"ok": False, "reason": f"{type(error).__name__}: {error}"}
    payload["smoke_test"] = smoke
    payload["status"] = "ready" if (payload["python_supported"] and imports_ok and smoke.get("ok")) else "not_ready"

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Python: {payload['python']} ({'supported' if payload['python_supported'] else 'unsupported, expected 3.10-3.12'})")
        print(f"Platform: {payload['platform']}")
        numpy_info = checks["numpy"]
        print(f"numpy: {'installed ' + str(numpy_info.get('version')) if numpy_info['installed'] else 'NOT INSTALLED (required)'}")
        pxr_info = checks["pxr"]
        if pxr_info["installed"]:
            print(f"pxr (OpenUSD): installed, Usd.GetVersion()={pxr_info['usd_version']}")
        else:
            print(f"pxr (OpenUSD): NOT INSTALLED (required) - {pxr_info.get('error', '')}")
        print(f"scipy: {'installed (unused by mesh commands)' if checks['scipy']['installed'] else 'not installed (not required)'}")
        print(f"smoke test: {'PASSED' if smoke.get('ok') else 'FAILED - ' + str(smoke.get('reason', 'see JSON payload'))}")
        print(f"status: {payload['status']}")
        if payload["status"] != "ready":
            print(f"fix: {payload['install_hint']}")
    return 0 if payload["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
