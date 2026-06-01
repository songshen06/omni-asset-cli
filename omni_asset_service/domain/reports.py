"""Report normalization for service job summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .status import classify_summary, classify_validation_summary


@dataclass(frozen=True)
class NormalizedReport:
    status: str
    result: dict[str, Any]
    error: str | None


def normalize_collision_summary(summary: dict[str, Any], *, returncode: int) -> NormalizedReport:
    status, result, error = classify_summary(summary)
    return _with_returncode(status, result, error, returncode)


def normalize_mesh_validation_summary(summary: dict[str, Any], *, returncode: int) -> NormalizedReport:
    status, result, error = classify_validation_summary(summary)
    return _with_returncode(status, result, error, returncode)


def normalize_job_summary(test_type: str, summary: dict[str, Any], *, returncode: int) -> NormalizedReport:
    if test_type == "collision":
        return normalize_collision_summary(summary, returncode=returncode)
    if test_type == "mesh":
        return normalize_mesh_validation_summary(summary, returncode=returncode)
    raise ValueError(f"Unsupported test_type: {test_type}")


def _with_returncode(
    status: str,
    result: dict[str, Any],
    error: str | None,
    returncode: int,
) -> NormalizedReport:
    normalized_result = dict(result)
    normalized_result["returncode"] = returncode
    return NormalizedReport(status=status, result=normalized_result, error=error)
