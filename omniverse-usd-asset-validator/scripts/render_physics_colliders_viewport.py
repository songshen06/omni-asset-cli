#!/usr/bin/env python3
"""Capture Kit's native Physics > Colliders viewport display as a review artifact."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_physics_harness import RuntimeConfig, _make_docker_output_host_writable, _path_in_docker, preflight_runtime_docker_container


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture native Kit Physics > Colliders viewport output for a USD asset.")
    parser.add_argument("asset", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--physics-colliders", choices=["selected", "all"], default="selected")
    parser.add_argument("--collider-only", action="store_true")
    parser.add_argument("--frames", type=int, default=1)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--runtime-docker-image")
    parser.add_argument("--runtime-docker-container")
    parser.add_argument("--runtime-docker-preflight", choices=["auto", "check", "restart", "skip"], default="auto")
    parser.add_argument("--docker-workspace", default="/workspace/omni-asset-cli")
    parser.add_argument("--docker-python", default="/isaac-sim/python.sh")
    return parser.parse_args()


def _child_command(args: argparse.Namespace, config: RuntimeConfig) -> list[str]:
    script = Path(__file__).with_name("render_asset_setup_orbit.py").resolve()
    command = [
        _path_in_docker(script, config), _path_in_docker(args.asset, config),
        "--out", _path_in_docker(args.out, config),
        "--frames", str(args.frames), "--width", str(args.width), "--height", str(args.height),
        "--viewport-settle-updates", "600", "--camera-settle-updates", "300",
        "--physics-colliders", args.physics_colliders,
        "--hide-bbox-overlays", "--hide-center-marker", "--hide-articulation-overlays",
        "--/app/asyncRendering=false",
        "--/rtx/materialDb/syncLoads=true",
        "--/omni.kit.plugin/syncUsdLoads=true",
        "--/rtx/hydra/materialSyncLoads=true",
        "--/rtx-transient/resourcemanager/texturestreaming/async=false",
        "--/rtx-transient/resourcemanager/enableTextureStreaming=false",
        "--/exts/omni.kit.window.viewport/blockingGetViewportDrawable=true",
        "--/rtx-transient/dlssg/enabled=false",
        "--/persistent/app/viewport/defaults/fillViewport=false",
    ]
    if args.collider_only:
        command.append("--collider-only")
    return command


def _write_manifest(
    args: argparse.Namespace,
    returncode: int,
    preflight: dict[str, Any] | None,
    *,
    command: list[str] | None = None,
    artifact_error: str | None = None,
) -> Path:
    summary = args.out / "setup_orbit_summary.json"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact_type": "kit-viewport-physics-colliders",
        "asset": str(args.asset),
        "physics_menu": {"colliders": args.physics_colliders},
        "selected_prim_policy": "all authored CollisionAPI prims" if args.physics_colliders == "selected" else None,
        "png_frames_dir": str(args.out / "orbit_frames"),
        "first_png": str(args.out / "orbit_frames" / "frame_0000.png"),
        "debug_stage": str(args.out / "cup_setup_orbit_debug.usda"),
        "setup_orbit_summary": str(summary),
        "returncode": returncode,
        "docker_preflight": preflight,
        "source_asset_modified": False,
    }
    if command is not None:
        payload["command"] = command
    if artifact_error is not None:
        payload["artifact_error"] = artifact_error
    if summary.exists():
        try:
            payload["native_physx_display"] = json.loads(summary.read_text(encoding="utf-8")).get("physics_colliders")
        except Exception as exc:
            payload["summary_read_error"] = f"{type(exc).__name__}: {exc}"
    manifest = args.out / "physics_colliders_view_manifest.json"
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    args = parse_args()
    args.asset = args.asset.resolve()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    # Isaac Sim images run as a different UID from the host workspace user.
    # The capture output is an explicit artifact directory, so make only this
    # directory writable before bind-mounting it through the repository mount.
    try:
        args.out.chmod(0o777)
    except PermissionError as exc:
        raise RuntimeError(f"cannot make viewport output directory writable for Isaac Docker: {args.out}") from exc
    config = RuntimeConfig(
        asset=args.asset,
        out_dir=args.out,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        runtime_docker_preflight=args.runtime_docker_preflight,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
    )
    preflight = preflight_runtime_docker_container(config) if args.runtime_docker_container else None
    if preflight and (preflight.get("ready") is False or preflight.get("action") == "blocked_residual_processes"):
        print(_write_manifest(args, 2, preflight))
        return 2

    if args.runtime_docker_container:
        command = ["docker", "exec", "-w", args.docker_workspace, args.runtime_docker_container, args.docker_python, *_child_command(args, config)]
    elif args.runtime_docker_image:
        command = [
            "docker", "run", "--rm", "--gpus", "all", "--network", "host", "--ipc", "host",
            "-e", "ACCEPT_EULA=Y", "-e", "PRIVACY_CONSENT=Y",
            "-e", "OMNI_ENV_ACCEPT_EULA=Y", "-e", "OMNI_ENV_PRIVACY_CONSENT=Y",
            "-v", f"{Path(__file__).resolve().parents[2]}:{args.docker_workspace}",
            "-w", args.docker_workspace, "--entrypoint", args.docker_python, args.runtime_docker_image,
            *_child_command(args, config),
        ]
    else:
        script = Path(__file__).with_name("render_asset_setup_orbit.py").resolve()
        command = [
            sys.executable, str(script), str(args.asset), "--out", str(args.out),
            "--frames", str(args.frames), "--width", str(args.width), "--height", str(args.height),
            "--physics-colliders", args.physics_colliders,
            "--hide-bbox-overlays", "--hide-center-marker", "--hide-articulation-overlays",
        ]
        if args.collider_only:
            command.append("--collider-only")
    completed = subprocess.run(command, check=False)
    if args.runtime_docker_container:
        _make_docker_output_host_writable(config)
    output_returncode = completed.returncode
    artifact_error = None
    expected_png = args.out / "orbit_frames" / "frame_0000.png"
    if output_returncode == 0 and not expected_png.exists():
        output_returncode = 1
        artifact_error = f"viewport capture returned success but did not write expected PNG: {expected_png}"
    print(_write_manifest(args, output_returncode, preflight, command=command, artifact_error=artifact_error))
    return output_returncode


if __name__ == "__main__":
    raise SystemExit(main())
