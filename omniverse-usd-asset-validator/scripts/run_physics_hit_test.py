#!/usr/bin/env python3
"""Run a minimal runtime physics harness with a dynamic box hitting a static asset."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from runtime_physics_harness import (
    RuntimeConfig,
    _path_in_docker,
    default_out_dir,
    execute_hit_test_entry,
    preflight_runtime_docker_container,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal runtime physics hit test against a USD asset.",
    )
    parser.add_argument("asset", type=Path, help="Path to the input USD asset")
    parser.add_argument(
        "--template-scene",
        type=Path,
        help="Optional authored USD scene template with /World/TestAssetSlot and /World/boxActor",
    )
    parser.add_argument(
        "--replace-prim",
        default="/World/roomScene/colliders/table",
        help=(
            "Template prim path to replace with the target asset. "
            "Only used with --template-scene; pass an empty value to use /World/TestAssetSlot instead."
        ),
    )
    parser.add_argument(
        "--placement-mode",
        choices=["auto", "replace-table", "tabletop", "replace-box"],
        default="auto",
        help=(
            "Template placement strategy. Use replace-table for furniture, tabletop for decor props, "
            "or replace-box to drop the input asset as /World/boxActor. "
            "Auto keeps the legacy replace-table default when --replace-prim is set."
        ),
    )
    parser.add_argument(
        "--hit-mode",
        choices=["side-hit", "top-drop"],
        default="side-hit",
        help="How to drive the dynamic box. Use top-drop for Stage 1 furniture/prop checks.",
    )
    parser.add_argument(
        "--size-policy",
        choices=["template-fit", "preserve"],
        default="template-fit",
        help="Whether template mode scales to the replaced prim footprint or preserves the asset's real size.",
    )
    parser.add_argument(
        "--asset-rotation-y-deg",
        type=float,
        default=0.0,
        help="Initial local Y-axis rotation applied to the referenced asset before running the test.",
    )
    parser.add_argument(
        "--asset-rotation-z-deg",
        type=float,
        default=0.0,
        help="Initial local Z-axis rotation applied to the referenced asset before running the test.",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=240,
        help="Number of frames to simulate",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=60.0,
        help="Simulation frames per second",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Output directory for summary.json, runtime_report.json, timeline.csv, and the authored stage",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Disable headless mode when launching the runtime app",
    )
    parser.add_argument(
        "--runtime-docker-image",
        help="Isaac Sim Docker image, such as nvcr.io/nvidia/isaac-sim:5.1.0",
    )
    parser.add_argument(
        "--runtime-docker-container",
        help="Optional running Isaac Sim container name or ID to exec into",
    )
    parser.add_argument(
        "--runtime-docker-preflight",
        choices=["auto", "check", "restart", "skip"],
        default="restart",
        help=(
            "Container clean-start policy before docker exec. restart always restarts; auto restarts only when "
            "stale Isaac/Kit processes are found; check blocks on stale processes; skip disables it."
        ),
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
        "--render-frames",
        action="store_true",
        help="Capture headless viewport PNG frames during simulation into OUT/render_frames",
    )
    parser.add_argument(
        "--render-every-n-frames",
        type=int,
        default=1,
        help="Capture every Nth simulation frame when --render-frames is enabled",
    )
    parser.add_argument(
        "--render-warmup-updates",
        type=int,
        default=2,
        help="Extra app updates after each capture request so the PNG writer can flush",
    )
    parser.add_argument(
        "--render-camera-preset",
        action="append",
        default=[],
        help=(
            "Camera preset to capture when --render-frames or --render-video is enabled. "
            "Repeat or pass comma-separated values. Choices: active, front, back, left, right, side, top, iso."
        ),
    )
    parser.add_argument(
        "--render-backend",
        choices=["replicator", "viewport"],
        default="replicator",
        help="Frame capture backend. Replicator matches the standalone video render script more closely.",
    )
    parser.add_argument("--render-width", type=int, default=1280, help="Rendered frame width for Replicator capture")
    parser.add_argument("--render-height", type=int, default=720, help="Rendered frame height for Replicator capture")
    parser.add_argument("--render-rt-subframes", type=int, default=4, help="Replicator subframes per captured frame")
    parser.add_argument("--render-wait-updates", type=int, default=20, help="App updates to wait for Replicator PNG writes")
    parser.add_argument(
        "--render-video",
        action="store_true",
        help="Encode captured render frames into one mp4 per camera under OUT/render_videos",
    )
    parser.add_argument(
        "--render-video-style",
        choices=["hit-test", "asset-table-drop"],
        default="hit-test",
        help=(
            "Video renderer style. asset-table-drop delegates to render_asset_table_drop.py "
            "so output matches the standalone validated renderer."
        ),
    )
    parser.add_argument(
        "--render-video-fps",
        type=float,
        help="Frame rate for encoded mp4 output; defaults to simulation fps divided by render-every-n-frames",
    )
    parser.add_argument(
        "--render-video-crf",
        type=int,
        default=23,
        help="libx264 CRF value used when --render-video is enabled",
    )
    parser.add_argument(
        "--render-material-mode",
        action="append",
        default=[],
        help="Material mode for asset-table-drop videos. Repeat or pass comma-separated values. Choices: all, material, transparent.",
    )
    parser.add_argument(
        "--render-camera-distance-scale",
        type=float,
        default=None,
        help="Camera distance scale forwarded to asset-table-drop video rendering.",
    )
    parser.add_argument(
        "--render-camera-focal-length",
        type=float,
        default=None,
        help="Camera focal length forwarded to asset-table-drop video rendering.",
    )
    parser.add_argument(
        "--render-camera-elevation-deg",
        type=float,
        default=None,
        help="Camera elevation in degrees forwarded to asset-table-drop video rendering.",
    )
    parser.add_argument(
        "--render-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Hard timeout for asset-table-drop video rendering. "
            "0 chooses a conservative timeout from frame and camera counts."
        ),
    )
    parser.add_argument(
        "--render-physics-bboxes",
        action="store_true",
        help="Draw temporary session-layer bbox curves for asset collider prims during rendered frame capture",
    )
    parser.add_argument(
        "--render-physics-bbox-fallback-default-prim",
        action="store_true",
        help="When no collider paths are available, draw the asset prim bbox for capture debugging only",
    )
    parser.add_argument(
        "--render-physics-bbox-width",
        type=float,
        default=0.0,
        help="BBox line width in stage units; 0 chooses an automatic width",
    )
    parser.add_argument(
        "--external-runtime-child",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _asset_table_drop_render_command(args: argparse.Namespace, out_dir: Path) -> list[str]:
    script = Path(__file__).resolve().parent / "render_asset_table_drop.py"
    render_out = out_dir / "asset_table_drop_render"
    command_args = [
        str(script),
        str(args.asset),
        "--template-scene",
        str(args.template_scene or Path("examples/mini_test.usda")),
        "--out",
        str(render_out),
        "--frames",
        str(args.frames),
        "--fps",
        str(args.fps),
        "--width",
        str(args.render_width),
        "--height",
        str(args.render_height),
        "--render-every-n-frames",
        str(args.render_every_n_frames),
        "--render-rt-subframes",
        str(args.render_rt_subframes),
        "--render-wait-updates",
        str(args.render_wait_updates),
        "--physics-driven",
    ]
    if args.asset_rotation_y_deg:
        command_args.extend(["--asset-rotation-y-deg", str(args.asset_rotation_y_deg)])
    if args.asset_rotation_z_deg:
        command_args.extend(["--asset-rotation-z-deg", str(args.asset_rotation_z_deg)])
    if args.render_video:
        command_args.append("--render-video")
        if args.render_video_fps is not None:
            command_args.extend(["--render-video-fps", str(args.render_video_fps)])
        command_args.extend(["--render-video-crf", str(args.render_video_crf)])
    for item in args.render_camera_preset:
        command_args.extend(["--camera-preset", item])
    for item in args.render_material_mode:
        command_args.extend(["--render-material-mode", item])
    if args.render_camera_distance_scale is not None:
        command_args.extend(["--camera-distance-scale", str(args.render_camera_distance_scale)])
    if args.render_camera_focal_length is not None:
        command_args.extend(["--camera-focal-length", str(args.render_camera_focal_length)])
    if args.render_camera_elevation_deg is not None:
        command_args.extend(["--camera-elevation-deg", str(args.render_camera_elevation_deg)])

    config = RuntimeConfig(
        asset=args.asset,
        template_scene=args.template_scene,
        out_dir=out_dir,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        runtime_docker_preflight=args.runtime_docker_preflight,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
    )
    if args.runtime_docker_container:
        docker_args = [
            _path_in_docker(Path(value), config) if index in {0, 1, 3, 5} else value
            for index, value in enumerate(command_args)
        ]
        return [
            "docker",
            "exec",
            "-w",
            args.docker_workspace,
            args.runtime_docker_container,
            args.docker_python,
            *docker_args,
        ]
    if args.runtime_docker_image:
        docker_args = [
            _path_in_docker(Path(value), config) if index in {0, 1, 3, 5} else value
            for index, value in enumerate(command_args)
        ]
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
            "-v",
            f"{Path(__file__).resolve().parents[2]}:{args.docker_workspace}",
            "-w",
            args.docker_workspace,
            "--entrypoint",
            args.docker_python,
            args.runtime_docker_image,
            *docker_args,
        ]
    return [sys.executable, *command_args]


def run_asset_table_drop_renderer(args: argparse.Namespace, out_dir: Path) -> int:
    preflight_config = RuntimeConfig(
        asset=args.asset,
        template_scene=args.template_scene,
        out_dir=out_dir,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        runtime_docker_preflight=args.runtime_docker_preflight,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
    )
    preflight = preflight_runtime_docker_container(preflight_config)
    if preflight.get("action") == "blocked_residual_processes" or preflight.get("ready") is False:
        preflight_path = out_dir / "asset_table_drop_render_preflight.json"
        preflight_path.parent.mkdir(parents=True, exist_ok=True)
        preflight_path.write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
        print(f"AssetTableDropRenderPreflightBlocked: {preflight_path}")
        return 2

    command = _asset_table_drop_render_command(args, out_dir)
    timeout_seconds = _asset_table_drop_render_timeout_seconds(args)
    print(f"AssetTableDropRenderStart: timeout_seconds={timeout_seconds:g}")
    try:
        completed = subprocess.run(command, check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_asset_table_drop_renderer(args)
        timeout_report = out_dir / "asset_table_drop_render" / "render_timeout_report.json"
        timeout_report.parent.mkdir(parents=True, exist_ok=True)
        timeout_report.write_text(
            json.dumps(
                {
                    "error": "asset_table_drop_render_timeout",
                    "timeout_seconds": timeout_seconds,
                    "command": command,
                    "out": str(out_dir / "asset_table_drop_render"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"AssetTableDropRenderTimeout: {timeout_report}")
        return 124
    render_summary = out_dir / "asset_table_drop_render" / "cup_table_drop_summary.json"
    if render_summary.exists():
        _make_asset_table_drop_render_host_writable(args, out_dir)
        _maybe_encode_asset_table_drop_video_on_host(args, render_summary)
        print(f"AssetTableDropRenderSummary: {render_summary}")
        video_dir = out_dir / "asset_table_drop_render" / "render_videos"
        if video_dir.exists():
            print(f"AssetTableDropRenderVideos: {video_dir}")
    return completed.returncode


def _asset_table_drop_render_timeout_seconds(args: argparse.Namespace) -> float:
    if float(args.render_timeout_seconds or 0.0) > 0.0:
        return float(args.render_timeout_seconds)
    camera_count = len(args.render_camera_preset) if args.render_camera_preset else 1
    material_count = len(args.render_material_mode) if args.render_material_mode else 1
    if any(str(item).lower() == "all" for item in args.render_camera_preset):
        camera_count = 8
    if any(str(item).lower() == "all" for item in args.render_material_mode):
        material_count = 2
    captured_frames = max(1, math.ceil(float(args.frames) / max(int(args.render_every_n_frames), 1)))
    return max(300.0, 180.0 + captured_frames * max(camera_count, 1) * max(material_count, 1) * 5.0)


def _terminate_asset_table_drop_renderer(args: argparse.Namespace) -> None:
    if not args.runtime_docker_container:
        return
    subprocess.run(
        [
            "docker",
            "exec",
            args.runtime_docker_container,
            "pkill",
            "-f",
            "render_asset_table_drop.py",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _make_asset_table_drop_render_host_writable(args: argparse.Namespace, out_dir: Path) -> None:
    if not args.runtime_docker_container:
        return
    config = RuntimeConfig(
        asset=args.asset,
        template_scene=args.template_scene,
        out_dir=out_dir,
        runtime_docker_container=args.runtime_docker_container,
        runtime_docker_preflight=args.runtime_docker_preflight,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
    )
    docker_render_out = _path_in_docker(out_dir / "asset_table_drop_render", config)
    subprocess.run(
        [
            "docker",
            "exec",
            "-w",
            args.docker_workspace,
            args.runtime_docker_container,
            "chmod",
            "-R",
            "a+rwX",
            docker_render_out,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _maybe_encode_asset_table_drop_video_on_host(args: argparse.Namespace, render_summary: Path) -> None:
    if not args.render_video:
        return
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return
    try:
        payload = json.loads(render_summary.read_text(encoding="utf-8"))
    except Exception:
        return
    videos = payload.get("render_videos") if isinstance(payload.get("render_videos"), list) else []
    if any(isinstance(item, dict) and item.get("path") for item in videos):
        return

    video_fps = args.render_video_fps or max(float(args.fps) / max(args.render_every_n_frames, 1), 1.0)

    def host_path(value: object) -> Path:
        path = Path(str(value))
        workspace = str(args.docker_workspace).rstrip("/")
        path_text = str(path)
        if workspace and path_text.startswith(workspace + "/"):
            return Path(__file__).resolve().parents[2] / path_text[len(workspace) + 1 :]
        return path

    def encode_sequence(frames_dir: Path, video_path: Path, camera: str | None = None, mode: str | None = None) -> dict[str, object] | None:
        source_frames = sorted(frames_dir.glob("frame_*.png"))
        if not source_frames:
            return None
        sequence_root = video_path.parent.parent / "_host_video_sequence"
        sequence_dir = sequence_root / (mode or "default") / (camera or "camera")
        sequence_dir.mkdir(parents=True, exist_ok=True)
        for old_file in sequence_dir.glob("frame_*.png"):
            old_file.unlink()
        copied_count = 0
        for index, source in enumerate(source_frames):
            target = sequence_dir / f"frame_{index:04d}.png"
            shutil.copy2(source, target)
            copied_count += 1
        if copied_count == 0:
            return None
        video_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            f"{video_fps:g}",
            "-i",
            str(sequence_dir / "frame_%04d.png"),
            "-vf",
            "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v",
            "libx264",
            "-crf",
            str(args.render_video_crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0 or not video_path.exists():
            return {
                "error": f"host ffmpeg failed returncode={completed.returncode}: {completed.stderr[-500:]}",
                "encoder": "host_ffmpeg",
                "camera": camera,
                "mode": mode,
            }
        item: dict[str, object] = {
            "path": str(video_path),
            "fps": video_fps,
            "frame_count": copied_count,
            "codec": "libx264",
            "encoder": "host_ffmpeg",
        }
        if camera:
            item["camera"] = camera
        if mode:
            item["mode"] = mode
        return item

    def encode_render_out(render_out: Path, mode: str | None = None) -> list[dict[str, object]]:
        frames_dir = render_out / "render_frames"
        video_dir = render_out / "render_videos"
        outputs: list[dict[str, object]] = []
        legacy = encode_sequence(frames_dir, video_dir / "drop_camera.mp4", "drop_camera", mode)
        if legacy is not None:
            outputs.append(legacy)
            return outputs
        for camera_dir in sorted(path for path in frames_dir.iterdir() if path.is_dir()) if frames_dir.exists() else []:
            encoded = encode_sequence(camera_dir, video_dir / f"{camera_dir.name}.mp4", camera_dir.name, mode)
            if encoded is not None:
                outputs.append(encoded)
        return outputs

    variants = payload.get("render_variants") if isinstance(payload.get("render_variants"), list) else []
    if variants:
        root_videos: list[dict[str, object]] = []
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            mode = str(variant.get("mode") or "")
            variant_summary = host_path(variant.get("summary") or "")
            render_out = host_path(variant.get("out") or variant_summary.parent)
            variant_videos = encode_render_out(render_out, mode=mode)
            if variant_videos:
                variant["render_videos"] = variant_videos
                root_videos.extend(variant_videos)
                if variant_summary.exists():
                    try:
                        variant_payload = json.loads(variant_summary.read_text(encoding="utf-8"))
                        variant_payload["render_videos"] = variant_videos
                        variant_summary.write_text(json.dumps(variant_payload, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
        payload["render_videos"] = root_videos
    else:
        payload["render_videos"] = encode_render_out(render_summary.parent)
    render_summary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(summary: dict[str, object], out_dir: Path) -> None:
    print(f"Status: {summary['result']}")
    print(f"Asset: {summary['asset']}")
    print(f"TestType: {summary['test_type']}")
    print(f"Frames: {summary['frames']}")
    print(f"OutputDir: {out_dir}")
    print(f"Checks: {summary['checks']}")
    runtime_report = out_dir / "runtime_report.json"
    if runtime_report.exists():
        print(f"RuntimeReport: {runtime_report}")
    render_dir = out_dir / "render_frames"
    if render_dir.exists():
        print(f"RenderFrames: {render_dir}")
    video_dir = out_dir / "render_videos"
    if video_dir.exists():
        print(f"RenderVideos: {video_dir}")
    if summary["notes"]:
        print("Notes:")
        for note in summary["notes"]:
            print(f"- {note}")


def main() -> int:
    args = parse_args()
    out_dir = args.out or default_out_dir(args.asset)
    hit_test_render_video = args.render_video and args.render_video_style == "hit-test"
    config = RuntimeConfig(
        asset=args.asset,
        template_scene=args.template_scene,
        replace_prim=args.replace_prim or None,
        placement_mode=args.placement_mode,
        hit_mode=args.hit_mode,
        size_policy=args.size_policy,
        asset_rotation_y_deg=args.asset_rotation_y_deg,
        asset_rotation_z_deg=args.asset_rotation_z_deg,
        out_dir=out_dir,
        frames=args.frames,
        fps=args.fps,
        headless=not args.no_headless,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        runtime_docker_preflight=args.runtime_docker_preflight,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
        render_frames=(args.render_frames or args.render_video) and args.render_video_style == "hit-test",
        render_every_n_frames=args.render_every_n_frames,
        render_warmup_updates=args.render_warmup_updates,
        render_camera_presets=args.render_camera_preset if args.render_video_style == "hit-test" else [],
        render_backend=args.render_backend,
        render_width=args.render_width,
        render_height=args.render_height,
        render_rt_subframes=args.render_rt_subframes,
        render_wait_updates=args.render_wait_updates,
        render_video=hit_test_render_video,
        render_video_fps=args.render_video_fps,
        render_video_crf=args.render_video_crf,
        render_physics_bboxes=args.render_physics_bboxes,
        render_physics_bbox_fallback_default_prim=args.render_physics_bbox_fallback_default_prim,
        render_physics_bbox_width=args.render_physics_bbox_width,
    )
    summary, code = execute_hit_test_entry(
        config,
        script_path=Path(__file__).resolve(),
        allow_external_runtime=not args.external_runtime_child,
    )
    if args.render_video_style == "asset-table-drop" and (args.render_frames or args.render_video):
        render_code = run_asset_table_drop_renderer(args, out_dir)
        if render_code != 0 and code == 0:
            code = render_code
    print_summary(summary, out_dir)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
