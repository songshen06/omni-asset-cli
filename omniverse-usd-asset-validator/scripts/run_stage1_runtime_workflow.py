#!/usr/bin/env python3
"""Run the fixed Stage 1 runtime physics evidence workflow for one USD asset."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_DOCKER_CONTAINER = "isaac-sim"
DEFAULT_DOCKER_IMAGE = "nvcr.io/nvidia/isaac-sim:5.1.0"
DEFAULT_VIDEO_CAMERAS = ["front", "side", "top", "iso"]


def default_out_dir(asset: Path) -> Path:
    return Path("out") / f"{asset.stem}_stage1_runtime"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Isaac Sim Docker preflight plus the standard Stage 1 top-drop runtime hit test.",
    )
    parser.add_argument("asset", type=Path, help="Path to the USD asset")
    parser.add_argument("--out", type=Path, help="Output directory for workflow and hit-test artifacts")
    parser.add_argument(
        "--template-scene",
        type=Path,
        default=REPO_ROOT / "examples" / "mini_test.usda",
        help="Template scene used by the Stage 1 top-drop test",
    )
    parser.add_argument(
        "--placement-mode",
        choices=["replace-table", "tabletop", "replace-box"],
        default="replace-table",
        help="Stage 1 placement strategy",
    )
    parser.add_argument(
        "--size-policy",
        choices=["preserve", "template-fit"],
        default="preserve",
        help="Whether to preserve the asset's authored size",
    )
    parser.add_argument("--frames", type=int, default=240, help="Number of simulation frames")
    parser.add_argument("--fps", type=float, default=60.0, help="Simulation frames per second")
    parser.add_argument("--asset-rotation-y-deg", type=float, default=0.0)
    parser.add_argument("--asset-rotation-z-deg", type=float, default=0.0)
    parser.add_argument(
        "--runtime-docker-container",
        help=(
            "Running Isaac Sim container name or ID. Defaults to isaac-sim unless "
            "--runtime-docker-image is supplied."
        ),
    )
    parser.add_argument(
        "--runtime-docker-image",
        help=f"Isaac Sim Docker image to launch when no running container is used. Typical: {DEFAULT_DOCKER_IMAGE}",
    )
    parser.add_argument(
        "--no-default-container",
        action="store_true",
        help="Do not default to the isaac-sim running container when no image/container is supplied",
    )
    parser.add_argument(
        "--runtime-docker-preflight",
        choices=["auto", "check", "restart", "skip"],
        default="restart",
        help="Container clean-start policy passed to physics-hit-test",
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
        "--evidence-preset",
        choices=["standard", "contact-only", "custom"],
        default="standard",
        help=(
            "Evidence bundle to collect. standard records PhysX contact evidence plus "
            "front/side/top/iso videos with physics bbox overlays."
        ),
    )
    parser.add_argument("--render-frames", action="store_true", help="Capture rendered PNG evidence")
    parser.add_argument("--render-every-n-frames", type=int)
    parser.add_argument("--render-camera-preset", action="append", default=[])
    parser.add_argument("--render-backend", choices=["replicator", "viewport"], default="replicator")
    parser.add_argument("--render-width", type=int, default=1280)
    parser.add_argument("--render-height", type=int, default=720)
    parser.add_argument("--render-rt-subframes", type=int, default=4)
    parser.add_argument("--render-wait-updates", type=int, default=20)
    parser.add_argument("--render-video", action="store_true")
    parser.add_argument("--render-video-style", choices=["hit-test", "asset-table-drop"], default="hit-test")
    parser.add_argument("--render-video-fps", type=float)
    parser.add_argument("--render-video-crf", type=int, default=23)
    parser.add_argument("--render-physics-bboxes", action="store_true")
    parser.add_argument("--render-physics-bbox-fallback-default-prim", action="store_true")
    parser.add_argument("--render-physics-bbox-width", type=float, default=0.0)
    return parser.parse_args()


def apply_evidence_preset(args: argparse.Namespace) -> None:
    if args.evidence_preset == "standard":
        args.render_frames = True
        args.render_video = True
        args.render_physics_bboxes = True
        if not args.render_camera_preset:
            args.render_camera_preset = list(DEFAULT_VIDEO_CAMERAS)
        if args.render_every_n_frames is None:
            args.render_every_n_frames = 2
    elif args.render_every_n_frames is None:
        args.render_every_n_frames = 1


def effective_runtime(args: argparse.Namespace) -> tuple[str | None, str | None]:
    container = args.runtime_docker_container
    image = args.runtime_docker_image
    if container is None and image is None and not args.no_default_container:
        container = DEFAULT_DOCKER_CONTAINER
    return container, image


def runtime_args(args: argparse.Namespace) -> list[str]:
    container, image = effective_runtime(args)
    command: list[str] = []
    if container:
        command.extend(["--runtime-docker-container", container])
    if image:
        command.extend(["--runtime-docker-image", image])
    command.extend(["--docker-workspace", args.docker_workspace])
    command.extend(["--docker-python", args.docker_python])
    return command


def physics_env_command(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        str(SCRIPTS_DIR / "check_physics_runtime_env.py"),
        *runtime_args(args),
    ]


def docker_access_command() -> list[str]:
    return ["docker", "ps", "--format", "{{.Names}}"]


def hit_test_command(args: argparse.Namespace, out_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "run_physics_hit_test.py"),
        str(args.asset),
        "--template-scene",
        str(args.template_scene),
        "--placement-mode",
        args.placement_mode,
        "--hit-mode",
        "top-drop",
        "--size-policy",
        args.size_policy,
        "--frames",
        str(args.frames),
        "--fps",
        str(args.fps),
        "--out",
        str(out_dir),
        "--runtime-docker-preflight",
        args.runtime_docker_preflight,
        *runtime_args(args),
    ]
    if args.asset_rotation_y_deg:
        command.extend(["--asset-rotation-y-deg", str(args.asset_rotation_y_deg)])
    if args.asset_rotation_z_deg:
        command.extend(["--asset-rotation-z-deg", str(args.asset_rotation_z_deg)])
    if args.render_frames:
        command.append("--render-frames")
    if args.render_every_n_frames is not None:
        command.extend(["--render-every-n-frames", str(args.render_every_n_frames)])
    for item in args.render_camera_preset:
        command.extend(["--render-camera-preset", item])
    command.extend(["--render-backend", args.render_backend])
    command.extend(["--render-width", str(args.render_width)])
    command.extend(["--render-height", str(args.render_height)])
    command.extend(["--render-rt-subframes", str(args.render_rt_subframes)])
    command.extend(["--render-wait-updates", str(args.render_wait_updates)])
    if args.render_video:
        command.append("--render-video")
        command.extend(["--render-video-style", args.render_video_style])
    if args.render_video_fps is not None:
        command.extend(["--render-video-fps", str(args.render_video_fps)])
    command.extend(["--render-video-crf", str(args.render_video_crf)])
    if args.render_physics_bboxes:
        command.append("--render-physics-bboxes")
    if args.render_physics_bbox_fallback_default_prim:
        command.append("--render-physics-bbox-fallback-default-prim")
    if args.render_physics_bbox_width is not None:
        command.extend(["--render-physics-bbox-width", str(args.render_physics_bbox_width)])
    return command


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_capture(command: list[str], stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(command, check=False, stdout=stdout, stderr=stderr)
        return completed.returncode
    except FileNotFoundError as exc:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 127


def encode_hit_test_videos_on_host(args: argparse.Namespace, out_dir: Path) -> list[dict[str, Any]]:
    if not args.render_video:
        return []
    ffmpeg = shutil.which("ffmpeg")
    report_path = out_dir / "workflow_host_video_encode.json"
    if ffmpeg is None:
        payload = [{"error": "host_ffmpeg_not_found"}]
        write_json(report_path, {"videos": payload})
        return payload

    frame_sources: list[tuple[str, Path, str]] = []
    for frames_root, pattern in (
        (out_dir / "render_frames", "frame_*.png"),
        (out_dir / "_replicator_render_product", "rgb_*.png"),
    ):
        if not frames_root.exists():
            continue
        camera_dirs = sorted(path for path in frames_root.iterdir() if path.is_dir())
        if not camera_dirs and any(frames_root.glob(pattern)):
            camera_dirs = [frames_root]
        for camera_dir in camera_dirs:
            if any(camera_dir.glob(pattern)):
                camera_name = camera_dir.name if camera_dir != frames_root else "camera"
                frame_sources.append((camera_name, camera_dir, pattern))

    if not frame_sources:
        payload = [{"error": "render_frames_not_found", "searched": [
            str(out_dir / "render_frames"),
            str(out_dir / "_replicator_render_product"),
        ]}]
        write_json(report_path, {"videos": payload})
        return payload

    video_dir = out_dir / "render_videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_fps = args.render_video_fps or max(float(args.fps) / max(int(args.render_every_n_frames or 1), 1), 1.0)
    outputs: list[dict[str, Any]] = []
    seen_cameras: set[str] = set()
    for camera_name, camera_dir, pattern in frame_sources:
        if camera_name in seen_cameras:
            continue
        seen_cameras.add(camera_name)
        frames = sorted(camera_dir.glob(pattern))
        video_path = video_dir / f"{camera_name}.mp4"
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            f"{video_fps:g}",
            "-pattern_type",
            "glob",
            "-i",
            str(camera_dir / pattern),
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
        item: dict[str, Any] = {
            "camera": camera_name,
            "path": str(video_path),
            "frame_count": len(frames),
            "fps": video_fps,
            "returncode": completed.returncode,
            "encoder": "host_ffmpeg",
        }
        if completed.returncode != 0:
            item["error"] = (completed.stderr or completed.stdout or "")[-1000:]
        outputs.append(item)
    write_json(report_path, {"videos": outputs})
    return outputs


def docker_access_report(args: argparse.Namespace, out_dir: Path, returncode: int) -> dict[str, Any]:
    stdout_path = out_dir / "workflow_docker_ps.stdout.txt"
    stderr_path = out_dir / "workflow_docker_ps.stderr.txt"
    stdout = stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else ""
    stderr = stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else ""
    containers = [line.strip() for line in stdout.splitlines() if line.strip()]
    requested_container = effective_runtime(args)[0]
    reason = None
    recommendation = None
    stderr_lower = stderr.lower()
    if returncode == 127:
        reason = "docker_cli_not_found"
        recommendation = "Install Docker CLI or run this workflow on a host with Docker available."
    elif returncode != 0 and ("permission denied" in stderr_lower or "docker.sock" in stderr_lower):
        reason = "docker_socket_permission_denied"
        recommendation = "Run with Docker daemon access, add the user to the docker group, or execute from an approved privileged context."
    elif returncode != 0:
        reason = "docker_probe_failed"
        recommendation = "Inspect workflow_docker_ps.stderr.txt before rerunning the runtime workflow."
    elif requested_container and requested_container not in containers:
        reason = "requested_container_not_visible"
        recommendation = f"Start or expose the '{requested_container}' Isaac Sim container, or pass --runtime-docker-image."
    else:
        reason = "docker_access_ok"

    return {
        "ready": returncode == 0 and (not requested_container or requested_container in containers),
        "returncode": returncode,
        "reason": reason,
        "requested_container": requested_container,
        "visible_containers": containers,
        "recommendation": recommendation,
        "logs": {
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
        },
    }


def classify_evidence(summary: dict[str, Any] | None, returncode: int) -> tuple[str, str, list[str]]:
    if summary is None:
        return "failed_missing_summary", "none", ["summary.json was not written or could not be parsed."]

    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    notes: list[str] = []
    if checks.get("contact_report_detected") is True and summary.get("contact_evidence_level") == "detected":
        return "passed", "physx_contact_report", notes
    if checks.get("contact_detected_or_inferred") is True:
        notes.append("Contact was inferred from motion; this is weaker than PhysX contact report evidence.")
        return "passed_weak_evidence", "motion_inferred", notes
    if returncode == 0 and summary.get("result") == "passed":
        notes.append("Runtime returned passed, but contact_report_detected was not true.")
        return "passed_weak_evidence", "runtime_pass_without_contact_report", notes
    return "failed_no_contact_evidence", "none", notes


def artifact_paths(out_dir: Path, runtime_report: dict[str, Any] | None) -> dict[str, str]:
    candidates = {
        "summary_json": out_dir / "summary.json",
        "runtime_report_json": out_dir / "runtime_report.json",
        "timeline_csv": out_dir / "timeline.csv",
    }
    artifacts = {name: str(path) for name, path in candidates.items() if path.exists()}
    if runtime_report and runtime_report.get("stage_path"):
        artifacts["generated_stage"] = str(runtime_report["stage_path"])
    render_frames = out_dir / "render_frames"
    if render_frames.exists():
        artifacts["render_frames"] = str(render_frames)
    render_videos = out_dir / "render_videos"
    if render_videos.exists():
        artifacts["render_videos"] = str(render_videos)
    asset_table_drop = out_dir / "asset_table_drop_render"
    if asset_table_drop.exists():
        artifacts["asset_table_drop_render"] = str(asset_table_drop)
    return artifacts


def build_report(
    args: argparse.Namespace,
    out_dir: Path,
    docker_returncode: int,
    preflight_returncode: int,
    hit_returncode: int | None,
    contact_out_dir: Path | None = None,
    contact_returncode: int | None = None,
) -> dict[str, Any]:
    summary = read_json(out_dir / "summary.json")
    runtime_report = read_json(out_dir / "runtime_report.json")
    contact_summary = read_json(contact_out_dir / "summary.json") if contact_out_dir else None
    contact_runtime_report = read_json(contact_out_dir / "runtime_report.json") if contact_out_dir else None
    if preflight_returncode != 0:
        status = "blocked_environment"
        evidence_level = "none"
        notes = ["physics-env preflight failed; runtime hit test was not executed."]
    elif contact_summary is not None:
        status, evidence_level, notes = classify_evidence(contact_summary, int(contact_returncode or 0))
        if hit_returncode not in (0, None):
            notes.append(f"visual physics-hit-test returned {hit_returncode}; inspect render logs if visual artifacts are incomplete.")
    else:
        status, evidence_level, notes = classify_evidence(summary, int(hit_returncode or 0))
        if hit_returncode not in (0, None) and status.startswith("passed"):
            notes.append(f"physics-hit-test returned {hit_returncode}; inspect logs before accepting evidence.")

    return {
        "workflow": "stage1-runtime",
        "status": status,
        "evidence_level": evidence_level,
        "asset": str(args.asset),
        "out_dir": str(out_dir),
        "runtime": {
            "docker_container": effective_runtime(args)[0],
            "docker_image": effective_runtime(args)[1],
            "docker_workspace": args.docker_workspace,
            "docker_python": args.docker_python,
        },
        "docker_access": docker_access_report(args, out_dir, docker_returncode),
        "parameters": {
            "template_scene": str(args.template_scene),
            "placement_mode": args.placement_mode,
            "hit_mode": "top-drop",
            "size_policy": args.size_policy,
            "frames": args.frames,
            "fps": args.fps,
            "evidence_preset": args.evidence_preset,
            "render_frames": args.render_frames,
            "render_video": args.render_video,
            "render_camera_preset": args.render_camera_preset,
            "render_every_n_frames": args.render_every_n_frames,
            "render_physics_bboxes": args.render_physics_bboxes,
        },
        "returncodes": {
            "docker_access": docker_returncode,
            "physics_env": preflight_returncode,
            "contact_physics_hit_test": contact_returncode,
            "physics_hit_test": hit_returncode,
        },
        "artifacts": {
            **artifact_paths(out_dir, runtime_report),
            **(
                {"contact_evidence": str(contact_out_dir)}
                if contact_out_dir and contact_out_dir.exists()
                else {}
            ),
        },
        "logs": {
            "docker_ps_stdout": str(out_dir / "workflow_docker_ps.stdout.txt"),
            "docker_ps_stderr": str(out_dir / "workflow_docker_ps.stderr.txt"),
            "physics_env_stdout": str(out_dir / "workflow_physics_env.stdout.txt"),
            "physics_env_stderr": str(out_dir / "workflow_physics_env.stderr.txt"),
            "contact_physics_hit_test_stdout": str(contact_out_dir / "workflow_physics_hit_test.stdout.txt")
            if contact_out_dir
            else None,
            "contact_physics_hit_test_stderr": str(contact_out_dir / "workflow_physics_hit_test.stderr.txt")
            if contact_out_dir
            else None,
            "physics_hit_test_stdout": str(out_dir / "workflow_physics_hit_test.stdout.txt"),
            "physics_hit_test_stderr": str(out_dir / "workflow_physics_hit_test.stderr.txt"),
            "host_video_encode": str(out_dir / "workflow_host_video_encode.json"),
        },
        "summary": contact_summary or summary,
        "visual_summary": summary if contact_summary is not None else None,
        "runtime_report_excerpt": {
            "stage_path": (contact_runtime_report or runtime_report or {}).get("stage_path"),
            "collider_prim_paths": (contact_runtime_report or runtime_report or {}).get("collider_prim_paths"),
            "box_size": (contact_runtime_report or runtime_report or {}).get("box_size"),
            "asset_bbox_min": (contact_runtime_report or runtime_report or {}).get("asset_bbox_min"),
            "asset_bbox_max": (contact_runtime_report or runtime_report or {}).get("asset_bbox_max"),
        },
        "notes": notes,
    }


def contact_only_args(args: argparse.Namespace) -> argparse.Namespace:
    contact_args = copy.copy(args)
    contact_args.evidence_preset = "contact-only"
    contact_args.render_frames = False
    contact_args.render_video = False
    contact_args.render_physics_bboxes = False
    contact_args.render_camera_preset = []
    contact_args.render_every_n_frames = 1
    return contact_args


def main() -> int:
    args = parse_args()
    apply_evidence_preset(args)
    out_dir = args.out or default_out_dir(args.asset)
    out_dir.mkdir(parents=True, exist_ok=True)

    docker_access = docker_access_command()
    preflight = physics_env_command(args)
    contact_out_dir = out_dir / "contact_evidence" if args.evidence_preset == "standard" else None
    contact_args = contact_only_args(args) if contact_out_dir else None
    contact_hit_test = hit_test_command(contact_args, contact_out_dir) if contact_args and contact_out_dir else None
    hit_test = hit_test_command(args, out_dir)
    write_json(
        out_dir / "workflow_commands.json",
        {
            "docker_access": docker_access,
            "physics_env": preflight,
            "contact_physics_hit_test": contact_hit_test,
            "physics_hit_test": hit_test,
        },
    )

    docker_returncode = run_capture(
        docker_access,
        out_dir / "workflow_docker_ps.stdout.txt",
        out_dir / "workflow_docker_ps.stderr.txt",
    )
    preflight_returncode = run_capture(
        preflight,
        out_dir / "workflow_physics_env.stdout.txt",
        out_dir / "workflow_physics_env.stderr.txt",
    )
    hit_returncode: int | None = None
    contact_returncode: int | None = None
    if preflight_returncode == 0:
        if contact_hit_test and contact_out_dir:
            contact_returncode = run_capture(
                contact_hit_test,
                contact_out_dir / "workflow_physics_hit_test.stdout.txt",
                contact_out_dir / "workflow_physics_hit_test.stderr.txt",
            )
        hit_returncode = run_capture(
            hit_test,
            out_dir / "workflow_physics_hit_test.stdout.txt",
            out_dir / "workflow_physics_hit_test.stderr.txt",
        )
        encode_hit_test_videos_on_host(args, out_dir)
    else:
        if contact_out_dir:
            (contact_out_dir / "workflow_physics_hit_test.stdout.txt").write_text(
                "Skipped because physics-env preflight failed.\n",
                encoding="utf-8",
            )
            (contact_out_dir / "workflow_physics_hit_test.stderr.txt").write_text("", encoding="utf-8")
        (out_dir / "workflow_physics_hit_test.stdout.txt").write_text(
            "Skipped because physics-env preflight failed.\n",
            encoding="utf-8",
        )
        (out_dir / "workflow_physics_hit_test.stderr.txt").write_text("", encoding="utf-8")

    report = build_report(
        args,
        out_dir,
        docker_returncode,
        preflight_returncode,
        hit_returncode,
        contact_out_dir=contact_out_dir,
        contact_returncode=contact_returncode,
    )
    report_path = out_dir / "workflow_report.json"
    write_json(report_path, report)

    print(f"WorkflowReport: {report_path}")
    print(f"Status: {report['status']}")
    print(f"EvidenceLevel: {report['evidence_level']}")
    print(f"OutputDir: {out_dir}")

    if report["status"] == "passed":
        return 0
    if report["status"] == "passed_weak_evidence":
        return 2
    if report["status"] == "blocked_environment":
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
