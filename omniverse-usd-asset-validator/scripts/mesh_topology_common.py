"""Shared mesh topology analysis and weld core for mesh-check and mesh-weld.

Pure pxr + numpy implementation. No scipy dependency: connected components use
numpy label propagation with pointer jumping.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
from pxr import Usd, UsdGeom

TOLERANCE_RELATIVE_DEFAULT = 5e-7
AREA_RELATIVE_EPS = 1e-12


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_mesh_prims(stage: Usd.Stage) -> list:
    return [prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Mesh)]


def _face_offsets(fvc: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = np.concatenate(([0], np.cumsum(fvc)[:-1])).astype(np.int64)
    owner = np.repeat(np.arange(len(fvc), dtype=np.int64), fvc)
    return starts, owner


def _edge_table(fvc: np.ndarray, fvi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Undirected unique edges with valence counts for a polygon mesh."""
    starts, owner = _face_offsets(fvc)
    pos = np.arange(len(fvi), dtype=np.int64) - starts[owner]
    nxt = starts[owner] + ((pos + 1) % fvc[owner])
    pairs = np.sort(np.stack([fvi, fvi[nxt]], axis=1), axis=1)
    unique, counts = np.unique(pairs, axis=0, return_counts=True)
    return unique, counts


def _faces_with_duplicate_corners(fvc: np.ndarray, fvi: np.ndarray) -> np.ndarray:
    """Boolean mask of faces that repeat a corner index after sorting per face."""
    starts, owner = _face_offsets(fvc)
    order = np.lexsort((fvi, owner))
    sorted_vals = fvi[order]
    same_value = sorted_vals[1:] == sorted_vals[:-1]
    same_face = owner[1:] == owner[:-1]
    bad = same_value & same_face
    mask = np.zeros(len(fvc), dtype=bool)
    if bad.any():
        mask[owner[1:][bad]] = True
    return mask


def _connected_component_labels(num: int, edges: np.ndarray) -> np.ndarray:
    """Component label per vertex via min-label propagation + pointer jumping."""
    labels = np.arange(num, dtype=np.int64)
    if num == 0 or len(edges) == 0:
        return labels
    u, v = edges[:, 0], edges[:, 1]
    order_u = np.argsort(u, kind="stable")
    order_v = np.argsort(v, kind="stable")
    us, vs = u[order_u], v[order_v]
    starts_u = np.flatnonzero(np.concatenate(([True], us[1:] != us[:-1])))
    starts_v = np.flatnonzero(np.concatenate(([True], vs[1:] != vs[:-1])))
    keys_u, keys_v = us[starts_u], vs[starts_v]

    def scatter(keys: np.ndarray, starts: np.ndarray, order: np.ndarray, values: np.ndarray) -> None:
        mins = np.minimum.reduceat(values[order], starts)
        labels[keys] = np.minimum(labels[keys], mins)

    for _ in range(256):
        previous = labels.copy()
        m = np.minimum(labels[u], labels[v])
        scatter(keys_u, starts_u, order_u, m)
        scatter(keys_v, starts_v, order_v, m)
        labels = labels[labels]
        if np.array_equal(labels, previous):
            break
    return labels


def read_mesh_arrays(mesh: UsdGeom.Mesh, time: Usd.TimeCode) -> dict[str, Any] | None:
    """Read static mesh arrays and supported primvars. None if animated or malformed."""
    for name in ("points", "faceVertexCounts", "faceVertexIndices"):
        if mesh.GetPrim().GetAttribute(name).GetNumTimeSamples() > 1:
            return None
    points = np.array(mesh.GetPointsAttr().Get(time), dtype=np.float64)
    fvc = np.array(mesh.GetFaceVertexCountsAttr().Get(time), dtype=np.int64)
    fvi = np.array(mesh.GetFaceVertexIndicesAttr().Get(time), dtype=np.int64)
    if points.ndim != 2 or points.shape[0] == 0 or len(fvc) == 0:
        return None
    if int(fvc.sum()) != len(fvi) or len(fvi) == 0:
        return None
    if (fvi < 0).any() or (fvi >= len(points)).any():
        return None

    primvars: list[dict[str, Any]] = []
    for name in ("normals", "primvars:st", "primvars:st0", "displayColor", "displayOpacity"):
        attr = mesh.GetPrim().GetAttribute(name)
        if not attr.HasAuthoredValue() or attr.GetNumTimeSamples() > 1:
            continue
        primvar = UsdGeom.Primvar(attr)
        interp = str(primvar.GetInterpolation() or "constant")
        values = np.array(attr.Get(time))
        if values is None or len(values) == 0:
            continue
        indices = np.array(primvar.GetIndices(time), dtype=np.int64) if primvar.IsIndexed() else None
        primvars.append({"name": name, "interpolation": interp, "values": values, "indices": indices})
    return {"points": points, "face_vertex_counts": fvc, "face_vertex_indices": fvi, "primvars": primvars}


