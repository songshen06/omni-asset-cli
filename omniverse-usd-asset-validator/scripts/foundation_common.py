"""Shared contracts for SimReady Foundation integration commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PACKAGE_PROFILES = {
    "static-prop": "Prop-Robotics-Neutral",
    "physics-prop": "Prop-Robotics-Physx",
    "articulated-asset": "Prop-Robotics-Physx",
    "runnable-robot": "Robot-Body-Runnable",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def default_out(asset: Path, suffix: str) -> Path:
    return Path("out") / f"{asset.stem}_{suffix}"
