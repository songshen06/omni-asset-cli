#!/usr/bin/env python3
"""Run the Stage 1 SimReady data-flywheel loop for a USD asset."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
INSPECTOR_ROOT = Path.home() / "usd-simready-inspector"
DEFAULT_REFERENCE = INSPECTOR_ROOT / "simready_furniture_reference_with_wikidata.json"


def _default_validator_python() -> str:
    candidate = REPO_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def _default_inspector_python(inspector_root: Path) -> str:
    candidate = inspector_root / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def _default_out_dir(asset: Path) -> Path:
    return Path("out") / f"{asset.stem}_simready_flywheel"


def _usd_suffix(output_format: str) -> str:
    return ".usdc" if output_format == "usdc" else ".usda"


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True)
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {"value": payload}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _physics_mass_entries(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not report:
        return []
    entries = ((report.get("physics") or {}).get("mass_api") or [])
    return [entry for entry in entries if isinstance(entry, dict)]


def _physics_supplement(recommendation: dict[str, Any] | None) -> dict[str, Any]:
    if not recommendation:
        return {}
    supplements = recommendation.get("supplements") or {}
    content_physics = supplements.get("content_agent_physics") or {}
    return content_physics if isinstance(content_physics, dict) else {}


def _mass_status(source_report: dict[str, Any] | None, fixed_report: dict[str, Any] | None, recommendation: dict[str, Any] | None) -> dict[str, Any]:
    fixed_mass = _physics_mass_entries(fixed_report)
    source_mass = _physics_mass_entries(source_report)
    supplement = _physics_supplement(recommendation)
    suggestion = supplement.get("physics_material_suggestion") or {}
    mass_assessment = supplement.get("mass_assessment") or {}
    authored_values = fixed_mass or source_mass
    usable_authored = [
        entry
        for entry in authored_values
        if entry.get("mass") not in (None, "") or entry.get("density") not in (None, "")
    ]

    if usable_authored:
        status = "authored"
        reason = "USD MassAPI has authored mass or density values."
    elif suggestion.get("mass_for_authoring_kg") is not None:
        status = "supplemental"
        reason = "Content physics supplement has a bounded mass_for_authoring_kg."
    elif suggestion.get("raw_estimated_mass_kg") is not None:
        status = "needs_review"
        reason = "Only raw supplemental mass exists; it was not accepted for authoring."
    else:
        status = "missing"
        reason = "No authored MassAPI mass/density or accepted supplemental mass was found."

    return {
        "status": status,
        "reason": reason,
        "authored_mass_api_count": len(authored_values),
        "authored_mass_api": authored_values[:20],
        "supplemental_mass": {
            "raw_estimated_mass_kg": suggestion.get("raw_estimated_mass_kg"),
            "mass_for_authoring_kg": suggestion.get("mass_for_authoring_kg"),
            "assessment_status": mass_assessment.get("status"),
            "rule_mass_range_kg": mass_assessment.get("rule_mass_range_kg"),
        },
    }


def _bbox_size(report: dict[str, Any] | None) -> Any:
    if not report:
        return None
    return (((report.get("geometry") or {}).get("bbox") or {}).get("world") or {}).get("size")


def _size_status(source_report: dict[str, Any] | None, fixed_report: dict[str, Any] | None, recommendation: dict[str, Any] | None) -> dict[str, Any]:
    rec = (recommendation or {}).get("recommendation") or {}
    size_recommendation = rec.get("size_recommendation") or {}
    authoring = rec.get("authoring") or {}
    expectations = (recommendation or {}).get("simready_expectations") or (fixed_report or {}).get("simready_expectations") or {}
    return {
        "status": size_recommendation.get("status") or "unknown",
        "source_bbox_size_cm": _bbox_size(source_report),
        "fixed_bbox_size_cm": _bbox_size(fixed_report),
        "reference_target_bbox_cm": size_recommendation.get("reference_target_bbox"),
        "expected_authored_bbox_size_cm": expectations.get("expected_authored_bbox_size_cm"),
        "apply_reference_scale": bool(authoring.get("apply_reference_scale")),
        "suggested_uniform_scale": authoring.get("suggested_uniform_scale"),
        "apply_orientation_correction": bool(authoring.get("apply_orientation_correction")),
        "orientation_correction": authoring.get("orientation_correction"),
    }


def _validator_defects(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"status": "not_run", "issue_count": None, "top_issues": []}
    issues = payload.get("issues") or []
    top_issues = []
    for issue in issues[:10]:
        if not isinstance(issue, dict):
            continue
        top_issues.append(
            {
                "rule": issue.get("rule"),
                "severity": issue.get("severity"),
                "message": issue.get("message"),
                "at": issue.get("at") or issue.get("path"),
            }
        )
    return {
        "status": payload.get("status") or payload.get("validation_status"),
        "issue_count": ((payload.get("summary") or {}).get("issue_count")),
        "severity_counts": ((payload.get("summary") or {}).get("severity_counts")),
        "rule_counts": ((payload.get("summary") or {}).get("rule_counts")),
        "top_issues": top_issues,
    }


def _runtime_flywheel_feedback(
    runtime_summary: dict[str, Any] | None,
    runtime_report: dict[str, Any] | None,
    runtime_step: dict[str, Any] | None,
) -> dict[str, Any]:
    if runtime_summary is None and runtime_report is None:
        reason = (runtime_step or {}).get("stderr") or "runtime artifacts were not produced"
        return {
            "status": "blocked",
            "failure_class": "environment_or_runtime_dispatch",
            "reason": reason,
            "upstream_actions": [
                "Run on a Linux host with NVIDIA Container Toolkit and Isaac Sim Docker.",
                "Pass --runtime-docker-image or --runtime-docker-container to the flywheel command.",
                "Do not substitute host Python or non-container runtimes for authoritative runtime validation.",
            ],
        }

    result = (runtime_summary or {}).get("result") or (runtime_report or {}).get("result")
    checks = (runtime_summary or {}).get("checks") or {}
    hit_analysis = (runtime_report or {}).get("hit_analysis") or {}
    contact_report = (((runtime_report or {}).get("final_state") or {}).get("contact_report") or {})
    if result == "passed" and checks.get("contact_report_detected"):
        return {
            "status": "passed",
            "failure_class": None,
            "reason": "Docker runtime completed with PhysX contact evidence.",
            "upstream_actions": [],
        }

    if result in {"blocked", "error"}:
        failure_class = "environment_or_runtime_dispatch"
        actions = [
            "Fix Docker image/container availability before changing asset authoring.",
            "Verify physics-env succeeds against the same Docker image or container.",
        ]
    elif not checks.get("asset_loaded"):
        failure_class = "authoring_or_reference"
        actions = [
            "Repair the exported USD package so references and payloads resolve inside the Docker mount.",
            "Keep generated assets under mounted repository/home paths consumed by the runtime container.",
        ]
    elif not checks.get("static_colliders_applied"):
        failure_class = "collider_authoring"
        actions = [
            "Improve usd-simready-inspector collider generation for the selected mesh subtree.",
            "Review recommended_collider, target_mesh_paths, and collision approximation policy.",
        ]
    elif not checks.get("hit_targeted"):
        failure_class = "placement_or_bbox"
        actions = [
            "Feed runtime asset_bbox_min/max back into recommendation authoring.",
            "Adjust bbox normalization, orientation correction, or template placement.",
        ]
    elif not checks.get("simulation_advanced") or hit_analysis.get("box_descended") is not True:
        failure_class = "runtime_motion"
        actions = [
            "Review gravity, metersPerUnit, drop actor size, and initial drop position.",
            "Compare runtime_report box_size and asset bbox with simready_expectations.",
        ]
    elif not checks.get("contact_report_detected"):
        failure_class = "contact_evidence"
        actions = [
            "Treat inferred contact as insufficient for promotion.",
            "Improve collider authoring or contact-report instrumentation until PhysX contact_report_detected is true.",
            "Use contact_report target_kind counts to distinguish asset_subtree from guide_bbox or other contacts.",
        ]
    else:
        failure_class = "runtime_quality"
        actions = [
            "Review summary.json, runtime_report.json, and timeline.csv as a downstream failure record.",
            "Patch the upstream recommendation or repair step, then rerun the same Docker command.",
        ]

    return {
        "status": "failed" if result == "passed" else result or "failed",
        "failure_class": failure_class,
        "reason": "Downstream Docker runtime validation did not produce strong contact evidence.",
        "observed": {
            "result": result,
            "checks": checks,
            "contact_evidence_level": (runtime_summary or {}).get("contact_evidence_level")
            or hit_analysis.get("contact_evidence_level"),
            "contact_report": {
                "event_count": contact_report.get("event_count"),
                "target_event_count": contact_report.get("target_event_count"),
                "asset_subtree_event_count": contact_report.get("asset_subtree_event_count"),
                "guide_bbox_event_count": contact_report.get("guide_bbox_event_count"),
                "errors": contact_report.get("errors"),
            },
        },
        "upstream_actions": actions,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run validator defects, usd-simready-inspector repair, and optional Isaac Sim "
            "headless top-drop retest as a Stage 1 data-flywheel loop."
        ),
    )
    parser.add_argument("asset", type=Path, help="Source USD/USDZ/USDA/USDC asset")
    parser.add_argument("--out", type=Path, help="Output directory for flywheel artifacts")
    parser.add_argument("--inspector-root", type=Path, default=INSPECTOR_ROOT)
    parser.add_argument("--reference-json", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--inspector-python", help="Python executable for usd-simready-inspector")
    parser.add_argument("--validator-python", help="Python executable for omni-asset-cli validator scripts")
    parser.add_argument("--output-format", choices=["usda", "usdc"], default="usdc")
    parser.add_argument("--max-prims", type=int, default=0)
    parser.add_argument("--skip-validator", action="store_true")
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--template-scene", type=Path, default=REPO_ROOT / "examples" / "mini_test.usda")
    parser.add_argument("--frames", type=int, default=240)
    parser.add_argument("--fps", type=float, default=60.0)
    parser.add_argument("--runtime-docker-image")
    parser.add_argument("--runtime-docker-container")
    parser.add_argument("--docker-workspace", default="/workspace/omni-asset-cli")
    parser.add_argument("--docker-python", default="/isaac-sim/python.sh")
    parser.add_argument("--render-frames", action="store_true")
    parser.add_argument("--render-every-n-frames", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asset = args.asset.resolve()
    out_dir = (args.out or _default_out_dir(asset)).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    inspector_root = args.inspector_root.resolve()
    reference_json = args.reference_json.resolve()
    inspector_python = args.inspector_python or _default_inspector_python(inspector_root)
    validator_python = args.validator_python or _default_validator_python()

    fixed_usd = out_dir / f"{asset.stem}.simready_static{_usd_suffix(args.output_format)}"
    source_report = out_dir / "source.inspect.report.json"
    recommendation = out_dir / "simready.recommendation.json"
    fixed_report = out_dir / "simready.inspect.report.json"
    source_validator_json = out_dir / "source.omni_validator.json"
    fixed_validator_json = out_dir / "fixed.omni_validator.json"
    fixed_validator_md = out_dir / "fixed.omni_validator.md"
    runtime_dir = out_dir / "runtime_top_drop"
    diagnosis_json = out_dir / "simready.diagnosis.json"
    flywheel_json = out_dir / "flywheel_report.json"

    if not asset.exists():
        print(f"Asset not found: {asset}", file=sys.stderr)
        return 2
    if not inspector_root.exists():
        print(f"Inspector root not found: {inspector_root}", file=sys.stderr)
        return 2
    if not reference_json.exists():
        print(f"Reference JSON not found: {reference_json}", file=sys.stderr)
        return 2

    steps: dict[str, Any] = {}

    inspect_source_cmd = [
        inspector_python,
        "usd_simready_cli.py",
        "inspect",
        str(asset),
        "--output",
        str(source_report),
        "--pretty",
        "--max-prims",
        str(args.max_prims),
    ]
    steps["source_inspect"] = _run(inspect_source_cmd, inspector_root)

    if not args.skip_validator:
        validate_source_cmd = [
            validator_python,
            str(REPO_ROOT / "omniverse-usd-asset-validator" / "scripts" / "run_sync_validation.py"),
            str(asset),
            "--output-json",
            str(source_validator_json),
            "--profile",
            "stage1-furniture",
        ]
        steps["source_validator"] = _run(validate_source_cmd, REPO_ROOT)

    process_cmd = [
        inspector_python,
        "usd_simready_cli.py",
        "process",
        str(reference_json),
        str(asset),
        "--output",
        str(fixed_usd),
        "--output-format",
        args.output_format,
        "--recommendation-output",
        str(recommendation),
        "--report-output",
        str(fixed_report),
        "--emit-report",
        "--max-prims",
        str(args.max_prims),
    ]
    steps["simready_process"] = _run(process_cmd, inspector_root)

    if fixed_usd.exists() and not args.skip_validator:
        validate_fixed_cmd = [
            validator_python,
            str(REPO_ROOT / "omniverse-usd-asset-validator" / "scripts" / "run_sync_validation.py"),
            str(fixed_usd),
            "--output-json",
            str(fixed_validator_json),
            "--output-md",
            str(fixed_validator_md),
            "--profile",
            "stage1-furniture",
        ]
        steps["fixed_validator"] = _run(validate_fixed_cmd, REPO_ROOT)

    runtime_report = runtime_dir / "runtime_report.json"
    runtime_summary = runtime_dir / "summary.json"
    if fixed_usd.exists() and not args.skip_runtime:
        if not (args.runtime_docker_image or args.runtime_docker_container):
            steps["runtime_top_drop"] = {
                "command": None,
                "cwd": str(REPO_ROOT),
                "returncode": 2,
                "stdout": "",
                "stderr": (
                    "Runtime validation requires Linux with Isaac Sim Docker. "
                    "Pass --runtime-docker-image or --runtime-docker-container."
                ),
            }
        else:
            runtime_cmd = [
                validator_python,
                str(REPO_ROOT / "omniverse-usd-asset-validator" / "scripts" / "run_physics_hit_test.py"),
                str(fixed_usd),
                "--template-scene",
                str(args.template_scene),
                "--hit-mode",
                "top-drop",
                "--size-policy",
                "preserve",
                "--frames",
                str(args.frames),
                "--fps",
                str(args.fps),
                "--out",
                str(runtime_dir),
            ]
            if args.runtime_docker_image:
                runtime_cmd.extend(["--runtime-docker-image", args.runtime_docker_image])
            if args.runtime_docker_container:
                runtime_cmd.extend(["--runtime-docker-container", args.runtime_docker_container])
            if args.docker_workspace:
                runtime_cmd.extend(["--docker-workspace", args.docker_workspace])
            if args.docker_python:
                runtime_cmd.extend(["--docker-python", args.docker_python])
            if args.render_frames:
                runtime_cmd.append("--render-frames")
                runtime_cmd.extend(["--render-every-n-frames", str(args.render_every_n_frames)])
            steps["runtime_top_drop"] = _run(runtime_cmd, REPO_ROOT)

    if recommendation.exists() and fixed_report.exists():
        diagnose_cmd = [
            inspector_python,
            "usd_simready_cli.py",
            "diagnose",
            "--recommendation",
            str(recommendation),
            "--report",
            str(fixed_report),
            "--output",
            str(diagnosis_json),
        ]
        if runtime_report.exists():
            diagnose_cmd.extend(["--runtime-report", str(runtime_report)])
        steps["diagnose"] = _run(diagnose_cmd, inspector_root)

    source_report_payload = _load_json(source_report)
    fixed_report_payload = _load_json(fixed_report)
    recommendation_payload = _load_json(recommendation)
    diagnosis_payload = _load_json(diagnosis_json)
    runtime_payload = _load_json(runtime_report)
    runtime_summary_payload = _load_json(runtime_summary)
    source_validator_payload = _load_json(source_validator_json)
    fixed_validator_payload = _load_json(fixed_validator_json)
    runtime_feedback = _runtime_flywheel_feedback(
        runtime_summary_payload,
        runtime_payload,
        steps.get("runtime_top_drop"),
    )

    report = {
        "schema_version": 1,
        "status": "completed",
        "asset": str(asset),
        "out_dir": str(out_dir),
        "environment": {
            "validator_python": validator_python,
            "inspector_root": str(inspector_root),
            "inspector_python": inspector_python,
            "reference_json": str(reference_json),
        },
        "artifacts": {
            "source_report": str(source_report),
            "source_validator_json": str(source_validator_json) if source_validator_json.exists() else None,
            "fixed_usd": str(fixed_usd) if fixed_usd.exists() else None,
            "recommendation": str(recommendation) if recommendation.exists() else None,
            "fixed_report": str(fixed_report) if fixed_report.exists() else None,
            "fixed_validator_json": str(fixed_validator_json) if fixed_validator_json.exists() else None,
            "fixed_validator_md": str(fixed_validator_md) if fixed_validator_md.exists() else None,
            "runtime_report": str(runtime_report) if runtime_report.exists() else None,
            "runtime_summary": str(runtime_summary) if runtime_summary.exists() else None,
            "diagnosis": str(diagnosis_json) if diagnosis_json.exists() else None,
        },
        "priority_checks": {
            "size": _size_status(source_report_payload, fixed_report_payload, recommendation_payload),
            "weight": _mass_status(source_report_payload, fixed_report_payload, recommendation_payload),
        },
        "defects": {
            "source_validator": _validator_defects(source_validator_payload),
            "fixed_validator": _validator_defects(fixed_validator_payload),
            "source_inspector_issues": (source_report_payload or {}).get("issues"),
            "fixed_inspector_issues": (fixed_report_payload or {}).get("issues"),
        },
        "runtime": {
            "status": (
                (runtime_summary_payload or {}).get("result")
                or (runtime_payload or {}).get("result")
                or ("not_run" if not runtime_payload else None)
            ),
            "checks": (runtime_summary_payload or {}).get("checks") or (runtime_payload or {}).get("checks"),
            "hit_analysis": (runtime_payload or {}).get("hit_analysis") if runtime_payload else None,
            "contact_evidence_level": (runtime_summary_payload or {}).get("contact_evidence_level")
            or ((runtime_payload or {}).get("hit_analysis") or {}).get("contact_evidence_level"),
        },
        "data_flywheel": {
            "downstream_runtime_feedback": runtime_feedback,
            "principle": (
                "Downstream Docker runtime failures are feedback for upstream asset preparation, "
                "collider authoring, placement, scale/orientation normalization, and contact instrumentation."
            ),
        },
        "diagnosis": diagnosis_payload,
        "steps": steps,
    }

    failed_steps = [name for name, step in steps.items() if step.get("returncode") not in (0, None)]
    if failed_steps:
        report["status"] = "warning"
        report["failed_steps"] = failed_steps

    _write_json(flywheel_json, report)
    print(flywheel_json)
    return 0 if not failed_steps else 1


if __name__ == "__main__":
    raise SystemExit(main())
