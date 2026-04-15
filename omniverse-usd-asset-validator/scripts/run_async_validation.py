#!/usr/bin/env python3
"""Run omniverse asset validation with polling and human-readable summaries."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


def build_command(args: argparse.Namespace, output_path: Path) -> list[str]:
    command = ["omni_asset_validate"]
    command.extend(["--json-output", str(output_path)])

    if args.no_variants:
        command.append("--no-variants")
    if args.no_init_rules:
        command.append("--no-init-rules")
    if args.fix:
        command.append("--fix")
    if args.predicate:
        command.extend(["--predicate", args.predicate])
    for rule in args.rule:
        command.extend(["--rule", rule])
    for category in args.category:
        command.extend(["--category", category])
    for extra_arg in args.extra_arg:
        command.append(extra_arg)

    command.append(str(args.asset))
    return command


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def walk_findings(node: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if any(key in node for key in ("message", "severity", "rule", "rule_name", "result")):
            findings.append(node)
        for value in node.values():
            findings.extend(walk_findings(value))
    elif isinstance(node, list):
        for item in node:
            findings.extend(walk_findings(item))
    return findings


def summarize_json(payload: Any) -> dict[str, Any]:
    findings = walk_findings(payload)
    severity_counter: Counter[str] = Counter()
    rule_counter: Counter[str] = Counter()
    messages: list[str] = []

    for finding in findings:
        severity = (
            finding.get("severity")
            or finding.get("result")
            or finding.get("level")
            or "unknown"
        )
        severity_counter[str(severity)] += 1

        rule_name = finding.get("rule") or finding.get("rule_name") or finding.get("checker")
        if rule_name:
            rule_counter[str(rule_name)] += 1

        message = finding.get("message") or finding.get("issue") or finding.get("description")
        if message and message not in messages:
            messages.append(str(message))

    return {
        "finding_count": len(findings),
        "severity_counter": dict(severity_counter),
        "rule_counter": dict(rule_counter),
        "sample_messages": messages[:5],
    }


def print_human_summary(
    *,
    status: str,
    asset: Path,
    command: list[str],
    output_path: Path,
    elapsed_seconds: float,
    process_returncode: int | None,
    summary: dict[str, Any] | None,
    stderr_tail: str | None,
) -> None:
    print(f"Status: {status}")
    print(f"Target: {asset}")
    print(f"Command: {' '.join(command)}")
    print(f"ElapsedSeconds: {elapsed_seconds:.1f}")
    print(f"JSONOutput: {output_path}")

    if process_returncode is not None:
        print(f"ReturnCode: {process_returncode}")

    if summary:
        print(f"Findings: {summary['finding_count']}")
        print(f"SeverityCounts: {json.dumps(summary['severity_counter'], ensure_ascii=True)}")
        if summary["rule_counter"]:
            print(f"RuleCounts: {json.dumps(summary['rule_counter'], ensure_ascii=True)}")
        if summary["sample_messages"]:
            print("Summary:")
            for message in summary["sample_messages"]:
                print(f"- {message}")
    elif stderr_tail:
        print("Summary:")
        print(f"- {stderr_tail}")
    elif status == "timed_out":
        print("Summary:")
        print("- Validation started but did not finish within the allowed timeout.")
    elif status == "completed":
        print("Summary:")
        print("- Validation finished but no findings were parsed from the JSON output.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run omniverse asset validation with polling and readable summaries.",
    )
    parser.add_argument("asset", type=Path, help="Path to the USD asset or folder to validate")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("/tmp/omniverse_asset_validation.json"),
        help="Path to the JSON output file",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Maximum number of seconds to wait for validation",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help="Polling interval while waiting for validation",
    )
    parser.add_argument("--rule", action="append", default=[], help="Specific rule to enable")
    parser.add_argument("--category", action="append", default=[], help="Specific category to enable")
    parser.add_argument("--predicate", help="Optional predicate filter")
    parser.add_argument("--fix", action="store_true", help="Enable automatic fixes")
    parser.add_argument("--no-variants", action="store_true", help="Disable variant expansion")
    parser.add_argument("--no-init-rules", action="store_true", help="Disable default rule initialization")
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Additional raw argument to pass through to omni_asset_validate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output_json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    command = build_command(args, output_path)
    start = time.monotonic()

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print_human_summary(
            status="blocked",
            asset=args.asset,
            command=command,
            output_path=output_path,
            elapsed_seconds=0.0,
            process_returncode=127,
            summary=None,
            stderr_tail="omni_asset_validate was not found on PATH.",
        )
        return 127

    status = "timed_out"
    summary: dict[str, Any] | None = None
    stderr_tail = ""

    while True:
        elapsed = time.monotonic() - start
        returncode = process.poll()

        if output_path.exists() and returncode is not None:
            payload = load_json(output_path)
            summary = summarize_json(payload)
            status = "completed"
            break

        if returncode is not None:
            status = "completed" if output_path.exists() else "blocked"
            break

        if elapsed >= args.timeout_seconds:
            process.kill()
            process.wait()
            status = "timed_out"
            break

        time.sleep(args.poll_seconds)

    stdout_text, stderr_text = process.communicate()
    combined = "\n".join(part for part in [stdout_text.strip(), stderr_text.strip()] if part).strip()
    if combined:
        stderr_tail = combined.splitlines()[-1]

    if output_path.exists() and summary is None:
        try:
            summary = summarize_json(load_json(output_path))
            status = "completed"
        except json.JSONDecodeError:
            if status != "timed_out":
                status = "blocked"
            stderr_tail = "JSON output exists but could not be parsed."

    print_human_summary(
        status=status,
        asset=args.asset,
        command=command,
        output_path=output_path,
        elapsed_seconds=time.monotonic() - start,
        process_returncode=process.returncode,
        summary=summary,
        stderr_tail=stderr_tail or None,
    )

    if status == "completed":
        return 0
    if status == "timed_out":
        return 124
    return process.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
