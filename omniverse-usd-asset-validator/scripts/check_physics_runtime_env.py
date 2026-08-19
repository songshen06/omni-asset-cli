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
    require_gpu: bool = False


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
    parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="Require host and Isaac Sim Docker runtime GPU visibility for rendered video evidence.",
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
                "-e",
                "OMNI_ENV_ACCEPT_EULA=Y",
                "-e",
                "OMNI_ENV_PRIVACY_CONSENT=Y",
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


def _run_command(command: list[str], timeout: float = 30.0) -> dict[str, object]:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc), "command": command}
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "timeout",
            "command": command,
        }
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "").strip(),
        "stderr": (completed.stderr or "").strip(),
        "command": command,
    }


def _docker_base_command(config: ProbeConfig) -> list[str] | None:
    if config.runtime_docker_container:
        return ["docker", "exec", config.runtime_docker_container]
    if not config.runtime_docker_image:
        return None
    return [
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
        config.runtime_docker_image,
    ]


def _gpu_probe(config: ProbeConfig) -> dict[str, object]:
    host = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,driver_version,memory.total",
            "--format=csv,noheader",
        ],
        timeout=10.0,
    )
    if not config.runtime_docker_container and not config.runtime_docker_image:
        return {
            "required": config.require_gpu,
            "ready": False,
            "host_nvidia_smi": host,
            "reason": "No Docker runtime was provided for GPU probing.",
        }

    if config.runtime_docker_container:
        container_nvml_command = [
            "docker", "exec", config.runtime_docker_container, "nvidia-smi",
            "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader",
        ]
        container_cuda_command_prefix = ["docker", "exec", config.runtime_docker_container, config.docker_python]
    else:
        image_base = [
            "docker", "run", "--rm", "--gpus", "all", "--network", "host", "--ipc", "host",
            "-e", "ACCEPT_EULA=Y", "-e", "PRIVACY_CONSENT=Y",
            "-e", "OMNI_ENV_ACCEPT_EULA=Y", "-e", "OMNI_ENV_PRIVACY_CONSENT=Y",
        ]
        container_nvml_command = [
            *image_base, "--entrypoint", "nvidia-smi", config.runtime_docker_image,
            "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader",
        ]
        container_cuda_command_prefix = [*image_base, "--entrypoint", config.docker_python, config.runtime_docker_image]
    container_nvml = _run_command(container_nvml_command, timeout=60.0)
    torch_probe = """import json
try:
    import torch
    print(json.dumps({"torch_imported": True, "cuda_available": torch.cuda.is_available(), "device_count": torch.cuda.device_count()}))
except Exception as exc:
    print(json.dumps({"torch_imported": False, "error": repr(exc)}))
"""
    container_cuda = _run_command(container_cuda_command_prefix + ["-c", torch_probe], timeout=60.0)
    cuda_payload: dict[str, object] = {}
    try:
        cuda_payload = json.loads(str(container_cuda.get("stdout") or "{}"))
    except json.JSONDecodeError:
        cuda_payload = {}

    ready = bool(
        host.get("ok")
        and container_nvml.get("ok")
        and cuda_payload.get("cuda_available") is True
        and int(cuda_payload.get("device_count") or 0) > 0
    )
    reason = None
    if not ready:
        if not host.get("ok"):
            reason = "Host nvidia-smi failed; host GPU/driver is not visible."
        elif not container_nvml.get("ok"):
            reason = "Docker runtime cannot initialize NVML; recreate the Isaac Sim container with compatible NVIDIA driver/runtime."
        elif cuda_payload.get("cuda_available") is not True:
            reason = "Docker Isaac Python cannot see CUDA devices."
        else:
            reason = "GPU probe failed for an unknown reason."

    return {
        "required": config.require_gpu,
        "ready": ready,
        "reason": reason,
        "host_nvidia_smi": host,
        "container_nvidia_smi": container_nvml,
        "container_cuda_python": {
            **container_cuda,
            "parsed": cuda_payload,
        },
    }


def main() -> int:
    args = parse_args()
    config = ProbeConfig(
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
        require_gpu=args.require_gpu,
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
        "require_gpu": args.require_gpu,
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
    payload["gpu_probe"] = _gpu_probe(config)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if probe_returncode != 0:
        return 2
    if args.require_gpu and not payload["gpu_probe"]["ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