def resolve_tolerance(points: np.ndarray, explicit: float | None) -> float:
    if explicit is not None:
        return float(explicit)
    diag = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
    return TOLERANCE_RELATIVE_DEFAULT * (diag or 1.0)


def analyze_mesh_arrays(points: np.ndarray, fvc: np.ndarray, fvi: np.ndarray, tolerance: float) -> dict[str, Any]:
    """Compute topology health metrics for one mesh. Tolerance is absolute."""
    num_points = len(points)
    unique_edges, valence = _edge_table(fvc, fvi)

    face_counts = np.bincount(fvi, minlength=num_points)
    edge_counts = np.bincount(unique_edges.reshape(-1), minlength=num_points)
    diff = edge_counts - face_counts
    nonmanifold_vertices = int(((diff != 0) & (diff != 1)).sum())

    starts, owner = _face_offsets(fvc)
    pos = np.arange(len(fvi), dtype=np.int64) - starts[owner]
    nxt = starts[owner] + ((pos + 1) % fvc[owner])
    directed = fvi.astype(np.int64) * num_points + fvi[nxt]
    dir_keys, dir_counts = np.unique(directed, return_counts=True)
    fwd = unique_edges[:, 0].astype(np.int64) * num_points + unique_edges[:, 1]
    bwd = unique_edges[:, 1].astype(np.int64) * num_points + unique_edges[:, 0]
    i_f = np.clip(np.searchsorted(dir_keys, fwd), 0, len(dir_keys) - 1)
    i_b = np.clip(np.searchsorted(dir_keys, bwd), 0, len(dir_keys) - 1)
    cf = np.where(dir_keys[i_f] == fwd, dir_counts[i_f], 0)
    cb = np.where(dir_keys[i_b] == bwd, dir_counts[i_b], 0)
    interior = valence == 2
    inconsistent_winding = int((interior & ~((cf == 1) & (cb == 1))).sum())

    repeated_corner_faces = _faces_with_duplicate_corners(fvc, fvi)
    tri_mask = fvc == 3
    zero_area_faces = 0
    if tri_mask.any():
        tri = points[fvi].reshape(-1, 3, 3)[tri_mask]
        diag = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0))) or 1.0
        areas = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        zero_area_faces = int(((areas < AREA_RELATIVE_EPS * diag * diag) & ~repeated_corner_faces[tri_mask]).sum())

    duplicate_faces = 0
    if tri_mask.all():
        sorted_corners = np.sort(fvi.reshape(-1, 3), axis=1).astype(np.int64)
        keys = (sorted_corners[:, 0] * np.int64(num_points) + sorted_corners[:, 1]) * np.int64(num_points) + sorted_corners[:, 2]
        _, fcounts = np.unique(keys, return_counts=True)
        duplicate_faces = int((fcounts - 1).clip(min=0).sum())

    grid = np.round(points / tolerance).astype(np.int64)
    _, group_counts = np.unique(grid, axis=0, return_counts=True)
    multi = group_counts > 1

    labels = _connected_component_labels(num_points, unique_edges)
    components = int((labels == np.arange(num_points, dtype=np.int64)).sum())
    used = np.bincount(fvi, minlength=num_points)

    return {
        "points": num_points,
        "faces": int(len(fvc)),
        "unique_edges": int(len(unique_edges)),
        "boundary_edges": int((valence == 1).sum()),
        "nonmanifold_edges": int((valence > 2).sum()),
        "nonmanifold_vertices": nonmanifold_vertices,
        "inconsistent_winding_edges": inconsistent_winding,
        "degenerate_repeated_corner_faces": int(repeated_corner_faces.sum()),
        "zero_area_faces": zero_area_faces,
        "duplicate_faces": duplicate_faces,
        "coincident_groups": int(multi.sum()),
        "redundant_points": int((group_counts[multi] - 1).sum()) if multi.any() else 0,
        "unreferenced_points": int((used == 0).sum()),
        "components": components,
        "euler_characteristic": int(num_points - len(unique_edges) + len(fvc)),
        "tolerance": float(tolerance),
    }


