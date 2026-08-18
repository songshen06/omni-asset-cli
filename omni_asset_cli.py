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
    if args.asset_rotation_y_deg:
        command.extend(["--asset-rotation-y-deg", str(args.asset_rotation_y_deg)])
    if args.asset_rotation_z_deg:
        command.extend(["--asset-rotation-z-deg", str(args.asset_rotation_z_deg)])
    if args.frames is not None:
        command.extend(["--frames", str(args.frames)])
    if args.fps is not None:
        command.extend(["--fps", str(args.fps)])
    if args.out:
        command.extend(["--out", args.out])
    if args.no_headless:
        command.append("--no-headless")
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.runtime_docker_preflight:
        command.extend(["--runtime-docker-preflight", args.runtime_docker_preflight])
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
    for item in args.render_camera_preset:
        command.extend(["--render-camera-preset", item])
    if args.render_backend:
        command.extend(["--render-backend", args.render_backend])
    if args.render_width is not None:
        command.extend(["--render-width", str(args.render_width)])
    if args.render_height is not None:
        command.extend(["--render-height", str(args.render_height)])
    if args.render_rt_subframes is not None:
        command.extend(["--render-rt-subframes", str(args.render_rt_subframes)])
    if args.render_wait_updates is not None:
        command.extend(["--render-wait-updates", str(args.render_wait_updates)])
    if args.render_video:
        command.append("--render-video")
    if args.render_video_style:
        command.extend(["--render-video-style", args.render_video_style])
    if args.render_video_fps is not None:
        command.extend(["--render-video-fps", str(args.render_video_fps)])
    if args.render_video_crf is not None:
        command.extend(["--render-video-crf", str(args.render_video_crf)])
    for item in args.render_material_mode:
        command.extend(["--render-material-mode", item])
    if args.render_camera_distance_scale is not None:
        command.extend(["--render-camera-distance-scale", str(args.render_camera_distance_scale)])
    if args.render_camera_focal_length is not None:
        command.extend(["--render-camera-focal-length", str(args.render_camera_focal_length)])
    if args.render_camera_elevation_deg is not None:
        command.extend(["--render-camera-elevation-deg", str(args.render_camera_elevation_deg)])
    if args.render_timeout_seconds is not None:
        command.extend(["--render-timeout-seconds", str(args.render_timeout_seconds)])
    if args.render_physics_bboxes:
        command.append("--render-physics-bboxes")
    if args.render_physics_bbox_fallback_default_prim:
        command.append("--render-physics-bbox-fallback-default-prim")
    if args.render_physics_bbox_width is not None:
        command.extend(["--render-physics-bbox-width", str(args.render_physics_bbox_width)])

    return command


def build_physics_env_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("check_physics_runtime_env.py"))]
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    if getattr(args, "require_gpu", False):
        command.append("--require-gpu")
    return command


def build_foundation_validate_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_foundation_validation.py")), args.asset,
               "--package", args.package, "--foundation-tag", args.foundation_tag]
    if args.foundation_root:
        command.extend(["--foundation-root", args.foundation_root])
    if args.foundation_python:
        command.extend(["--foundation-python", args.foundation_python])
    if args.foundation_command:
        command.extend(["--foundation-command", args.foundation_command])
    if args.official_cli:
        command.append("--official-cli")
    if args.out:
        command.extend(["--out", args.out])
    if args.shadow:
        command.append("--shadow")
    return command


def build_foundation_repair_plan_command(args: argparse.Namespace) -> list[str]:
    return [sys.executable, str(script_path("foundation_repair_plan.py")), args.findings, "--out", args.out]


def build_apply_foundation_repair_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("apply_foundation_repair.py")), args.repair_plan, "--out", args.out]
    if args.apply_safe:
        command.append("--apply-safe")
    return command


def build_articulated_policy_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("check_articulated_cart_policy.py")), args.asset, "--out", args.out]
    if args.expected_rigid_bodies is not None:
        command.extend(["--expected-rigid-bodies", str(args.expected_rigid_bodies)])
    if args.expected_joints is not None:
        command.extend(["--expected-joints", str(args.expected_joints)])
    if args.scope:
        command.extend(["--scope", args.scope])
    return command


