#!/usr/bin/env python3
"""Report whether the current environment can run the runtime physics harness."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from dataclasses import dataclass


@dataclass
class ProbeConfig:
    runtime_python: str | None = None
    runtime_platform: str = "auto"
    runtime_docker_image: str | None = None
    runtime_docker_container: str | None = None
    docker_workspace: str = "/workspace/omni-asset-cli"
    docker_python: str = "/isaac-sim/python.sh"


def _host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    return "linux"


def is_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))


def _is_windows_runtime_path(path_value: str) -> bool:
    lower = path_value.lower()
    return lower.endswith(".bat") or lower.endswith(".exe") or ":\\" in path_value or ":/" in path_value


def normalize_runtime_python_path(raw_path: str) -> str:
    if _host_platform() == "linux" and _is_windows_runtime_path(raw_path):
        windows_style = raw_path.replace("/", "\\")
        drive, _, tail = windows_style.partition(":\\")
        if drive and tail:
            return f"/mnt/{drive.lower()}/{tail.replace(chr(92), '/')}"
    return raw_path


def default_windows_runtime_python_wsl() -> str | None:
    if not is_wsl():
        return None

    for candidate in (
        Path("/mnt/c/isaacsim/python.bat"),
        Path("/mnt/c/isaacsim/python.exe"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _infer_runtime_platform(runtime_python: str | None, requested_platform: str) -> str:
    if requested_platform in {"linux", "windows"}:
        return requested_platform
    if runtime_python and _is_windows_runtime_path(runtime_python):
        return "windows"
    return _host_platform()


def _candidate_runtime_paths() -> list[str]:
    candidates: list[str] = []

    for env_name in ("OMNI_ASSET_CLI_RUNTIME_PYTHON", "ISAACSIM_PYTHON", "ISAACSIM_PYTHON_EXE"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(value)

    home = Path.home()
    for path in sorted(home.glob(".local/share/ov/pkg/isaac-sim-*/python.sh"), reverse=True):
        candidates.append(str(path))
    for path in sorted(home.glob("isaacsim/python.sh"), reverse=True):
        candidates.append(str(path))

    wsl_windows_runtime = default_windows_runtime_python_wsl()
    if wsl_windows_runtime:
        candidates.append(wsl_windows_runtime)

    deduped: list[str] = []
    for value in candidates:
        if value not in deduped:
            deduped.append(value)
    return deduped


def discover_runtime_python(config: ProbeConfig) -> str | None:
    if config.runtime_python:
        candidate = normalize_runtime_python_path(config.runtime_python)
        if Path(candidate).exists():
            return candidate
        return config.runtime_python

    for candidate in _candidate_runtime_paths():
        if Path(candidate).exists():
            return candidate
    return None


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
    parser.add_argument(
        "--runtime-docker-image",
        help="Optional Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID to exec into",
    )
    parser.add_argument(
        "--docker-workspace",
        default="/workspace/omni-asset-cli",
        help="Repository mount path inside the Isaac Sim container",
    )
    parser.add_argument(
        "--docker-python",
        default="/isaac-sim/python.sh",
        help="Isaac Sim Python launcher path inside the container",
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
    probe = """import json
import sys

payload = {"python": sys.executable}
ok = False
name = None
try:
    from isaacsim import SimulationApp
    ok = True
    name = "isaacsim.SimulationApp"
except ImportError:
    try:
        from omni.isaac.kit import SimulationApp
        ok = True
        name = "omni.isaac.kit.SimulationApp"
    except ImportError:
        pass
payload["simulation_app_available"] = ok
payload["simulation_app_name"] = name
print(json.dumps(payload, ensure_ascii=True))
"""

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


def _run_docker_probe(config: ProbeConfig) -> tuple[int | None, str | None, list[str] | None]:
    probe = """import json
import sys

ok = False
name = None
try:
    from isaacsim import SimulationApp
    ok = True
    name = "isaacsim.SimulationApp"
except ImportError:
    try:
        from omni.isaac.kit import SimulationApp
        ok = True
        name = "omni.isaac.kit.SimulationApp"
    except ImportError:
        pass
print(json.dumps({"python": sys.executable, "simulation_app_available": ok, "simulation_app_name": name}))
"""

    try:
        if config.runtime_docker_container:
            command = [
                "docker",
                "exec",
                "-w",
                config.docker_workspace,
                config.runtime_docker_container,
                config.docker_python,
                "-c",
                probe,
            ]
        else:
            command = [
                "docker",
                "run",
                "--rm",
                "--gpus",
                "all",
                "--network",
                "host",
                "--ipc",
                "host",
                "-e",
                "ACCEPT_EULA=Y",
                "-e",
                "PRIVACY_CONSENT=Y",
                "-v",
                f"{Path(__file__).resolve().parents[2]}:{config.docker_workspace}",
                "-w",
                config.docker_workspace,
                "--entrypoint",
                config.docker_python,
                config.runtime_docker_image,
                "-c",
                probe,
            ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return None, None, None

    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, output or None, command


def main() -> int:
    args = parse_args()
    normalized_runtime_python = normalize_runtime_python_path(args.runtime_python) if args.runtime_python else None
    config = ProbeConfig(
        runtime_python=normalized_runtime_python,
        runtime_platform=args.runtime_platform,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
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
        "requested_runtime_docker_image": args.runtime_docker_image,
        "requested_runtime_docker_container": args.runtime_docker_container,
        "docker_workspace": args.docker_workspace,
        "docker_python": args.docker_python,
    }

    if args.runtime_docker_image or args.runtime_docker_container:
        probe_returncode, probe_output, probe_command = _run_docker_probe(config)
        payload["probe"] = {
            "ready": probe_returncode == 0,
            "returncode": probe_returncode,
            "output": probe_output,
            "command": probe_command,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if probe_returncode == 0 else 2

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
