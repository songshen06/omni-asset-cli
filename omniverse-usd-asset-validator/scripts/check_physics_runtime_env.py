#!/usr/bin/env python3
"""Report whether the current environment can run the runtime physics harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from runtime_physics_harness import (
    RuntimeConfig,
    _host_platform,
    _infer_runtime_platform,
    default_windows_runtime_python_wsl,
    discover_runtime_python,
    is_wsl,
    normalize_runtime_python_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check runtime physics environment readiness for Isaac Sim.",
    )
    parser.add_argument(
        "--runtime-python",
        help="Optional Isaac Sim launcher path. In WSL, Windows paths like C:\\isaacsim\\python.bat are accepted.",
    )
    parser.add_argument(
        "--runtime-platform",
        choices=["auto", "linux", "windows"],
        default="auto",
        help="Target runtime platform when using an external Isaac Sim python",
    )
    return parser.parse_args()


def _load_simulation_app_in_current_interpreter() -> tuple[bool, str | None]:
    try:
        from isaacsim import SimulationApp  # type: ignore  # noqa: F401

        return True, "isaacsim.SimulationApp"
    except ImportError:
        pass

    try:
        from omni.isaac.kit import SimulationApp  # type: ignore  # noqa: F401

        return True, "omni.isaac.kit.SimulationApp"
    except ImportError:
        return False, None


def _run_probe(runtime_python: str, target_platform: str) -> tuple[int | None, str | None]:
    probe = (
        "import json; "
        "payload={'python': __import__('sys').executable}; "
        "ok=False; name=None; "
        "try:\n import isaacsim; from isaacsim import SimulationApp; ok=True; name='isaacsim.SimulationApp'\n"
        "except ImportError:\n"
        "  try:\n   from omni.isaac.kit import SimulationApp; ok=True; name='omni.isaac.kit.SimulationApp'\n"
        "  except ImportError:\n   pass\n"
        "payload['simulation_app_available']=ok; payload['simulation_app_name']=name; "
        "print(json.dumps(payload, ensure_ascii=True))"
    )

    if target_platform == "windows":
        command = ["cmd.exe", "/C", runtime_python, "-c", probe]
    else:
        command = [runtime_python, "-c", probe]

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None, None

    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, output or None


def main() -> int:
    args = parse_args()
    normalized_runtime_python = normalize_runtime_python_path(args.runtime_python) if args.runtime_python else None
    config = RuntimeConfig(
        asset=Path("."),
        out_dir=Path("out") / "_physics_env_probe",
        runtime_python=normalized_runtime_python,
        runtime_platform=args.runtime_platform,
    )

    current_ok, current_name = _load_simulation_app_in_current_interpreter()
    discovered_runtime = discover_runtime_python(config)
    target_platform = _infer_runtime_platform(discovered_runtime, args.runtime_platform)

    payload = {
        "host_platform": _host_platform(),
        "is_wsl": is_wsl(),
        "current_interpreter": {
            "python": sys.executable,
            "simulation_app_available": current_ok,
            "simulation_app_name": current_name,
        },
        "requested_runtime_python": args.runtime_python,
        "normalized_runtime_python": normalized_runtime_python,
        "discovered_runtime_python": discovered_runtime,
        "runtime_platform": target_platform,
        "default_windows_runtime_python_wsl": default_windows_runtime_python_wsl(),
    }

    if discovered_runtime is None:
        payload["probe"] = {
            "ready": False,
            "reason": "No Isaac Sim runtime launcher was discovered.",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    probe_returncode, probe_output = _run_probe(discovered_runtime, target_platform)
    payload["probe"] = {
        "ready": probe_returncode == 0,
        "returncode": probe_returncode,
        "output": probe_output,
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if probe_returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