def build_physics_collider_audit_command(args: argparse.Namespace) -> list[str]:
    return [sys.executable, str(script_path("check_primitive_collider_semantics.py")), args.asset, "--out", args.out]


def build_articulated_physics_workflow_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable, str(script_path("run_articulated_physics_workflow.py")), args.asset,
        "--foundation-root", args.foundation_root,
        "--foundation-python", args.foundation_python,
        "--foundation-tag", args.foundation_tag,
        "--out", args.out,
    ]


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
    if args.content_label:
        command.extend(["--content-label", args.content_label])
    if args.target_bbox_cm:
        command.extend(["--target-bbox-cm", args.target_bbox_cm])
    if args.skip_validator:
        command.append("--skip-validator")
    if args.skip_runtime:
        command.append("--skip-runtime")
    if args.allow_mesh_defects:
        command.append("--allow-mesh-defects")
    if args.allow_missing_assets:
        command.append("--allow-missing-assets")
    if args.template_scene:
        command.extend(["--template-scene", args.template_scene])
    if args.frames is not None:
        command.extend(["--frames", str(args.frames)])
    if args.fps is not None:
        command.extend(["--fps", str(args.fps)])
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.runtime_docker_preflight:
        command.extend(["--runtime-docker-preflight", args.runtime_docker_preflight])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    if args.render_frames:
        command.append("--render-frames")
    if args.render_every_n_frames is not None:
        command.extend(["--render-every-n-frames", str(args.render_every_n_frames)])
    for item in args.render_camera_preset:
        command.extend(["--render-camera-preset", item])
    if args.render_backend:
        command.extend(["--render-backend", args.render_backend])
    if args.render_width is not None:
        command.extend(["--render-width", str(args.render_width)])
    if args.render_height is not None:
        command.extend(["--render-height", str(args.render_height)])
    if args.render_rt_subframes is not None:
        command.extend(["--render-rt-subframes", str(args.render_rt_subframes)])
    if args.render_wait_updates is not None:
        command.extend(["--render-wait-updates", str(args.render_wait_updates)])
    if args.render_video:
        command.append("--render-video")
    if args.render_video_fps is not None:
        command.extend(["--render-video-fps", str(args.render_video_fps)])
    if args.render_video_crf is not None:
        command.extend(["--render-video-crf", str(args.render_video_crf)])
    if args.render_physics_bboxes:
        command.append("--render-physics-bboxes")
    if args.render_physics_bbox_fallback_default_prim:
        command.append("--render-physics-bbox-fallback-default-prim")
    if args.render_physics_bbox_width is not None:
        command.extend(["--render-physics-bbox-width", str(args.render_physics_bbox_width)])

    return command


