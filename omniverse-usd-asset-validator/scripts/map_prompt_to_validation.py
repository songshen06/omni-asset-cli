#!/usr/bin/env python3
"""Map natural-language validation requests to run_sync_validation.py arguments."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


RULE_PATTERNS = [
    ("StageMetadataChecker", [r"stage metadata", r"metadata", r"upaxis", r"metersperunit", r"defaultprim"]),
    ("DefaultPrimChecker", [r"defaultprim"]),
    (
        "KindChecker",
        [
            r"kind",
            r"asset structure",
            r"simulation structure",
            r"hierarchy",
            r"component hierarchy",
            r"component structure",
            r"isaac sim structure",
            r"simready structure",
            r"组件语义",
            r"层级结构",
            r"资产结构",
            r"仿真层级",
        ],
    ),
    ("MissingReferenceChecker", [r"missing reference", r"丢失引用", r"引用缺失", r"引用", r"dependency", r"依赖"]),
    ("TextureChecker", [r"texture", r"贴图"]),
    ("ValidateTopologyChecker", [r"topology", r"拓扑"]),
    ("NormalsValidChecker", [r"normals", r"法线"]),
    ("ZeroAreaFaceChecker", [r"zero-area", r"zero area", r"零面积"]),
    ("ManifoldChecker", [r"manifold", r"non-manifold", r"non manifold"]),
    ("IndexedPrimvarChecker", [r"indexed primvar"]),
    ("UnusedPrimvarChecker", [r"unused primvar"]),
    ("ExtentsChecker", [r"extents"]),
    ("SubdivisionSchemeChecker", [r"subdivision"]),
]

CATEGORY_PATTERNS = [
    ("Geometry", [r"geometry", r"mesh", r"几何", r"模型"]),
    ("Material", [r"material", r"材质", r"纹理"]),
    ("Physics", [r"physics", r"物理", r"rigid body", r"collider", r"joint"]),
]

PREDICATE_PATTERNS = [
    ("IsError", [r"only errors", r"只看错误", r"只看 error"]),
    ("IsFailure", [r"only failures", r"只看 failure", r"阻塞性问题"]),
    ("IsWarning", [r"only warnings", r"只看 warning", r"只看警告"]),
]

PROFILE_PATTERNS = [
    (
        "static",
        [
            r"static asset",
            r"static usage",
            r"display asset",
            r"background prop",
            r"静态资产",
            r"展示资产",
            r"背景道具",
            r"场景摆放",
            r"非交互资产",
        ],
    ),
    (
        "collidable",
        [
            r"collidable asset",
            r"collision asset",
            r"collision",
            r"collidable",
            r"碰撞资产",
            r"碰撞体",
            r"碰撞",
            r"障碍物",
            r"物理接触",
        ],
    ),
    (
        "movable",
        [
            r"movable asset",
            r"movable",
            r"grasp",
            r"pick and place",
            r"robot asset",
            r"robot interaction",
            r"可移动资产",
            r"搬运",
            r"抓取",
            r"机器人资产",
            r"机器人交互",
        ],
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map natural language to run_sync_validation.py arguments.",
    )
    parser.add_argument("asset", type=Path, help="Path to the USD asset")
    parser.add_argument("prompt", help="Natural-language validation request")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("/tmp/asset_validation.json"),
        help="Path to the JSON output file",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the generated command instead of only printing it",
    )
    return parser.parse_args()


def contains_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def map_prompt(prompt: str) -> dict[str, list[str] | str | bool]:
    text = prompt.lower()
    rules: list[str] = []
    categories: list[str] = []
    predicate: str | None = None
    profile: str | None = None
    init_rules = False
    variants = False

    for candidate, patterns in PROFILE_PATTERNS:
        if contains_any(text, patterns):
            profile = candidate
            break

    for rule, patterns in RULE_PATTERNS:
        if contains_any(text, patterns) and rule not in rules:
            rules.append(rule)

    for category, patterns in CATEGORY_PATTERNS:
        if contains_any(text, patterns) and category not in categories:
            categories.append(category)

    for candidate, patterns in PREDICATE_PATTERNS:
        if contains_any(text, patterns):
            predicate = candidate
            break

    if contains_any(text, [r"all checks", r"标准校验", r"默认规则", r"default rules"]):
        init_rules = True

    if contains_any(text, [r"variants", r"variant", r"变体"]):
        variants = True

    return {
        "profile": profile,
        "rules": rules,
        "categories": categories,
        "predicate": predicate,
        "init_rules": init_rules,
        "variants": variants,
    }


def build_command(asset: Path, output_json: Path, mapping: dict[str, list[str] | str | bool]) -> list[str]:
    skill_root = Path(__file__).resolve().parents[1]
    script_path = skill_root / "scripts" / "run_sync_validation.py"
    command = [sys.executable, str(script_path), str(asset), "--output-json", str(output_json)]

    if mapping["profile"]:
        command.extend(["--profile", str(mapping["profile"])])
    for rule in mapping["rules"]:
        command.extend(["--rule", rule])
    for category in mapping["categories"]:
        command.extend(["--category", category])
    if mapping["predicate"]:
        command.extend(["--predicate", str(mapping["predicate"])])
    if mapping["init_rules"]:
        command.append("--init-rules")
    if mapping["variants"]:
        command.append("--variants")

    return command


def main() -> int:
    args = parse_args()
    mapping = map_prompt(args.prompt)
    command = build_command(args.asset, args.output_json, mapping)

    payload = {
        "asset": str(args.asset),
        "prompt": args.prompt,
        "mapping": mapping,
        "command": command,
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if not args.execute:
        return 0

    completed = subprocess.run(command, check=False, text=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
