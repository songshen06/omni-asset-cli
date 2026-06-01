"""Artifact naming and classification rules."""

from __future__ import annotations

from pathlib import Path


SUMMARY_FILENAME = "summary.json"
RUNTIME_REPORT_FILENAME = "runtime_report.json"


def artifact_kind(path: Path) -> str:
    if path.name == SUMMARY_FILENAME:
        return "summary"
    if path.name == RUNTIME_REPORT_FILENAME:
        return "runtime_report"
    if path.suffix.lower() == ".csv":
        return "timeline"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return "image"
    if path.suffix.lower() == ".json":
        return "json"
    return "artifact"