def build_stage1_runtime_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(script_path("run_stage1_runtime_workflow.py")), args.asset]

    if args.out:
        command.extend(["--out", args.out])
    if args.template_scene:
        command.extend(["--template-scene", args.template_scene])
    if args.placement_mode:
        command.extend(["--placement-mode", args.placement_mode])
    if args.size_policy:
        command.extend(["--size-policy", args.size_policy])
    if args.frames is not None:
        command.extend(["--frames", str(args.frames)])
    if args.fps is not None:
        command.extend(["--fps", str(args.fps)])
    if args.asset_rotation_y_deg:
        command.extend(["--asset-rotation-y-deg", str(args.asset_rotation_y_deg)])
    if args.asset_rotation_z_deg:
        command.extend(["--asset-rotation-z-deg", str(args.asset_rotation_z_deg)])
    if args.runtime_docker_container:
        command.extend(["--runtime-docker-container", args.runtime_docker_container])
    if args.runtime_docker_image:
        command.extend(["--runtime-docker-image", args.runtime_docker_image])
    if args.no_default_container:
        command.append("--no-default-container")
    if args.runtime_docker_preflight:
        command.extend(["--runtime-docker-preflight", args.runtime_docker_preflight])
    if args.docker_workspace:
        command.extend(["--docker-workspace", args.docker_workspace])
    if args.docker_python:
        command.extend(["--docker-python", args.docker_python])
    if args.evidence_preset:
        command.extend(["--evidence-preset", args.evidence_preset])
    if args.render_frames:
        command.append("--render-frames")
    if args.render_every_n_frames is not None:
        command.extend(["--render-every-n-frames", str(args.render_every_n_frames)])
    for item in args.render_camera_preset:
        command.extend(["--render-camera-preset", item])
    if args.render_backend:
        command.extend(["--render-backend", args.render_backend])
    if args.render_width is not None:
        command.extend(["--render-width", str(args.render_width)])
    if args.render_height is not None:
        command.extend(["--render-height", str(args.render_height)])
    if args.render_rt_subframes is not None:
        command.extend(["--render-rt-subframes", str(args.render_rt_subframes)])
    if args.render_wait_updates is not None:
        command.extend(["--render-wait-updates", str(args.render_wait_updates)])
    if args.render_video:
        command.append("--render-video")
    if args.render_video_style:
        command.extend(["--render-video-style", args.render_video_style])
    if args.render_video_fps is not None:
        command.extend(["--render-video-fps", str(args.render_video_fps)])
    if args.render_video_crf is not None:
        command.extend(["--render-video-crf", str(args.render_video_crf)])
    if args.render_physics_bboxes:
        command.append("--render-physics-bboxes")
    if args.render_physics_bbox_fallback_default_prim:
        command.append("--render-physics-bbox-fallback-default-prim")
    if args.render_physics_bbox_width is not None:
        command.extend(["--render-physics-bbox-width", str(args.render_physics_bbox_width)])
    if args.contact_timeout_seconds is not None:
        command.extend(["--contact-timeout-seconds", str(args.contact_timeout_seconds)])
    if args.visual_timeout_seconds is not None:
        command.extend(["--visual-timeout-seconds", str(args.visual_timeout_seconds)])

    return command


def build_gallery_command(args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(REPO_ROOT / "scripts" / "build_out_gallery.py")]
    if args.out_dir:
        command.extend(["--out-dir", args.out_dir])
    if args.output:
        command.extend(["--output", args.output])
    if args.title:
        command.extend(["--title", args.title])
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


def cmd_foundation_validate(args: argparse.Namespace) -> int:
    return passthrough(build_foundation_validate_command(args))


def cmd_foundation_repair_plan(args: argparse.Namespace) -> int:
    return passthrough(build_foundation_repair_plan_command(args))


def cmd_apply_foundation_repair(args: argparse.Namespace) -> int:
    return passthrough(build_apply_foundation_repair_command(args))


def cmd_articulated_policy(args: argparse.Namespace) -> int:
    return passthrough(build_articulated_policy_command(args))


def cmd_physics_collider_audit(args: argparse.Namespace) -> int:
    return passthrough(build_physics_collider_audit_command(args))


def cmd_simready_flywheel(args: argparse.Namespace) -> int:
    return passthrough(build_simready_flywheel_command(args))


def cmd_stage1_runtime(args: argparse.Namespace) -> int:
    return passthrough(build_stage1_runtime_command(args))


