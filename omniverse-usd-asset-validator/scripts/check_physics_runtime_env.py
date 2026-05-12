#!/usr/bin/env python3
"""Report whether the current environment can run the runtime physics harness."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from dataclasses import dataclass


@dataclass
class ProbeConfig:
    runtime_docker_image: str | None = None
    runtime_docker_container: str | None = None
    docker_workspace: str = "/workspace/omni-asset-cli"
    docker_python: str = "/isaac-sim/python.sh"


def _host_platform() -> str:
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    return "linux"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Linux + Isaac Sim Docker readiness for runtime physics validation.",
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
    config = ProbeConfig(
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
    )

    current_ok, current_name = _load_simulation_app_in_current_interpreter()

    payload = {
        "host_platform": _host_platform(),
        "runtime_policy": "linux_docker_only",
        "current_interpreter": {
            "python": sys.executable,
            "simulation_app_available": current_ok,
            "simulation_app_name": current_name,
        },
        "requested_runtime_docker_image": args.runtime_docker_image,
        "requested_runtime_docker_container": args.runtime_docker_container,
        "docker_workspace": args.docker_workspace,
        "docker_python": args.docker_python,
    }

    if not (args.runtime_docker_image or args.runtime_docker_container):
        payload["probe"] = {
            "ready": False,
            "reason": "Runtime physics validation requires Linux with Isaac Sim Docker. Pass --runtime-docker-image or --runtime-docker-container.",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2
    if _host_platform() != "linux":
        payload["probe"] = {
            "ready": False,
            "reason": f"Runtime physics validation requires a Linux host with Isaac Sim Docker; host_platform={_host_platform()}.",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    probe_returncode, probe_output, probe_command = _run_docker_probe(config)
    payload["probe"] = {
        "ready": probe_returncode == 0,
        "returncode": probe_returncode,
        "output": probe_output,
        "command": probe_command,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if probe_returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
