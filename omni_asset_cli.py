#!/usr/bin/env python3
"""Unified CLI entry point for the omniverse USD asset validator helpers."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "omniverse-usd-asset-validator" / "scripts"


def script_path(name: str) -> Path:
    return SCRIPTS_DIR / name


def passthrough(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def add_common_validation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("asset", help="Path to the USD asset")
    parser.add_argument("--output-json", help="Path to the JSON output file")
    parser.add_argument("--output-md", help="Path to the Markdown report")
    parser.add_argument(
        "--pxr-ar-default-search-path",
        action="append",
        default=[],
        help="Additional resolver search path entries",
    )
    parser.add_argument("--profile", choices=["stage1-furniture", "static", "collidable", "movable"])
    parser.add_argument("--rule", action="append", default=[], help="Specific rule to enable")
    parser.add_argument("--category", action="append", default=[], help="Specific category to enable")
    parser.add_argument("--predicate", choices=["Any", "IsError", "IsFailure", "IsWarning", "HasRootLayer"])
    parser.add_argument("--init-rules", action="store_true", help="Enable default rule initialization")
    parser.add_argument("--variants", action="store_true", help="Enable variant processing")


def build_validate_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_sync_validation.py")), args.asset]

    if args.output_json:
        command.extend(["--output-json", args.output_json])
    if args.output_md:
        command.extend(["--output-md", args.output_md])
    if args.profile:
        command.extend(["--profile", args.profile])
    for item in args.pxr_ar_default_search_path:
        command.extend(["--pxr-ar-default-search-path", item])
    for item in args.rule:
        command.extend(["--rule", item])
    for item in args.category:
        command.extend(["--category", item])
    if args.predicate:
        command.extend(["--predicate", args.predicate])
    if args.init_rules:
        command.append("--init-rules")
    if args.variants:
        command.append("--variants")

    return command


def build_map_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("map_prompt_to_validation.py")), args.asset, args.prompt]

    if args.output_json:
        command.extend(["--output-json", args.output_json])
    for item in args.pxr_ar_default_search_path:
        command.extend(["--pxr-ar-default-search-path", item])
    if getattr(args, "execute", False):
        command.append("--execute")

    return command


def build_async_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_async_validation.py")), args.asset]

    if args.output_json:
        command.extend(["--output-json", args.output_json])
    if args.timeout_seconds is not None:
        command.extend(["--timeout-seconds", str(args.timeout_seconds)])
    if args.poll_seconds is not None:
        command.extend(["--poll-seconds", str(args.poll_seconds)])
    for item in args.rule:
        command.extend(["--rule", item])
    for item in args.category:
        command.extend(["--category", item])
    if args.predicate:
        command.extend(["--predicate", args.predicate])
    if args.fix:
        command.append("--fix")
    if args.no_variants:
        command.append("--no-variants")
    if args.no_init_rules:
        command.append("--no-init-rules")
    for item in args.extra_arg:
        command.extend(["--extra-arg", item])

    return command


def build_physics_hit_test_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_physics_hit_test.py")), args.asset]

    if args.template_scene:
        command.extend(["--template-scene", args.template_scene])
    if args.replace_prim:
        command.extend(["--replace-prim", args.replace_prim])
    if args.placement_mode:
        command.extend(["--placement-mode", args.placement_mode])
    if args.hit_mode:
        command.extend(["--hit-mode", args.hit_mode])
    if args.size_policy:
        command.extend(["--size-policy", args.size_policy])
    if args.frames is not None:
        command.extend(["--frames", str(args.frames)])
    if args.fps is not None:
        command.extend(["--fps", str(args.fps)])
    if args.out:
        command.extend(["--out", args.out])
    if args.no_headless:
        command.append("--no-headless")
    if args.runtime_python:
        command.extend(["--runtime-python", args.runtime_python])
    if args.runtime_platform:
        command.extend(["--runtime-platform", args.runtime_platform])
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    if args.render_frames:
        command.append("--render-frames")
    if args.render_every_n_frames is not None:
        command.extend(["--render-every-n-frames", str(args.render_every_n_frames)])
    if args.render_warmup_updates is not None:
        command.extend(["--render-warmup-updates", str(args.render_warmup_updates)])

    return command


def build_physics_env_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("check_physics_runtime_env.py"))]
    if args.runtime_python:
        command.extend(["--runtime-python", args.runtime_python])
    if args.runtime_platform:
        command.extend(["--runtime-platform", args.runtime_platform])
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    return command


def build_simready_flywheel_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_simready_flywheel.py")), args.asset]

    if args.out:
        command.extend(["--out", args.out])
    if args.inspector_root:
        command.extend(["--inspector-root", args.inspector_root])
    if args.reference_json:
        command.extend(["--reference-json", args.reference_json])
    if args.inspector_python:
        command.extend(["--inspector-python", args.inspector_python])
    if args.validator_python:
        command.extend(["--validator-python", args.validator_python])
    if args.output_format:
        command.extend(["--output-format", args.output_format])
    if args.max_prims is not None:
        command.extend(["--max-prims", str(args.max_prims)])
    if args.skip_validator:
        command.append("--skip-validator")
    if args.skip_runtime:
        command.append("--skip-runtime")
    if args.template_scene:
        command.extend(["--template-scene", args.template_scene])
    if args.frames is not None:
        command.extend(["--frames", str(args.frames)])
    if args.fps is not None:
        command.extend(["--fps", str(args.fps)])
    if args.runtime_python:
        command.extend(["--runtime-python", args.runtime_python])
    if args.runtime_platform:
        command.extend(["--runtime-platform", args.runtime_platform])
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    if args.render_frames:
        command.append("--render-frames")
    if args.render_every_n_frames is not None:
        command.extend(["--render-every-n-frames", str(args.render_every_n_frames)])

    return command


def cmd_env(_: argparse.Namespace) -> int:
    return passthrough([sys.executable, str(script_path("check_omniverse_asset_validator_env.py"))])


def cmd_validate(args: argparse.Namespace) -> int:
    return passthrough(build_validate_command(args))


def cmd_map(args: argparse.Namespace) -> int:
    return passthrough(build_map_command(args))


def cmd_validate_from_prompt(args: argparse.Namespace) -> int:
    command = build_map_command(args)
    if "--execute" not in command:
        command.append("--execute")
    return passthrough(command)


def cmd_validate_async(args: argparse.Namespace) -> int:
    return passthrough(build_async_command(args))


def cmd_physics_hit_test(args: argparse.Namespace) -> int:
    return passthrough(build_physics_hit_test_command(args))


def cmd_physics_env(args: argparse.Namespace) -> int:
    return passthrough(build_physics_env_command(args))


def cmd_simready_flywheel(args: argparse.Namespace) -> int:
    return passthrough(build_simready_flywheel_command(args))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified CLI for OpenUSD asset validation and agent-friendly orchestration.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    env_parser = subparsers.add_parser("env", help="Check the current validator runtime")
    env_parser.set_defaults(func=cmd_env)

    validate_parser = subparsers.add_parser("validate", help="Run synchronous validation")
    add_common_validation_args(validate_parser)
    validate_parser.set_defaults(func=cmd_validate)

    map_parser = subparsers.add_parser("map", help="Map a natural-language request to validation arguments")
    map_parser.add_argument("asset", help="Path to the USD asset")
    map_parser.add_argument("prompt", help="Natural-language validation request")
    map_parser.add_argument("--output-json", help="Path to the JSON output file for the generated command")
    map_parser.add_argument(
        "--pxr-ar-default-search-path",
        action="append",
        default=[],
        help="Additional resolver search path entries",
    )
    map_parser.add_argument("--execute", action="store_true", help="Execute the generated command")
    map_parser.set_defaults(func=cmd_map)

    validate_from_prompt_parser = subparsers.add_parser(
        "validate-from-prompt",
        help="Map a natural-language request and immediately run validation",
    )
    validate_from_prompt_parser.add_argument("asset", help="Path to the USD asset")
    validate_from_prompt_parser.add_argument("prompt", help="Natural-language validation request")
    validate_from_prompt_parser.add_argument(
        "--output-json",
        help="Path to the JSON output file for the generated command and validation result",
    )
    validate_from_prompt_parser.add_argument(
        "--pxr-ar-default-search-path",
        action="append",
        default=[],
        help="Additional resolver search path entries",
    )
    validate_from_prompt_parser.set_defaults(func=cmd_validate_from_prompt)

    async_parser = subparsers.add_parser("validate-async", help="Run asynchronous CLI validation")
    async_parser.add_argument("asset", help="Path to the USD asset or folder")
    async_parser.add_argument("--output-json", help="Path to the JSON output file")
    async_parser.add_argument("--timeout-seconds", type=int, default=300)
    async_parser.add_argument("--poll-seconds", type=float, default=2.0)
    async_parser.add_argument("--rule", action="append", default=[], help="Specific rule to enable")
    async_parser.add_argument("--category", action="append", default=[], help="Specific category to enable")
    async_parser.add_argument("--predicate", help="Optional predicate filter")
    async_parser.add_argument("--fix", action="store_true", help="Enable automatic fixes")
    async_parser.add_argument("--no-variants", action="store_true", help="Disable variant expansion")
    async_parser.add_argument("--no-init-rules", action="store_true", help="Disable default rule initialization")
    async_parser.add_argument("--extra-arg", action="append", default=[], help="Raw argument for omni_asset_validate")
    async_parser.set_defaults(func=cmd_validate_async)

    physics_parser = subparsers.add_parser(
        "physics-hit-test",
        help="Run a minimal runtime physics harness with a dynamic box hitting a static furniture/prop asset",
    )
    physics_parser.add_argument("asset", help="Path to the USD asset")
    physics_parser.add_argument(
        "--template-scene",
        help="Optional authored USD scene template with /World/TestAssetSlot and /World/boxActor",
    )
    physics_parser.add_argument(
        "--replace-prim",
        default="/World/roomScene/colliders/table",
        help=(
            "Template prim path to replace with the target asset. "
            "Only used with --template-scene; pass an empty value to use /World/TestAssetSlot instead."
        ),
    )
    physics_parser.add_argument(
        "--placement-mode",
        choices=["auto", "replace-table", "tabletop"],
        default="auto",
        help="Template placement strategy. Use replace-table for furniture and tabletop for decor props.",
    )
    physics_parser.add_argument(
        "--hit-mode",
        choices=["side-hit", "top-drop"],
        default="side-hit",
        help="How to drive the dynamic box. Use top-drop for Stage 1 furniture/prop checks.",
    )
    physics_parser.add_argument(
        "--size-policy",
        choices=["template-fit", "preserve"],
        default="template-fit",
        help="Whether template mode scales to the replaced prim footprint or preserves the asset's real size.",
    )
    physics_parser.add_argument("--frames", type=int, default=240, help="Number of frames to simulate")
    physics_parser.add_argument("--fps", type=float, default=60.0, help="Simulation frames per second")
    physics_parser.add_argument("--out", help="Output directory for runtime artifacts")
    physics_parser.add_argument("--no-headless", action="store_true", help="Disable headless runtime mode")
    physics_parser.add_argument("--runtime-python", help="Optional Isaac Sim python launcher path")
    physics_parser.add_argument(
        "--runtime-platform",
        choices=["auto", "linux", "windows"],
        default="auto",
        help="Target runtime platform when using an external Isaac Sim python",
    )
    physics_parser.add_argument(
        "--runtime-docker-image",
        help="Optional Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    physics_parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID to exec into",
    )
    physics_parser.add_argument(
        "--docker-workspace",
        default="/workspace/omni-asset-cli",
        help="Repository mount path inside the Isaac Sim container",
    )
    physics_parser.add_argument(
        "--docker-python",
        default="/isaac-sim/python.sh",
        help="Isaac Sim Python launcher path inside the container",
    )
    physics_parser.add_argument(
        "--render-frames",
        action="store_true",
        help="Capture headless viewport PNG frames during simulation into OUT/render_frames",
    )
    physics_parser.add_argument(
        "--render-every-n-frames",
        type=int,
        default=1,
        help="Capture every Nth simulation frame when --render-frames is enabled",
    )
    physics_parser.add_argument(
        "--render-warmup-updates",
        type=int,
        default=2,
        help="Extra app updates after each capture request so the PNG writer can flush",
    )
    physics_parser.set_defaults(func=cmd_physics_hit_test)

    physics_env_parser = subparsers.add_parser(
        "physics-env",
        help="Check whether the runtime physics harness can launch Isaac Sim in the current environment",
    )
    physics_env_parser.add_argument("--runtime-python", help="Optional Isaac Sim python launcher path")
    physics_env_parser.add_argument(
        "--runtime-platform",
        choices=["auto", "linux", "windows"],
        default="auto",
        help="Target runtime platform when using an external Isaac Sim python",
    )
    physics_env_parser.add_argument(
        "--runtime-docker-image",
        help="Optional Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    physics_env_parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID to exec into",
    )
    physics_env_parser.add_argument(
        "--docker-workspace",
        default="/workspace/omni-asset-cli",
        help="Repository mount path inside the Isaac Sim container",
    )
    physics_env_parser.add_argument(
        "--docker-python",
        default="/isaac-sim/python.sh",
        help="Isaac Sim Python launcher path inside the container",
    )
    physics_env_parser.set_defaults(func=cmd_physics_env)

    flywheel_parser = subparsers.add_parser(
        "simready-flywheel",
        help="Run validator defects, SimReady repair, and optional Isaac Sim top-drop retest",
    )
    flywheel_parser.add_argument("asset", help="Path to the source USD asset")
    flywheel_parser.add_argument("--out", help="Output directory for flywheel artifacts")
    flywheel_parser.add_argument(
        "--inspector-root",
        default=str(Path.home() / "usd-simready-inspector"),
        help="Path to the usd-simready-inspector checkout",
    )
    flywheel_parser.add_argument(
        "--reference-json",
        default=str(Path.home() / "usd-simready-inspector" / "simready_furniture_reference_with_wikidata.json"),
        help="Static furniture reference JSON for recommendation",
    )
    flywheel_parser.add_argument("--inspector-python", help="Python executable for usd-simready-inspector")
    flywheel_parser.add_argument("--validator-python", help="Python executable for omni-asset-cli validator scripts")
    flywheel_parser.add_argument(
        "--output-format",
        choices=["usda", "usdc"],
        default="usdc",
        help="Format for the repaired SimReady USD",
    )
    flywheel_parser.add_argument("--max-prims", type=int, default=0)
    flywheel_parser.add_argument("--skip-validator", action="store_true")
    flywheel_parser.add_argument("--skip-runtime", action="store_true")
    flywheel_parser.add_argument(
        "--template-scene",
        default=str(REPO_ROOT / "examples" / "mini_test.usda"),
        help="Isaac Sim physics template scene used by the top-drop runtime test",
    )
    flywheel_parser.add_argument("--frames", type=int, default=240)
    flywheel_parser.add_argument("--fps", type=float, default=60.0)
    flywheel_parser.add_argument("--runtime-python", help="Optional Isaac Sim python launcher path")
    flywheel_parser.add_argument(
        "--runtime-platform",
        choices=["auto", "linux", "windows"],
        default="auto",
        help="Target runtime platform when using an external Isaac Sim python",
    )
    flywheel_parser.add_argument(
        "--runtime-docker-image",
        help="Optional Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    flywheel_parser.add_argument("--runtime-docker-container", help="Optional running Isaac Sim container name or ID")
    flywheel_parser.add_argument(
        "--docker-workspace",
        default="/workspace/omni-asset-cli",
        help="Repository mount path inside the Isaac Sim container",
    )
    flywheel_parser.add_argument(
        "--docker-python",
        default="/isaac-sim/python.sh",
        help="Isaac Sim Python launcher path inside the container",
    )
    flywheel_parser.add_argument("--render-frames", action="store_true")
    flywheel_parser.add_argument("--render-every-n-frames", type=int, default=1)
    flywheel_parser.set_defaults(func=cmd_simready_flywheel)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