def cmd_gallery(args: argparse.Namespace) -> int:
    return passthrough(build_gallery_command(args))


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
        choices=["auto", "replace-table", "tabletop", "replace-box"],
        default="auto",
        help="Template placement strategy. Use replace-table for furniture, tabletop for decor props, or replace-box for the falling actor.",
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
    physics_parser.add_argument(
        "--asset-rotation-y-deg",
        type=float,
        default=0.0,
        help="Initial local Y-axis rotation applied to the referenced asset before running the test.",
    )
    physics_parser.add_argument(
        "--asset-rotation-z-deg",
        type=float,
        default=0.0,
        help="Initial local Z-axis rotation applied to the referenced asset before running the test.",
    )
    physics_parser.add_argument("--frames", type=int, default=240, help="Number of frames to simulate")
    physics_parser.add_argument("--fps", type=float, default=60.0, help="Simulation frames per second")
    physics_parser.add_argument("--out", help="Output directory for runtime artifacts")
    physics_parser.add_argument("--no-headless", action="store_true", help="Disable headless runtime mode")
    physics_parser.add_argument(
        "--runtime-docker-image",
        help="Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    physics_parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID to exec into",
    )
    physics_parser.add_argument(
        "--runtime-docker-preflight",
        choices=["auto", "check", "restart", "skip"],
        default="restart",
        help=(
            "Container clean-start policy before docker exec. restart always restarts; auto restarts only when "
            "stale Isaac/Kit processes are found; check blocks on stale processes; skip disables it."
        ),
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
    physics_parser.add_argument(
        "--render-camera-preset",
        action="append",
        default=[],
        help=(
            "Camera preset to capture when --render-frames or --render-video is enabled. "
            "Repeat or pass comma-separated values. Choices: active, front, back, left, right, side, top, iso."
        ),
    )
    physics_parser.add_argument(
        "--render-backend",
        choices=["replicator", "viewport"],
        default="replicator",
        help="Frame capture backend. Replicator matches the standalone video render script more closely.",
    )
    physics_parser.add_argument("--render-width", type=int, default=1280, help="Rendered frame width")
    physics_parser.add_argument("--render-height", type=int, default=720, help="Rendered frame height")
    physics_parser.add_argument("--render-rt-subframes", type=int, default=4, help="Replicator subframes per frame")
    physics_parser.add_argument("--render-wait-updates", type=int, default=20, help="App updates to wait for frame writes")
    physics_parser.add_argument(
        "--render-video",
        action="store_true",
        help="Encode captured render frames into one mp4 per camera under OUT/render_videos",
    )
    physics_parser.add_argument(
        "--render-video-style",
        choices=["hit-test", "asset-table-drop"],
        default="hit-test",
        help=(
            "Video renderer style. asset-table-drop delegates to render_asset_table_drop.py "
            "so output matches the standalone validated renderer."
        ),
    )
    physics_parser.add_argument(
        "--render-video-fps",
        type=float,
        help="Frame rate for encoded mp4 output; defaults to simulation fps divided by render-every-n-frames",
    )
    physics_parser.add_argument(
        "--render-video-crf",
        type=int,
        default=23,
        help="libx264 CRF value used when --render-video is enabled",
    )
    physics_parser.add_argument(
        "--render-material-mode",
        action="append",
        default=[],
        help="Material mode for asset-table-drop videos. Repeat or pass comma-separated values. Choices: all, material, transparent.",
    )
    physics_parser.add_argument(
        "--render-camera-distance-scale",
        type=float,
        default=None,
        help="Camera distance scale for asset-table-drop videos.",
    )
    physics_parser.add_argument(
        "--render-camera-focal-length",
        type=float,
        default=None,
        help="Camera focal length for asset-table-drop videos.",
    )
    physics_parser.add_argument(
        "--render-camera-elevation-deg",
        type=float,
        default=None,
        help="Camera elevation in degrees for asset-table-drop videos.",
    )
    physics_parser.add_argument(
        "--render-timeout-seconds",
        type=float,
        default=0.0,
        help="Hard timeout for asset-table-drop video rendering; 0 chooses a conservative default.",
    )
    physics_parser.add_argument(
        "--render-physics-bboxes",
        action="store_true",
        help="Draw temporary session-layer bbox curves for asset collider prims during rendered frame capture",
    )
    physics_parser.add_argument(
        "--render-physics-bbox-fallback-default-prim",
        action="store_true",
        help="When no collider paths are available, draw the asset prim bbox for capture debugging only",
    )
    physics_parser.add_argument(
        "--render-physics-bbox-width",
        type=float,
        default=0.0,
        help="BBox line width in stage units; 0 chooses an automatic width",
    )
    physics_parser.set_defaults(func=cmd_physics_hit_test)

    physics_env_parser = subparsers.add_parser(
        "physics-env",
        help="Check Linux + Isaac Sim Docker runtime readiness",
    )
    physics_env_parser.add_argument(
        "--runtime-docker-image",
        help="Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
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
    physics_env_parser.add_argument(
        "--require-gpu",
        action="store_true",
        help="Require host and Isaac Sim Docker GPU visibility (needed for rendered evidence).",
    )
    physics_env_parser.set_defaults(func=cmd_physics_env)

    foundation_parser = subparsers.add_parser(
        "foundation-validate",
        help="Run pinned SimReady Foundation validation and write normalized shadow findings",
    )
    foundation_parser.add_argument("asset", help="Path to the USD asset")
    foundation_parser.add_argument("--package", choices=["static-prop", "physics-prop", "articulated-asset", "runnable-robot"], required=True)
    foundation_parser.add_argument("--foundation-tag", required=True, help="Approved SimReady Foundation release tag")
    foundation_parser.add_argument("--foundation-root", help="Foundation checkout pinned to the release tag")
    foundation_parser.add_argument("--foundation-python", help="Python interpreter in the isolated Foundation environment")
    foundation_parser.add_argument("--foundation-command", help="Executor template with {asset}, {profile}, {out}, {tag}, {python}")
    foundation_parser.add_argument("--official-cli", action="store_true", help="Run the pinned official simready-validate CLI")
    foundation_parser.add_argument("--out", help="Output directory for foundation_validation.json")
    foundation_parser.add_argument("--shadow", action="store_true", help="Do not affect existing validation or customer status")
    foundation_parser.set_defaults(func=cmd_foundation_validate)

    repair_plan_parser = subparsers.add_parser("foundation-repair-plan", help="Create a reviewable repair_plan.json from Foundation findings")
    repair_plan_parser.add_argument("findings", help="foundation_validation.json or normalized foundation_findings.json")
    repair_plan_parser.add_argument("--out", required=True, help="Output directory")
    repair_plan_parser.set_defaults(func=cmd_foundation_repair_plan)

    apply_repair_parser = subparsers.add_parser("apply-foundation-repair", help="Create a non-destructive candidate from an approved repair plan")
    apply_repair_parser.add_argument("repair_plan", help="repair_plan.json")
    apply_repair_parser.add_argument("--out", required=True, help="Output directory")
    apply_repair_parser.add_argument("--apply-safe", action="store_true", help="Approve safe items only; never overwrite the source asset")
    apply_repair_parser.set_defaults(func=cmd_apply_foundation_repair)

    articulated_policy_parser = subparsers.add_parser("articulated-cart-policy", help="Check the articulated-cart rigid-body and joint graph")
    articulated_policy_parser.add_argument("asset", help="Path to the USD asset")
    articulated_policy_parser.add_argument("--out", required=True, help="Output directory")
    articulated_policy_parser.add_argument("--expected-rigid-bodies", type=int, default=13)
    articulated_policy_parser.add_argument("--expected-joints", type=int, default=12)
    articulated_policy_parser.add_argument("--scope", choices=["topology", "physics-structure"], default="topology")
    articulated_policy_parser.set_defaults(func=cmd_articulated_policy)

    collider_audit_parser = subparsers.add_parser(
        "physics-collider-audit",
        help="Detect ambiguous MeshCollisionAPI/approximation schemas on primitive colliders without modifying the asset",
    )
    collider_audit_parser.add_argument("asset", help="Path to the USD asset")
    collider_audit_parser.add_argument("--out", required=True, help="Output directory for primitive_collider_audit.json")
    collider_audit_parser.set_defaults(func=cmd_physics_collider_audit)

    articulated_workflow_parser = subparsers.add_parser(
        "articulated-physics-workflow",
        help="Run Prop-Robotics-Physx plus focused nested-body and collider-schema gates",
    )
    articulated_workflow_parser.add_argument("asset", help="Path to the USD asset")
    articulated_workflow_parser.add_argument("--foundation-root", required=True)
    articulated_workflow_parser.add_argument("--foundation-python", required=True)
    articulated_workflow_parser.add_argument("--foundation-tag", default="v2026.04.1")
    articulated_workflow_parser.add_argument("--out", required=True)
    articulated_workflow_parser.set_defaults(func=lambda args: passthrough(build_articulated_physics_workflow_command(args)))

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
    flywheel_parser.add_argument(
        "--content-label",
        help=(
            "Optional normalized content label used by usd-simready-inspector for built-in "
            "physical size priors, e.g. wine_bottle, chair, basketball, soccer_ball."
        ),
    )
    flywheel_parser.add_argument(
        "--target-bbox-cm",
        help="Explicit target bbox in centimeters as X,Y,Z; overrides any content-label size prior.",
    )
    flywheel_parser.add_argument("--skip-validator", action="store_true")
    flywheel_parser.add_argument("--skip-runtime", action="store_true")
    flywheel_parser.add_argument(
        "--allow-mesh-defects",
        action="store_true",
        help="Pass through to usd-simready-inspector process when mesh preflight defects are explicitly accepted",
    )
    flywheel_parser.add_argument(
        "--allow-missing-assets",
        action="store_true",
        help="Pass through to usd-simready-inspector process when missing asset dependencies are explicitly accepted",
    )
    flywheel_parser.add_argument(
        "--template-scene",
        default=str(REPO_ROOT / "examples" / "mini_test.usda"),
        help="Isaac Sim physics template scene used by the top-drop runtime test",
    )
    flywheel_parser.add_argument("--frames", type=int, default=240)
    flywheel_parser.add_argument("--fps", type=float, default=60.0)
    flywheel_parser.add_argument(
        "--runtime-docker-image",
        help="Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    flywheel_parser.add_argument("--runtime-docker-container", help="Optional running Isaac Sim container name or ID")
    flywheel_parser.add_argument(
        "--runtime-docker-preflight",
        choices=["auto", "check", "restart", "skip"],
        default="restart",
    )
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
    flywheel_parser.add_argument("--render-camera-preset", action="append", default=[])
    flywheel_parser.add_argument("--render-backend", choices=["replicator", "viewport"], default="replicator")
    flywheel_parser.add_argument("--render-width", type=int, default=1280)
    flywheel_parser.add_argument("--render-height", type=int, default=720)
    flywheel_parser.add_argument("--render-rt-subframes", type=int, default=4)
    flywheel_parser.add_argument("--render-wait-updates", type=int, default=20)
    flywheel_parser.add_argument("--render-video", action="store_true")
    flywheel_parser.add_argument("--render-video-fps", type=float)
    flywheel_parser.add_argument("--render-video-crf", type=int, default=23)
    flywheel_parser.add_argument("--render-physics-bboxes", action="store_true")
    flywheel_parser.add_argument("--render-physics-bbox-fallback-default-prim", action="store_true")
    flywheel_parser.add_argument("--render-physics-bbox-width", type=float, default=0.0)
    flywheel_parser.set_defaults(func=cmd_simready_flywheel)

    stage1_runtime_parser = subparsers.add_parser(
        "stage1-runtime",
        help="Run the fixed Stage 1 Docker runtime workflow: preflight, top-drop hit test, and evidence report",
    )
    stage1_runtime_parser.add_argument("asset", help="Path to the USD asset")
    stage1_runtime_parser.add_argument("--out", help="Output directory for workflow artifacts")
    stage1_runtime_parser.add_argument(
        "--template-scene",
        default=str(REPO_ROOT / "examples" / "mini_test.usda"),
        help="Isaac Sim physics template scene used by the top-drop runtime test",
    )
    stage1_runtime_parser.add_argument(
        "--placement-mode",
        choices=["replace-table", "tabletop", "replace-box"],
        default="replace-table",
        help="Stage 1 placement strategy",
    )
    stage1_runtime_parser.add_argument(
        "--size-policy",
        choices=["preserve", "template-fit"],
        default="preserve",
        help="Whether to preserve the asset's authored size",
    )
    stage1_runtime_parser.add_argument("--frames", type=int, default=240)
    stage1_runtime_parser.add_argument("--fps", type=float, default=60.0)
    stage1_runtime_parser.add_argument("--asset-rotation-y-deg", type=float, default=0.0)
    stage1_runtime_parser.add_argument("--asset-rotation-z-deg", type=float, default=0.0)
    stage1_runtime_parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID. Defaults to isaac-sim unless --runtime-docker-image is supplied.",
    )
    stage1_runtime_parser.add_argument(
        "--runtime-docker-image",
        help="Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    stage1_runtime_parser.add_argument(
        "--no-default-container",
        action="store_true",
        help="Do not default to the isaac-sim running container when no image/container is supplied",
    )
    stage1_runtime_parser.add_argument(
        "--runtime-docker-preflight",
        choices=["auto", "check", "restart", "skip"],
        default="restart",
    )
    stage1_runtime_parser.add_argument(
        "--docker-workspace",
        default="/workspace/omni-asset-cli",
        help="Repository mount path inside the Isaac Sim container",
    )
    stage1_runtime_parser.add_argument(
        "--docker-python",
        default="/isaac-sim/python.sh",
        help="Isaac Sim Python launcher path inside the container",
    )
    stage1_runtime_parser.add_argument(
        "--evidence-preset",
        choices=["standard", "contact-only", "custom"],
        default="standard",
        help=(
            "Evidence bundle to collect. standard records PhysX contact evidence plus "
            "front/side/top/iso videos with physics bbox overlays."
        ),
    )
    stage1_runtime_parser.add_argument("--render-frames", action="store_true")
    stage1_runtime_parser.add_argument("--render-every-n-frames", type=int)
    stage1_runtime_parser.add_argument("--render-camera-preset", action="append", default=[])
    stage1_runtime_parser.add_argument("--render-backend", choices=["replicator", "viewport"], default="replicator")
    stage1_runtime_parser.add_argument("--render-width", type=int, default=1280)
    stage1_runtime_parser.add_argument("--render-height", type=int, default=720)
    stage1_runtime_parser.add_argument("--render-rt-subframes", type=int, default=4)
    stage1_runtime_parser.add_argument("--render-wait-updates", type=int, default=20)
    stage1_runtime_parser.add_argument("--render-video", action="store_true")
    stage1_runtime_parser.add_argument(
        "--render-video-style",
        choices=["hit-test", "asset-table-drop"],
        default="hit-test",
    )
    stage1_runtime_parser.add_argument("--render-video-fps", type=float)
    stage1_runtime_parser.add_argument("--render-video-crf", type=int, default=23)
    stage1_runtime_parser.add_argument("--render-physics-bboxes", action="store_true")
    stage1_runtime_parser.add_argument("--render-physics-bbox-fallback-default-prim", action="store_true")
    stage1_runtime_parser.add_argument("--render-physics-bbox-width", type=float, default=0.0)
    stage1_runtime_parser.add_argument(
        "--contact-timeout-seconds",
        type=float,
        default=900.0,
        help="Hard timeout for the contact-evidence hit test. 0 disables the timeout.",
    )
    stage1_runtime_parser.add_argument(
        "--visual-timeout-seconds",
        type=float,
        default=900.0,
        help="Hard timeout for visual/video evidence. 0 disables the timeout.",
    )
    stage1_runtime_parser.set_defaults(func=cmd_stage1_runtime)

    gallery_parser = subparsers.add_parser(
        "gallery",
        help="Build a lightweight static HTML gallery for images and videos under out/",
    )
    gallery_parser.add_argument("--out-dir", default="out", help="Directory to scan for media artifacts")
    gallery_parser.add_argument("--output", default="out/gallery.html", help="HTML file to write")
    gallery_parser.add_argument("--title", default="Omni Asset Output Gallery", help="Page title")
    gallery_parser.set_defaults(func=cmd_gallery)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
