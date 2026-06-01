"""Job status classification rules for service reports."""

from __future__ import annotations

from typing import Any


PHYSICS_IMPACTING_VALIDATION_RULES = {
    "ExtentsChecker",
    "ManifoldChecker",
    "MissingReferenceChecker",
    "NormalsValidChecker",
    "StageMetadataChecker",
    "ValidateTopologyChecker",
    "ZeroAreaFaceChecker",
}
PHYSICS_BLOCKING_SEVERITIES = {"ERROR", "FAILURE"}


def classify_summary(summary: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    result = summary.get("result")
    contact_report_detected = checks.get("contact_report_detected") is True
    evidence_level = summary.get("contact_evidence_level")
    strong_contact_evidence = contact_report_detected and evidence_level == "detected"
    adapted = {
        "summary_result": result,
        "contact_report_detected": contact_report_detected,
        "contact_evidence_level": evidence_level,
        "strong_contact_evidence": strong_contact_evidence,
    }
    if result == "blocked":
        return "blocked", adapted, summary.get("error") if isinstance(summary.get("error"), str) else None
    if result == "passed" and strong_contact_evidence:
        return "passed", adapted, None
    return "failed", adapted, None


def classify_validation_summary(summary: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    validation_status = summary.get("validation_status") or summary.get("status")
    execution_status = summary.get("execution_status")
    issue_summary = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    error_payload = summary.get("error") if isinstance(summary.get("error"), dict) else {}
    issues = summary.get("issues") if isinstance(summary.get("issues"), list) else []
    physics_blocking_issues = [
        issue
        for issue in issues
        if isinstance(issue, dict)
        and issue.get("rule") in PHYSICS_IMPACTING_VALIDATION_RULES
        and issue.get("severity") in PHYSICS_BLOCKING_SEVERITIES
    ]
    adapted = {
        "validation_status": validation_status,
        "execution_status": execution_status,
        "issue_count": issue_summary.get("issue_count"),
        "severity_counts": issue_summary.get("severity_counts") or {},
        "rule_counts": issue_summary.get("rule_counts") or {},
        "physics_blocking_issue_count": len(physics_blocking_issues),
        "physics_blocking_rules": sorted(
            {str(issue.get("rule")) for issue in physics_blocking_issues if issue.get("rule")}
        ),
    }
    if execution_status == "error" or validation_status == "blocked":
        return "blocked", adapted, error_payload.get("message") if error_payload else None
    if physics_blocking_issues:
        return "failed", adapted, "Mesh validation found issues that can affect physics collision."
    if validation_status in {"passed", "warning", "failed"}:
        return "passed", adapted, None
    return "failed", adapted, None

