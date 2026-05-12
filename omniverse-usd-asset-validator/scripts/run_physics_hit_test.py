#!/usr/bin/env python3
"""Run a minimal runtime physics harness with a dynamic box hitting a static asset."""

from __future__ import annotations

import argparse
from pathlib import Path

from runtime_physics_harness import RuntimeConfig, default_out_dir, execute_hit_test_entry


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
        choices=["auto", "replace-table", "tabletop"],
        default="auto",
        help=(
            "Template placement strategy. Use replace-table for furniture and tabletop for decor props. "
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
        "--external-runtime-child",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def print_summary(summary: dict[str, object], out_dir: Path) -> None:
    print(f"Status: {summary['result']}")
    print(f"Asset: {summary['asset']}")
    print(f"TestType: {summary['test_type']}")
    print(f"Frames: {summary['frames']}")
    print(f"OutputDir: {out_dir}")
    print(f"Checks: {summary['checks']}")
    if summary["notes"]:
        print("Notes:")
        for note in summary["notes"]:
            print(f"- {note}")


def main() -> int:
    args = parse_args()
    out_dir = args.out or default_out_dir(args.asset)
    config = RuntimeConfig(
        asset=args.asset,
        template_scene=args.template_scene,
        replace_prim=args.replace_prim or None,
        placement_mode=args.placement_mode,
        hit_mode=args.hit_mode,
        size_policy=args.size_policy,
        out_dir=out_dir,
        frames=args.frames,
        fps=args.fps,
        headless=not args.no_headless,
        runtime_docker_image=args.runtime_docker_image,
        runtime_docker_container=args.runtime_docker_container,
        docker_workspace=args.docker_workspace,
        docker_python=args.docker_python,
        render_frames=args.render_frames,
        render_every_n_frames=args.render_every_n_frames,
        render_warmup_updates=args.render_warmup_updates,
    )
    summary, code = execute_hit_test_entry(
        config,
        script_path=Path(__file__).resolve(),
        allow_external_runtime=not args.external_runtime_child,
    )
    print_summary(summary, out_dir)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
