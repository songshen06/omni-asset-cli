#!/usr/bin/env python3
"""Run a pinned SimReady Foundation validation command and normalize its findings."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from foundation_common import PACKAGE_PROFILES, default_out, sha256_file, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--package", choices=sorted(PACKAGE_PROFILES), required=True)
    parser.add_argument("--foundation-tag", required=True, help="Released Foundation tag approved for this run")
    parser.add_argument("--foundation-root", type=Path, help="Checkout pinned to --foundation-tag")
    parser.add_argument("--foundation-python", default=sys.executable)
    parser.add_argument(
        "--official-cli",
        action="store_true",
        help=("Run the pinned simready-validate executable with the official Foundation "
              "capabilities, features, and profiles paths."),
    )
    parser.add_argument(
        "--foundation-command",
        help=("Foundation command template. {asset}, {profile}, {out}, {tag}, and {python} are expanded; "
              "the command must write a JSON object to {out} or stdout."),
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--shadow", action="store_true", help="Record results without changing customer pass/fail state")
    return parser.parse_args()


def git_value(root: Path | None, *args: str) -> str | None:
    if root is None or not root.exists():
        return None
    completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def normalize_findings(raw: Any) -> list[dict[str, Any]]:
    """Normalize either one Foundation result object or its JSON result list."""
    if isinstance(raw, list):
        candidates: Any = raw
    elif isinstance(raw, dict) and all(isinstance(value, dict) for value in raw.values()):
        # simready-validate writes {asset_path: {features_summary: ...}}.
        candidates = []
        for asset_result in raw.values():
            for feature_id, feature in asset_result.get("features_summary", {}).items():
                if isinstance(feature, dict) and not feature.get("passed", False):
                    candidates.append({
                        "feature_id": feature_id,
                        "requirement_id": feature.get("failing requirements"),
                        "severity": "error",
                        "message": "Official Foundation feature validation failed.",
                    })
    else:
        candidates = raw.get("findings", raw.get("issues", [])) if isinstance(raw, dict) else []
    if not isinstance(candidates, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", item.get("level", "error"))).lower()
        normalized.append({
            "requirement_id": item.get("requirement_id") or item.get("requirement") or item.get("rule"),
            "feature_id": item.get("feature_id") or item.get("feature"),
            "severity": severity,
            "prim_path": item.get("prim_path") or item.get("path") or item.get("prim"),
            "message": item.get("message") or item.get("description") or "Foundation finding",
            "repairability": item.get("repairability", "manual"),
        })
    return normalized


def main() -> int:
    args = parse_args()
    asset = args.asset.resolve()
    out_dir = (args.out or default_out(asset, "foundation_validation")).resolve()
    output = out_dir / "foundation_validation.json"
    profile = PACKAGE_PROFILES[args.package]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "blocked",
        "shadow": args.shadow,
        "asset": {"path": str(asset), "sha256": sha256_file(asset) if asset.is_file() else None},
        "foundation": {
            "tag": args.foundation_tag,
            "commit": git_value(args.foundation_root, "rev-list", "-n", "1", args.foundation_tag),
            "profile": profile,
            "features": [],
            "root": str(args.foundation_root.resolve()) if args.foundation_root else None,
        },
        "findings": [],
        "execution": {"command": None, "returncode": None, "stdout": "", "stderr": ""},
    }
    if not asset.is_file():
        payload["reason"] = "Input asset does not exist."
        write_json(output, payload)
        return 2
    if args.foundation_root and payload["foundation"]["commit"] is None:
        payload["reason"] = "Foundation checkout does not contain the requested release tag."
        write_json(output, payload)
        return 2
    if args.official_cli and not args.foundation_root:
        payload["reason"] = "--official-cli requires --foundation-root."
        write_json(output, payload)
        return 2
    if not args.foundation_command and not args.official_cli:
        payload["reason"] = "No Foundation executor configured; provide --foundation-command to run shadow validation."
        write_json(output, payload)
        return 2

    raw_path = out_dir / "foundation_raw.json"
    values = {"asset": str(asset), "profile": profile, "out": str(raw_path), "tag": args.foundation_tag, "python": args.foundation_python}
    # Do not use str.format here: Foundation commands commonly contain JSON literals
    # whose braces must pass through unchanged.
    def expand(part: str) -> str:
        for key, value in values.items():
            part = part.replace("{" + key + "}", value)
        return part

    if args.official_cli:
        foundation_root = args.foundation_root.resolve()
        command = [
            str(Path(args.foundation_python).with_name("simready-validate")),
            "--rules-path", str(foundation_root / "nv_core/sr_specs/docs/capabilities"),
            "--features-path", str(foundation_root / "nv_core/sr_specs/docs/features"),
            "--profiles-path", str(foundation_root / "nv_core/sr_specs/docs/profiles/profiles.toml"),
            "--profile", profile,
            "--version", "1.0.0",
            "--output", str(raw_path),
            str(asset),
        ]
    else:
        command = [expand(part) for part in shlex.split(args.foundation_command)]
    completed = subprocess.run(command, cwd=str(args.foundation_root) if args.foundation_root else None, capture_output=True, text=True, check=False)
    payload["execution"] = {"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    raw: Any = None
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else json.loads(completed.stdout)
    except (OSError, json.JSONDecodeError):
        raw = None
    payload["findings"] = normalize_findings(raw)
    payload["status"] = "passed" if completed.returncode == 0 and raw is not None and not payload["findings"] else "failed"
    if completed.returncode != 0:
        payload["reason"] = "Foundation executor returned a non-zero status."
    elif raw is None:
        payload["reason"] = "Foundation executor did not produce parseable JSON output."
    write_json(output, payload)
    print(output)
    return 0 if payload["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
