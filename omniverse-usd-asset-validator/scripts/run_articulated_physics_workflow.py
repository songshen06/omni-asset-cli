#!/usr/bin/env python3
"""Run the focused articulated-physics workflow without gating on mass or grasp data."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from foundation_common import sha256_file, write_json


SCRIPTS_DIR = Path(__file__).resolve().parent
FOCUS_REQUIREMENTS = ("RB.006", "RB.COL.002")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--foundation-root", type=Path, required=True)
    parser.add_argument("--foundation-python", type=Path, required=True)
    parser.add_argument("--foundation-tag", default="v2026.04.1")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    asset = args.asset.resolve()
    out = args.out.resolve()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "workflow": "articulated-physics-structure",
        "profile": {"id": "Prop-Robotics-Physx", "version": "1.0.0", "tag": args.foundation_tag},
        "scope": {"blocking_requirements": list(FOCUS_REQUIREMENTS), "deferred": ["RB.007 mass", "GSP.001 grasp", "PMT.001 physics material"]},
        "asset": {"path": str(asset), "sha256": sha256_file(asset) if asset.is_file() else None},
        "status": "blocked", "artifacts": {}, "findings": [],
    }
    if not asset.is_file():
        report["reason"] = "Input asset does not exist."
        write_json(out / "workflow.json", report)
        return 2

    foundation_out = out / "foundation"
    policy_out = out / "physics_structure"
    repair_out = out / "repair_candidate"
    candidate_policy_out = out / "candidate_physics_structure"
    candidate_foundation_out = out / "candidate_foundation"
    geometry_out = out / "rigid_body_geometry"
    foundation_command = [
        sys.executable, str(SCRIPTS_DIR / "run_foundation_validation.py"), str(asset),
        "--package", "articulated-asset", "--foundation-tag", args.foundation_tag,
        "--foundation-root", str(args.foundation_root), "--foundation-python", str(args.foundation_python),
        "--official-cli", "--shadow", "--out", str(foundation_out),
    ]
    policy_command = [
        str(args.foundation_python), str(SCRIPTS_DIR / "check_articulated_cart_policy.py"), str(asset),
        "--scope", "physics-structure", "--out", str(policy_out),
    ]
    foundation_run = subprocess.run(foundation_command, capture_output=True, text=True, check=False)
    policy_run = subprocess.run(policy_command, capture_output=True, text=True, check=False)
    geometry_run = subprocess.run(
        [str(args.foundation_python), str(SCRIPTS_DIR / "check_rigid_body_geometry_fidelity.py"), str(asset), "--out", str(geometry_out)],
        capture_output=True,
        text=True,
        check=False,
    )
    foundation_report = foundation_out / "foundation_validation.json"
    policy_report = policy_out / "articulated_policy.json"
    geometry_report = geometry_out / "rigid_body_geometry_fidelity.json"
    report["artifacts"] = {"foundation": str(foundation_report), "policy": str(policy_report), "geometry_fidelity": str(geometry_report)}
    try:
        foundation_data = json.loads(foundation_report.read_text(encoding="utf-8"))
        raw = json.loads((foundation_out / "foundation_raw.json").read_text(encoding="utf-8"))
        upstream_ran = any(value.get("profile_id") == "Prop-Robotics-Physx" for value in raw.values() if isinstance(value, dict))
    except (OSError, json.JSONDecodeError):
        foundation_data, upstream_ran = {}, False
    try:
        policy_data = json.loads(policy_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        policy_data = {}
    report["upstream_profile_registered_and_ran"] = upstream_ran
    report["executions"] = {"foundation_returncode": foundation_run.returncode, "policy_returncode": policy_run.returncode}
    try:
        geometry_data = json.loads(geometry_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        geometry_data = {}
    report["geometry_fidelity"] = {"status": geometry_data.get("status"), "summary": geometry_data.get("summary"), "evidence_level": geometry_data.get("evidence_level")}
    report["executions"]["geometry_fidelity_returncode"] = geometry_run.returncode
    report["findings"] = [finding for finding in policy_data.get("findings", []) if finding.get("requirement_id") in FOCUS_REQUIREMENTS]
    repair_report = repair_out / "safe_repair.json"
    repair_run = subprocess.run(
        [str(args.foundation_python), str(SCRIPTS_DIR / "apply_articulated_physics_safe_repair.py"), str(asset), str(policy_report), "--out", str(repair_out)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        repair_data = json.loads(repair_report.read_text(encoding="utf-8"))
        candidate_path = Path(str(repair_data.get("candidate", {}).get("path", "")))
    except (OSError, json.JSONDecodeError, TypeError):
        repair_data, candidate_path = {}, Path()
    candidate_policy_report = candidate_policy_out / "articulated_policy.json"
    if candidate_path.is_file():
        candidate_policy_run = subprocess.run(
            [str(args.foundation_python), str(SCRIPTS_DIR / "check_articulated_cart_policy.py"), str(candidate_path), "--scope", "physics-structure", "--out", str(candidate_policy_out)],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        candidate_policy_run = None
    if candidate_path.is_file():
        candidate_foundation_run = subprocess.run(
            [
                sys.executable, str(SCRIPTS_DIR / "run_foundation_validation.py"), str(candidate_path),
                "--package", "articulated-asset", "--foundation-tag", args.foundation_tag,
                "--foundation-root", str(args.foundation_root), "--foundation-python", str(args.foundation_python),
                "--official-cli", "--shadow", "--out", str(candidate_foundation_out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        candidate_foundation_run = None
    try:
        candidate_policy_data = json.loads(candidate_policy_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        candidate_policy_data = {}
    report["artifacts"].update({
        "safe_repair": str(repair_report),
        "candidate_policy": str(candidate_policy_report),
        "candidate_foundation": str(candidate_foundation_out / "foundation_validation.json"),
    })
    report["safe_repair"] = {
        "status": repair_data.get("status"),
        "applied_count": len(repair_data.get("applied", [])) if isinstance(repair_data.get("applied", []), list) else 0,
        "candidate": repair_data.get("candidate"),
        "candidate_remaining_focus_findings": [
            item.get("requirement_id") for item in candidate_policy_data.get("findings", [])
            if isinstance(item, dict) and item.get("requirement_id") in FOCUS_REQUIREMENTS
        ],
        "candidate_official_profile_returncode": candidate_foundation_run.returncode if candidate_foundation_run else None,
    }
    report["executions"].update({
        "safe_repair_returncode": repair_run.returncode,
        "candidate_policy_returncode": candidate_policy_run.returncode if candidate_policy_run else None,
        "candidate_foundation_returncode": candidate_foundation_run.returncode if candidate_foundation_run else None,
    })
    if not upstream_ran:
        report["reason"] = "Foundation profile did not register and execute."
    elif not policy_data:
        report["reason"] = "Focused structural policy did not produce a report."
    elif repair_data.get("status") != "applied_safe":
        report["reason"] = "Safe RB.COL.002 repair candidate was not created."
    else:
        report["status"] = "passed" if not report["findings"] else "failed"
    workflow_path = out / "workflow.json"
    write_json(workflow_path, report)
    html_path = out / "articulated_physics_structure_report.html"
    html_run = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "build_articulated_physics_html_report.py"), str(workflow_path), str(policy_report), "--out", str(html_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    report["artifacts"]["html_report"] = str(html_path)
    report["executions"]["html_report_returncode"] = html_run.returncode
    if html_run.returncode != 0:
        report["status"] = "blocked"
        report["reason"] = "HTML report generation failed."
    write_json(workflow_path, report)
    print(workflow_path)
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
