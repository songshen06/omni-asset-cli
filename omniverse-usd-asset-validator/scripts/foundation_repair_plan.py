#!/usr/bin/env python3
"""Convert normalized Foundation findings into a reviewable, non-mutating repair plan."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from foundation_common import load_json, write_json


SAFE_KEYWORDS = ("default prim", "defaultprim", "upaxis", "metersperunit", "extent", "normal")
OPT_IN_KEYWORDS = ("weld", "zero area", "manifold", "collider", "mesh")
MANUAL_KEYWORDS = ("joint", "drive", "limit", "mass", "semantic", "material", "friction")


def repairability(finding: dict[str, Any]) -> str:
    existing = finding.get("repairability")
    if existing in {"safe", "opt_in", "manual", "not_applicable"}:
        return str(existing)
    text = " ".join(str(finding.get(key, "")) for key in ("requirement_id", "feature_id", "message")).lower()
    if any(word in text for word in MANUAL_KEYWORDS):
        return "manual"
    if any(word in text for word in OPT_IN_KEYWORDS):
        return "opt_in"
    if any(word in text for word in SAFE_KEYWORDS):
        return "safe"
    return "manual"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("findings", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = load_json(args.findings)
    items: list[dict[str, Any]] = []
    for index, finding in enumerate(source.get("findings", []), start=1):
        if not isinstance(finding, dict):
            continue
        level = repairability(finding)
        items.append({
            "id": f"foundation-repair-{index:03d}",
            "status": "planned",
            "repairability": level,
            "risk": "low" if level == "safe" else ("controlled" if level == "opt_in" else "high"),
            "source": {key: finding.get(key) for key in ("requirement_id", "feature_id", "prim_path", "message")},
            "action": "apply_safe_overlay" if level == "safe" else "requires_explicit_approval",
            "rollback": "Delete the generated output USD/overlay; the source asset is never overwritten.",
        })
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "ready_for_review",
        "input": source.get("asset"),
        "foundation": source.get("foundation"),
        "source_findings": str(args.findings.resolve()),
        "items": items,
    }
    output = args.out.resolve() / "repair_plan.json"
    write_json(output, payload)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
