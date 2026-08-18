#!/usr/bin/env python3
"""Create a non-destructive Foundation repair overlay and execution record."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from foundation_common import load_json, sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repair_plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply-safe", action="store_true", help="Apply only low-risk, explicitly planned actions")
    args = parser.parse_args()
    plan = load_json(args.repair_plan)
    asset_data = plan.get("input") or {}
    source = Path(str(asset_data.get("path") or ""))
    if not source.is_file():
        raise SystemExit("repair plan does not reference a readable source asset")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    selected = [item for item in plan.get("items", []) if isinstance(item, dict) and item.get("repairability") == "safe"]
    copied = out / f"{source.stem}.foundation_candidate{source.suffix}"
    # A byte-for-byte copy is the safe default until a requirement supplies a concrete authoring value.
    # It preserves the source package and gives downstream Inspector tooling a stable candidate path.
    shutil.copy2(source, copied)
    status = "applied_safe_noop" if args.apply_safe and not selected else ("review_required" if selected else "no_safe_repairs")
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "status": status,
        "source": {"path": str(source.resolve()), "sha256": sha256_file(source)},
        "candidate": {"path": str(copied), "sha256": sha256_file(copied)},
        "applied_items": [],
        "pending_safe_items": selected,
        "reason": (
            "No concrete authoring values were supplied by the normalized findings; candidate is an immutable-source copy."
            if selected else "No safe repair items were present."
        ),
        "rollback": f"Delete {copied}; source asset remains unchanged.",
    }
    write_json(out / "repair_apply.json", payload)
    print(out / "repair_apply.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