def build_findings(prim_path: str, metrics: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize topology metrics into findings compatible with the repair-plan model."""
    findings: list[dict[str, str]] = []
    if metrics["coincident_groups"]:
        findings.append({
            "rule": "CoincidentVerticesChecker", "severity": "warning", "prim_path": prim_path,
            "message": f"{metrics['coincident_groups']} positions hold {metrics['redundant_points']} redundant points within tolerance {metrics['tolerance']:.3g}.",
            "repairability": "opt_in",
        })
    if metrics["nonmanifold_vertices"]:
        findings.append({
            "rule": "NonManifoldVertexChecker", "severity": "warning", "prim_path": prim_path,
            "message": f"{metrics['nonmanifold_vertices']} vertices fail the fan test (incident edges minus incident faces not in 0/1).",
            "repairability": "opt_in",
        })
    if metrics["nonmanifold_edges"]:
        findings.append({
            "rule": "NonManifoldEdgeChecker", "severity": "warning", "prim_path": prim_path,
            "message": f"{metrics['nonmanifold_edges']} edges are shared by more than two faces.",
            "repairability": "opt_in",
        })
    if metrics["degenerate_repeated_corner_faces"] or metrics["zero_area_faces"]:
        findings.append({
            "rule": "DegenerateFaceChecker", "severity": "warning", "prim_path": prim_path,
            "message": f"{metrics['degenerate_repeated_corner_faces']} repeated-corner faces, {metrics['zero_area_faces']} zero-area faces.",
            "repairability": "opt_in",
        })
    if metrics["duplicate_faces"]:
        findings.append({
            "rule": "DuplicateFaceChecker", "severity": "warning", "prim_path": prim_path,
            "message": f"{metrics['duplicate_faces']} duplicate faces detected.",
            "repairability": "manual",
        })
    if metrics["unreferenced_points"]:
        findings.append({
            "rule": "UnreferencedPointsChecker", "severity": "info", "prim_path": prim_path,
            "message": f"{metrics['unreferenced_points']} points are not referenced by any face.",
            "repairability": "opt_in",
        })
    if metrics["inconsistent_winding_edges"]:
        findings.append({
            "rule": "WindingConsistencyChecker", "severity": "error", "prim_path": prim_path,
            "message": f"{metrics['inconsistent_winding_edges']} interior edges have inconsistent winding.",
            "repairability": "manual",
        })
    if metrics["boundary_edges"]:
        findings.append({
            "rule": "BoundaryEdgeChecker", "severity": "info", "prim_path": prim_path,
            "message": f"{metrics['boundary_edges']} boundary edges (open surface). Legitimate for non-closed designs.",
            "repairability": "not_applicable",
        })
    return findings


def _slice_primvar(pv: dict[str, Any], keep_face: np.ndarray, fvc: np.ndarray, old_to_new: np.ndarray) -> dict[str, Any] | None:
    interp = pv["interpolation"]
    expected = {
        "constant": 1,
        "uniform": int(len(fvc)),
        "vertex": int(len(old_to_new)),
        "varying": int(len(old_to_new)),
        "faceVarying": int(fvc.sum()),
    }.get(interp)
    element_count = len(pv["indices"]) if pv["indices"] is not None else len(pv["values"])
    if expected is None or expected != element_count:
        return None
    out = dict(pv)
    if interp == "faceVarying":
        corner_mask = np.repeat(keep_face, fvc)
        if pv["indices"] is not None:
            out["indices"] = pv["indices"][corner_mask]
        else:
            out["values"] = pv["values"][corner_mask]
    elif interp in ("vertex", "varying"):
        if pv["indices"] is not None:
            out["indices"] = old_to_new[pv["indices"]]
        else:
            out["values"] = pv["values"][old_to_new]
    return out


def weld_mesh_arrays(data: dict[str, Any], tolerance: float) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Weld coincident points and drop faces degenerated by the weld.

    Returns (new_data, stats) or None when a primvar layout is unsupported.
    """
    points, fvc, fvi = data["points"], data["face_vertex_counts"], data["face_vertex_indices"]
    grid = np.round(points / tolerance).astype(np.int64)
    order = np.lexsort(grid.T)
    sorted_grid = grid[order]
    new_group = np.any(np.diff(sorted_grid, axis=0) != 0, axis=1)
    group_id = np.concatenate(([0], np.cumsum(new_group)))
    old_to_new = np.empty(len(points), dtype=np.int64)
    old_to_new[order] = group_id
    new_points = np.empty((int(group_id[-1]) + 1, points.shape[1]), dtype=points.dtype)
    new_points[old_to_new] = points
    new_fvi = old_to_new[fvi]

    keep_face = ~_faces_with_duplicate_corners(fvc, new_fvi)
    faces_removed = int((~keep_face).sum())

    new_primvars: list[dict[str, Any]] = []
    for pv in data["primvars"]:
        sliced = _slice_primvar(pv, keep_face, fvc, old_to_new)
        if sliced is None:
            return None
        new_primvars.append(sliced)

    if faces_removed:
        corner_mask = np.repeat(keep_face, fvc)
        new_fvi = new_fvi[corner_mask]
        new_fvc = fvc[keep_face]
    else:
        new_fvc = fvc

    stats = {
        "points_before": int(len(points)),
        "points_after": int(len(new_points)),
        "faces_before": int(len(fvc)),
        "faces_after": int(len(new_fvc)),
        "points_removed": int(len(points) - len(new_points)),
        "faces_removed": faces_removed,
        "tolerance": float(tolerance),
    }
    return {"points": new_points, "face_vertex_counts": new_fvc, "face_vertex_indices": new_fvi, "primvars": new_primvars}, stats


def _vt_array_class(attr: object):
    """Resolve the Vt array Python class declared by the attribute, or None."""
    from pxr import Vt

    try:
        cpp = attr.GetTypeName().cppTypeName
    except Exception:
        return None
    if not cpp.startswith("VtArray<"):
        return None
    inner = cpp[len("VtArray<"):].rstrip(">")
    name = inner[2:] if inner.startswith("Gf") else inner
    name = name[0].upper() + name[1:]
    return getattr(Vt, name + "Array", None)


def _to_vt_array(attr: object, values: np.ndarray):
    """Build the Vt array type declared by the attribute from a numpy block."""
    vt_type = _vt_array_class(attr)
    if vt_type is None:
        raise TypeError(f"Unsupported attribute type: {attr.GetTypeName()}")
    casted = values
    if values.ndim > 1:
        if values.dtype != np.float32:
            casted = values.astype(np.float32)
    elif values.dtype.kind == "f" and values.dtype != np.float32:
        casted = values.astype(np.float32)
    elif values.dtype.kind == "i" and values.dtype != np.int32:
        casted = values.astype(np.int32)
    from_numpy = getattr(vt_type, "FromNumpy", None)
    if from_numpy is not None:
        try:
            return from_numpy(casted if casted.flags["C_CONTIGUOUS"] else np.ascontiguousarray(casted))
        except (TypeError, ValueError):
            pass
    return vt_type([tuple(row) for row in casted] if casted.ndim > 1 else list(casted))


def write_mesh_arrays(mesh: UsdGeom.Mesh, data: dict[str, Any], time: Usd.TimeCode) -> None:
    """Author welded arrays back onto the mesh prim (candidate layer only)."""
    points_attr = mesh.GetPointsAttr()
    points_attr.Set(_to_vt_array(points_attr, data["points"]), time)
    counts_attr = mesh.GetFaceVertexCountsAttr()
    counts_attr.Set(_to_vt_array(counts_attr, data["face_vertex_counts"]), time)
    indices_attr = mesh.GetFaceVertexIndicesAttr()
    indices_attr.Set(_to_vt_array(indices_attr, data["face_vertex_indices"]), time)
    extent = [data["points"].min(axis=0).tolist(), data["points"].max(axis=0).tolist()]
    mesh.GetExtentAttr().Set(extent, time)
    for pv in data["primvars"]:
        attr = mesh.GetPrim().GetAttribute(pv["name"])
        primvar = UsdGeom.Primvar(attr)
        attr.Set(_to_vt_array(attr, pv["values"]), time)
        if pv["indices"] is not None and primvar.IsIndexed():
            from pxr import Vt

            primvar.SetIndices(Vt.IntArray.FromNumpy(np.ascontiguousarray(pv["indices"].astype(np.int32))), time)
