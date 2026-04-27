#!/usr/bin/env python3
"""Run omniverse asset validation through the synchronous Python API."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

RULE_EXPLANATIONS = {
    "StageMetadataChecker": {
        "what": "检查 stage 级别的基础元数据是否完整，例如 upAxis、metersPerUnit 等关键字段。",
        "why": "这些元数据决定坐标系方向和单位尺度，是很多工具正确解释资产的基础。",
        "fix": "在 stage 根层补齐 upAxis、metersPerUnit 等必需元数据，再重新导出或保存资产。",
    },
    "KindChecker": {
        "what": "检查 USD 模型层级中的 kind 标记是否合理，例如 assembly、group、component、subcomponent 的父子关系是否符合规范。",
        "why": "kind 用于表达装配层级语义。若 component 挂在不合适的父节点下，下游工具会难以正确识别完整资产、分组和零件关系。",
        "fix": "给父节点补充合适的 kind，或移除/调整子节点不合适的 kind 标记，必要时重构模型树层级。",
    },
    "UsdDanglingMaterialBinding": {
        "what": "检查 prim 的材质绑定是否指向真实存在的材质 prim。",
        "why": "悬空材质绑定会导致渲染结果错误或材质丢失。",
        "fix": "修正材质绑定路径，或补齐被引用的材质 prim。",
    },
    "UsdMaterialBindingApi": {
        "what": "检查存在材质绑定的 prim 是否正确应用了 MaterialBindingApi。",
        "why": "没有正确应用 API 的绑定在不同工具链里可能表现不一致。",
        "fix": "对绑定材质的 prim 正确应用 MaterialBindingAPI，再重新导出或清理资产。",
    },
    "MaterialPathChecker": {
        "what": "检查材质或 Shader 里引用的外部路径是否存在。",
        "why": "材质依赖路径失效会直接导致 shader 或材质不可用。",
        "fix": "修正路径、补齐依赖文件，或改成可解析的相对/绝对路径。",
    },
    "MissingReferenceChecker": {
        "what": "检查外部引用、payload、依赖文件是否可以正常解析。",
        "why": "缺失依赖会让场景不完整，也会放大后续材质和结构问题。",
        "fix": "先修复引用缺失，再做其他规则清理。",
    },
    "ManifoldChecker": {
        "what": "检查 mesh 是否存在 non-manifold 顶点或边。",
        "why": "non-manifold 几何会影响布尔运算、物理、细分和许多下游处理。",
        "fix": "在 DCC 或网格处理工具中修复网格连通性，清理异常边界和重复结构。",
    },
    "WeldChecker": {
        "what": "检查 mesh 中是否存在可焊接的共点。",
        "why": "重复点会增加数据冗余，也可能导致法线和拓扑质量问题。",
        "fix": "执行点焊接或顶点合并，减少重复几何。",
    },
    "NormalsValidChecker": {
        "what": "检查法线是否有效，例如是否为零向量、是否为单位长度。",
        "why": "异常法线会导致渲染、光照和表面方向判断错误。",
        "fix": "重新计算法线，或修复异常几何后再导出法线。",
    },
    "ZeroAreaFaceChecker": {
        "what": "检查 mesh 是否存在零面积面。",
        "why": "零面积面通常意味着脏几何，会影响拓扑质量和性能。",
        "fix": "删除退化面或重新清理网格。",
    },
    "ValidateTopologyChecker": {
        "what": "检查 mesh 拓扑是否合法。",
        "why": "拓扑问题会影响几何处理、渲染与导入稳定性。",
        "fix": "修复面、边、顶点关系，再重新导出模型。",
    },
    "UnusedMeshTopologyChecker": {
        "what": "检查是否存在未被有效使用的拓扑数据。",
        "why": "无效或冗余拓扑会降低资产质量并增加处理复杂度。",
        "fix": "清理未使用的面索引或冗余拓扑数据。",
    },
    "IndexedPrimvarChecker": {
        "what": "检查 indexed primvar 数据是否匹配几何拓扑。",
        "why": "primvar 索引不匹配会导致 UV、颜色或其他属性读取错误。",
        "fix": "重建 primvar 索引，保证与 mesh 拓扑一致。",
    },
    "DefaultPrimChecker": {
        "what": "检查 defaultPrim 及其与场景其他顶层 prim 的关系是否合理。",
        "why": "defaultPrim 是很多工具识别资产主入口的重要依据。",
        "fix": "整理顶层结构，确保默认 prim 语义清晰且层级合理。",
    },
    "LayerSpecChecker": {
        "what": "检查 layer 中属性定义和写入值的类型是否一致。",
        "why": "类型不匹配说明 layer authoring 不干净，可能引发兼容性问题。",
        "fix": "修正属性类型或清理错误写入的值。",
    },
}

RULE_GROUPS = {
    "结构问题": {
        "rules": {"KindChecker", "DefaultPrimChecker", "LayerSpecChecker", "StageMetadataChecker"},
        "meaning": "这类问题说明 USD 层级、kind、defaultPrim 或 layer authoring 方式不够规范。",
    },
    "材质问题": {
        "rules": {"UsdDanglingMaterialBinding", "UsdMaterialBindingApi", "MaterialPathChecker"},
        "meaning": "这类问题说明材质绑定链路不完整、材质路径失效或材质 API 使用不规范。",
    },
    "依赖问题": {
        "rules": {"MissingReferenceChecker"},
        "meaning": "这类问题说明外部引用、shader、payload 或依赖文件无法解析。",
    },
    "Mesh问题": {
        "rules": {
            "ManifoldChecker",
            "WeldChecker",
            "NormalsValidChecker",
            "ZeroAreaFaceChecker",
            "ValidateTopologyChecker",
            "UnusedMeshTopologyChecker",
            "IndexedPrimvarChecker",
            "UnusedPrimvarChecker",
            "ExtentsChecker",
            "SubdivisionSchemeChecker",
        },
        "meaning": "这类问题说明几何拓扑、法线、面质量或 primvar 数据存在缺陷。",
    },
}

HIGH_IMPACT_RULES = {
    "KindChecker",
    "DefaultPrimChecker",
    "MissingReferenceChecker",
    "MaterialPathChecker",
    "UsdDanglingMaterialBinding",
    "UsdMaterialBindingApi",
    "LayerSpecChecker",
    "StageMetadataChecker",
    "ManifoldChecker",
    "ValidateTopologyChecker",
}

MEDIUM_IMPACT_RULES = {
    "ZeroAreaFaceChecker",
    "NormalsValidChecker",
    "UnusedMeshTopologyChecker",
    "WeldChecker",
}

LOW_IMPACT_RULES = {
    "IndexedPrimvarChecker",
}

PROFILE_PRESETS = {
    "stage1-furniture": {
        "label": "Stage 1 家具/摆件",
        "description": "适用于静态家具、摆件、装饰道具等第一阶段 SimReady 资产检查。",
        "rules": [
            "StageMetadataChecker",
            "DefaultPrimChecker",
            "MissingReferenceChecker",
            "MaterialPathChecker",
            "UsdDanglingMaterialBinding",
            "UsdMaterialBindingApi",
            "ValidateTopologyChecker",
            "ManifoldChecker",
            "ZeroAreaFaceChecker",
            "NormalsValidChecker",
            "WeldChecker",
            "ExtentsChecker",
        ],
        "reasons": [
            "Stage 1 目标是静态家具和摆件，优先确认资产入口、引用、材质链路和 mesh 质量。",
            "collider 推荐与 authoring 由 usd-simready-inspector 的静态家具链路承接，本 profile 先给出交付前校验结果。",
        ],
    },
    "static": {
        "label": "静态资产",
        "description": "适用于展示、场景摆放、背景道具和非交互资产。",
        "rules": [
            "StageMetadataChecker",
            "DefaultPrimChecker",
            "MissingReferenceChecker",
            "MaterialPathChecker",
            "UsdDanglingMaterialBinding",
            "UsdMaterialBindingApi",
        ],
        "reasons": [
            "静态资产最先暴露的是入口定义、引用完整性和材质链路问题。",
            "即使 mesh 还可预览，缺失引用或材质失效也会直接影响交付质量。",
        ],
    },
    "collidable": {
        "label": "可碰撞资产",
        "description": "适用于碰撞体生成、障碍物和物理接触检测。",
        "rules": [
            "MissingReferenceChecker",
            "ValidateTopologyChecker",
            "ManifoldChecker",
            "ZeroAreaFaceChecker",
            "NormalsValidChecker",
            "WeldChecker",
            "ExtentsChecker",
        ],
        "reasons": [
            "碰撞相关资产最怕 non-manifold、拓扑脏、零面积面和法线异常。",
            "材质不完整不一定阻断碰撞，但 mesh 质量差会显著影响物理稳定性。",
        ],
    },
    "movable": {
        "label": "可移动资产",
        "description": "适用于搬运、抓取、机器人交互和可配置物理行为的资产。",
        "rules": [
            "KindChecker",
            "DefaultPrimChecker",
            "StageMetadataChecker",
            "MissingReferenceChecker",
            "ValidateTopologyChecker",
            "ManifoldChecker",
            "NormalsValidChecker",
        ],
        "reasons": [
            "可移动资产不仅要能显示，还要结构语义清晰、层级稳定、几何质量可靠。",
            "对 Isaac Sim、SimReady 和机器人场景，KindChecker 的优先级会明显提高。",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synchronous omniverse asset validation and emit JSON plus a readable summary.",
    )
    parser.add_argument("asset", type=Path, help="Path to a USD asset")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("/tmp/omniverse_asset_validation_sync.json"),
        help="Path to the JSON output file",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        help="Path to the Markdown report. Defaults to the JSON path with a .md suffix.",
    )
    parser.add_argument(
        "--pxr-ar-default-search-path",
        action="append",
        default=[],
        help="Additional resolver search path entries to append to PXR_AR_DEFAULT_SEARCH_PATH.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_PRESETS.keys()),
        help="Apply a preset rule set for a target asset scenario.",
    )
    parser.add_argument("--rule", action="append", default=[], help="Specific rule to enable")
    parser.add_argument("--category", action="append", default=[], help="Specific category to enable")
    parser.add_argument("--predicate", choices=["Any", "IsError", "IsFailure", "IsWarning", "HasRootLayer"])
    parser.add_argument("--init-rules", action="store_true", help="Enable default rule initialization")
    parser.add_argument("--variants", action="store_true", help="Enable variant processing")
    return parser.parse_args()


def normalize_search_paths(raw_values: list[str]) -> list[str]:
    paths: list[str] = []
    for raw_value in raw_values:
        for item in raw_value.split(os.pathsep):
            candidate = item.strip()
            if candidate and candidate not in paths:
                paths.append(candidate)
    return paths


def configure_search_paths(args: argparse.Namespace) -> list[str]:
    existing_paths = normalize_search_paths([os.environ.get("PXR_AR_DEFAULT_SEARCH_PATH", "")])
    requested_paths = normalize_search_paths(args.pxr_ar_default_search_path)
    combined_paths = existing_paths.copy()

    for path in requested_paths:
        if path not in combined_paths:
            combined_paths.append(path)

    if combined_paths:
        os.environ["PXR_AR_DEFAULT_SEARCH_PATH"] = os.pathsep.join(combined_paths)

    return combined_paths


def get_effective_rules(args: argparse.Namespace) -> list[str]:
    effective_rules: list[str] = []

    if args.profile:
        effective_rules.extend(PROFILE_PRESETS[args.profile]["rules"])

    for rule_name in args.rule:
        if rule_name not in effective_rules:
            effective_rules.append(rule_name)

    return effective_rules


def should_enable_default_rules(args: argparse.Namespace) -> bool:
    return args.init_rules or not (args.profile or args.rule or args.category)


def build_engine(args: argparse.Namespace) -> Any:
    from omni.asset_validator import CategoryRuleRegistry, ValidationEngine

    engine = ValidationEngine(init_rules=should_enable_default_rules(args), variants=args.variants)
    registry = CategoryRuleRegistry()

    for rule_name in get_effective_rules(args):
        rule = registry.find_rule(rule_name)
        if rule is None:
            raise ValueError(f"Unknown rule: {rule_name}")
        engine.enable_rule(rule)

    for category in args.category:
        for rule in registry.get_rules(category):
            engine.enable_rule(rule)

    return engine


def issue_to_dict(issue: Any) -> dict[str, Any]:
    at = issue.at
    if isinstance(at, list):
        at_value = [item.as_str() for item in at]
    elif at is not None:
        at_value = at.as_str()
    else:
        at_value = None

    requirement = issue.requirement
    if requirement is not None:
        requirement_value = {
            "code": requirement.code,
            "version": requirement.version,
        }
    else:
        requirement_value = None

    rule = issue.rule
    return {
        "message": issue.message,
        "severity": issue.severity.name if issue.severity else None,
        "rule": rule.__name__ if rule else None,
        "asset": str(issue.asset) if issue.asset is not None else None,
        "at": at_value,
        "suggestion": str(issue.suggestion) if issue.suggestion is not None else None,
        "requirement": requirement_value,
        "code": issue.code,
        "tags": list(issue.tags) if issue.tags else [],
    }


def build_payload(
    args: argparse.Namespace,
    elapsed_seconds: float,
    issues: list[dict[str, Any]],
    search_paths: list[str],
) -> dict[str, Any]:
    effective_rules = get_effective_rules(args)
    severity_counts = Counter(issue["severity"] or "UNKNOWN" for issue in issues)
    rule_counts = Counter(issue["rule"] for issue in issues if issue["rule"])

    if severity_counts.get("ERROR", 0) > 0:
        status = "failed"
    elif severity_counts.get("FAILURE", 0) > 0:
        status = "failed"
    elif severity_counts.get("WARNING", 0) > 0:
        status = "warning"
    else:
        status = "passed"

    return {
        "status": status,
        "validation_status": status,
        "execution_status": "completed",
        "asset": str(args.asset),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "config": {
            "profile": args.profile,
            "rules": effective_rules,
            "user_rules": args.rule,
            "categories": args.category,
            "predicate": args.predicate,
            "init_rules": should_enable_default_rules(args),
            "variants": args.variants,
            "pxr_ar_default_search_path": search_paths,
        },
        "summary": {
            "issue_count": len(issues),
            "severity_counts": dict(severity_counts),
            "rule_counts": dict(rule_counts),
        },
        "issues": issues,
    }


def build_profile_rationale(profile_name: str | None) -> list[str]:
    if not profile_name:
        return []

    preset = PROFILE_PRESETS[profile_name]
    lines = [
        f"- 当前场景：`{preset['label']}`",
        f"- 场景说明：{preset['description']}",
        f"- 启用规则：{', '.join(f'`{rule}`' for rule in preset['rules'])}",
    ]
    lines.extend(f"- 为什么启用：{reason}" for reason in preset["reasons"])
    return lines


def build_static_profile_advice(payload: dict[str, Any]) -> list[str]:
    if payload["config"].get("profile") != "static":
        return []

    rule_counts = payload["summary"]["rule_counts"]
    lines: list[str] = []

    if payload["status"] == "passed":
        lines.append("- 总体建议：`可直接使用`。当前静态资产在入口、依赖和材质链路上没有发现明显阻塞。")
    elif any(
        rule_counts.get(name)
        for name in ["MissingReferenceChecker", "MaterialPathChecker", "UsdDanglingMaterialBinding", "UsdMaterialBindingApi"]
    ):
        lines.append("- 总体建议：`能预览，但不建议直接交付`。请优先处理依赖和材质链路问题。")
    else:
        lines.append("- 总体建议：`建议先修复再使用`。请先处理入口定义和结构规范性问题。")

    lines.append("- 修复顺序：先修复外部引用和材质依赖，再确认材质绑定，随后补齐 stage 元数据和 defaultPrim。")

    if rule_counts.get("MissingReferenceChecker"):
        lines.append("- `MissingReferenceChecker`：先确认外部依赖文件是否存在，以及路径是否可被当前环境解析。")
    if rule_counts.get("MaterialPathChecker"):
        lines.append("- `MaterialPathChecker`：先确认材质路径是否真实缺失；若命中 `.mdl`，优先检查 resolver search path 是否缺失。")
    if rule_counts.get("UsdDanglingMaterialBinding"):
        lines.append("- `UsdDanglingMaterialBinding`：检查绑定目标材质 prim 是否存在，避免预览与交付结果不一致。")
    if rule_counts.get("UsdMaterialBindingApi"):
        lines.append("- `UsdMaterialBindingApi`：检查材质绑定方式是否规范，避免跨工具链兼容性问题。")
    if rule_counts.get("StageMetadataChecker"):
        lines.append("- `StageMetadataChecker`：补齐 `upAxis`、`metersPerUnit` 等基础元数据，保证跨工具解释一致。")
    if rule_counts.get("DefaultPrimChecker"):
        lines.append("- `DefaultPrimChecker`：确保资产主入口明确，便于引用、加载和资产识别。")

    if any(rule_counts.get(name) for name in ["MaterialPathChecker", "MissingReferenceChecker"]):
        lines.append("- 特别提示：如果问题集中在 `.mdl` 路径，请先确认 `PXR_AR_DEFAULT_SEARCH_PATH` 是否完整；这不一定代表资产本身缺失材质。")

    return lines


def build_stage1_furniture_advice(payload: dict[str, Any]) -> list[str]:
    if payload["config"].get("profile") != "stage1-furniture":
        return []

    rule_counts = payload["summary"]["rule_counts"]
    lines: list[str] = []

    if payload["status"] == "passed":
        lines.append("- 总体建议：`可进入 Stage 1 后续流程`。当前家具/摆件资产在入口、依赖、材质和 mesh 质量上没有发现明显阻塞。")
    elif any(rule_counts.get(name) for name in ["MissingReferenceChecker", "MaterialPathChecker"]):
        lines.append("- 总体建议：`先修依赖再继续`。Stage 1 家具/摆件需要先保证引用、MDL 和贴图路径可解析。")
    elif any(rule_counts.get(name) for name in ["ManifoldChecker", "ValidateTopologyChecker", "ZeroAreaFaceChecker", "NormalsValidChecker"]):
        lines.append("- 总体建议：`先清理 mesh 再做 collider 推荐`。当前几何质量会影响静态 collider authoring 和 runtime hit-test。")
    else:
        lines.append("- 总体建议：`建议修复后复测`。当前问题会影响家具/摆件进入 SimReady Stage 1 流程。")

    lines.append("- Stage 1 边界：本报告负责 validator 校验；家具分类、尺寸参考和静态 collider 推荐由 `usd-simready-inspector` 的 static furniture 流程承接。")
    lines.append("- 推荐顺序：先修引用和材质路径，再清理 mesh，最后运行静态家具推荐和模板 runtime hit-test。")

    if rule_counts.get("DefaultPrimChecker") or rule_counts.get("StageMetadataChecker"):
        lines.append("- 入口与单位：补齐 `defaultPrim`、`upAxis`、`metersPerUnit`，避免家具资产被下游工具按错误入口或尺度读取。")
    if rule_counts.get("UsdDanglingMaterialBinding") or rule_counts.get("UsdMaterialBindingApi"):
        lines.append("- 材质绑定：修正材质 prim 路径和 MaterialBindingAPI，避免 Stage 1 人工复核时出现材质丢失。")
    if rule_counts.get("ExtentsChecker"):
        lines.append("- 尺寸信息：修正 extents，后续尺寸分组、table-slot fitting 和静态 collider 推荐会依赖 bbox。")

    return lines


def infer_next_steps(payload: dict[str, Any]) -> list[str]:
    rule_counts = payload["summary"]["rule_counts"]
    steps: list[str] = []

    if payload["config"].get("profile") == "stage1-furniture":
        if rule_counts.get("MissingReferenceChecker") or rule_counts.get("MaterialPathChecker"):
            steps.append("先修复外部引用、MDL 和贴图路径，保证家具/摆件资产完整可解析。")
        if rule_counts.get("UsdDanglingMaterialBinding") or rule_counts.get("UsdMaterialBindingApi"):
            steps.append("修正材质绑定目标和 MaterialBindingAPI，避免 Stage 1 复核时材质丢失。")
        if any(rule_counts.get(name) for name in ["ManifoldChecker", "ValidateTopologyChecker", "ZeroAreaFaceChecker", "NormalsValidChecker", "WeldChecker"]):
            steps.append("清理 mesh 拓扑、manifold、零面积面、法线和重复点，再做静态 collider 推荐。")
        if rule_counts.get("StageMetadataChecker") or rule_counts.get("DefaultPrimChecker") or rule_counts.get("ExtentsChecker"):
            steps.append("补齐 stage 元数据、defaultPrim 和 extents，稳定后续尺寸分组与模板场景注入。")
        if not steps and payload["status"] == "passed":
            steps.append("运行 usd-simready-inspector 静态家具推荐，抽查 furniture_class、size、support_structure 和 recommended_collider。")
            steps.append("在可用 Isaac Sim runtime 中运行 template physics-hit-test，确认 Stage 1 runtime 链路。")
        if steps:
            return steps[:4]

    if payload["config"].get("profile") == "static":
        if rule_counts.get("MissingReferenceChecker"):
            steps.append("先确认外部依赖文件是否存在，以及当前环境是否能正确解析这些引用。")
        if rule_counts.get("MaterialPathChecker"):
            steps.append("若命中 `.mdl` 材质路径，请先补齐 resolver search path，再区分是真缺失还是环境误报。")
        if rule_counts.get("UsdDanglingMaterialBinding") or rule_counts.get("UsdMaterialBindingApi"):
            steps.append("在静态交付前，先修正材质绑定目标和绑定方式，避免预览与交付结果不一致。")
        if rule_counts.get("StageMetadataChecker") or rule_counts.get("DefaultPrimChecker"):
            steps.append("补齐 stage 元数据和 defaultPrim，保证静态资产入口明确且跨工具表现稳定。")
        if steps:
            return steps[:4]

    if rule_counts.get("MissingReferenceChecker"):
        steps.append("先修复缺失引用或外部依赖，再重新运行校验。")
    if rule_counts.get("UsdDanglingMaterialBinding") or rule_counts.get("UsdMaterialBindingApi"):
        steps.append("检查材质绑定路径和 MaterialBindingAPI 应用位置，先处理材质链路问题。")
    if rule_counts.get("KindChecker") or rule_counts.get("DefaultPrimChecker"):
        steps.append("补齐 kind、defaultPrim 等 USD 结构元数据，降低结构类失败数量。")
    if any(
        rule_counts.get(name)
        for name in [
            "ManifoldChecker",
            "WeldChecker",
            "ValidateTopologyChecker",
            "ZeroAreaFaceChecker",
            "NormalsValidChecker",
        ]
    ):
        steps.append("对 mesh 做第二轮清理，重点处理 manifold、weld、topology 和 normals 问题。")
    if not steps and payload["status"] == "passed":
        steps.append("当前规则范围内未发现问题，可继续做更细的分类检查或进入下游流程。")
    if not steps and payload["status"] == "warning":
        steps.append("当前资产没有失败项，但存在警告，建议按 rule_counts 从高到低逐步清理。")
    if not steps:
        steps.append("按 rule_counts 从高到低排序处理问题，优先解决失败数最多的规则。")

    return steps[:4]


def classify_rule_priority(rule_name: str) -> str:
    if rule_name in HIGH_IMPACT_RULES:
        return "必须修复"
    if rule_name in MEDIUM_IMPACT_RULES:
        return "建议修复"
    if rule_name in LOW_IMPACT_RULES:
        return "可暂缓"
    return "建议修复"


def collect_rules_by_priority(payload: dict[str, Any]) -> dict[str, list[tuple[str, int]]]:
    grouped = {"必须修复": [], "建议修复": [], "可暂缓": []}
    for rule_name, count in payload["summary"]["rule_counts"].items():
        grouped[classify_rule_priority(rule_name)].append((rule_name, count))
    for items in grouped.values():
        items.sort(key=lambda item: (-item[1], item[0]))
    return grouped


def build_one_line_conclusion(payload: dict[str, Any]) -> str:
    rule_counts = payload["summary"]["rule_counts"]
    if payload["config"].get("profile") == "stage1-furniture":
        if payload["status"] == "passed":
            return "这份家具/摆件资产通过了 Stage 1 validator 检查，可以继续进入静态家具推荐和 runtime 模板验证。"
        if any(rule_counts.get(name) for name in ["MissingReferenceChecker", "MaterialPathChecker"]):
            return "这份家具/摆件资产的主要问题在引用或材质依赖，进入 Stage 1 后续流程前应先修复资产完整性。"
        if any(rule_counts.get(name) for name in ["ManifoldChecker", "ValidateTopologyChecker", "ZeroAreaFaceChecker"]):
            return "这份家具/摆件资产的主要问题在 mesh 质量，直接做静态 collider 推荐和 runtime 测试会放大风险。"
        return "这份家具/摆件资产还存在 Stage 1 校验问题，建议按报告优先级修复后复测。"
    if payload["status"] == "passed":
        return "这份资产当前没有发现明显问题，可以继续进入 SimReady 后续流程。"
    if any(rule_counts.get(name) for name in ["KindChecker", "DefaultPrimChecker", "LayerSpecChecker"]):
        return "这份资产的主要问题在资产结构和组织语义，进入 SimReady 前建议先整理层级与入口定义。"
    if any(rule_counts.get(name) for name in ["ManifoldChecker", "ValidateTopologyChecker", "ZeroAreaFaceChecker"]):
        return "这份资产的主要问题在 mesh 质量，继续做碰撞、物理或可移动资产时风险较高。"
    if any(rule_counts.get(name) for name in ["MissingReferenceChecker", "MaterialPathChecker", "UsdDanglingMaterialBinding"]):
        return "这份资产的主要问题在材质和外部依赖链路，当前更像资产不完整，而不是单纯显示细节问题。"
    return "这份资产可以继续使用，但进入正式 SimReady 交付前仍建议先清理当前报告中的问题。"


def asset_use_assessments(payload: dict[str, Any]) -> list[dict[str, str]]:
    rule_counts = payload["summary"]["rule_counts"]
    if payload["config"].get("profile") == "stage1-furniture":
        has_dependency = any(rule_counts.get(name) for name in ["MissingReferenceChecker", "MaterialPathChecker"])
        has_material = any(rule_counts.get(name) for name in ["UsdDanglingMaterialBinding", "UsdMaterialBindingApi"])
        has_mesh = any(
            rule_counts.get(name)
            for name in ["ManifoldChecker", "ValidateTopologyChecker", "ZeroAreaFaceChecker", "NormalsValidChecker", "WeldChecker"]
        )
        has_structure = any(rule_counts.get(name) for name in ["StageMetadataChecker", "DefaultPrimChecker", "ExtentsChecker"])

        stage1_status = "可进入后续流程"
        stage1_reason = "当前 validator 范围内没有发现阻塞家具/摆件 Stage 1 的问题。"
        if has_dependency:
            stage1_status = "先修复依赖"
            stage1_reason = "引用、MDL 或贴图路径不可解析会让资产不完整，后续分类和 authoring 结果不可信。"
        elif has_mesh:
            stage1_status = "先清理 mesh"
            stage1_reason = "mesh 拓扑或法线问题会影响静态 collider 推荐和 runtime 接触稳定性。"
        elif has_material or has_structure:
            stage1_status = "建议修复后继续"
            stage1_reason = "材质绑定、入口或尺寸元数据问题会影响 Stage 1 交付复核。"
        if payload["status"] == "passed":
            stage1_status = "可进入后续流程"
            stage1_reason = "当前检查范围内未发现 Stage 1 阻塞问题。"

        return [
            {"name": "Stage 1 家具/摆件", "status": stage1_status, "reason": stage1_reason},
            {
                "name": "静态 collider 推荐",
                "status": "可作为后续步骤" if not (has_dependency or has_mesh) else "暂缓",
                "reason": "由 usd-simready-inspector 的 static furniture 流程处理，建议在依赖和 mesh 清理后运行。",
            },
            {
                "name": "runtime 模板测试",
                "status": "环境可用时执行",
                "reason": "使用 examples/mini_test.usda 注入家具/摆件资产，blocked 应区分为 runtime 环境问题而不是资产失败。",
            },
        ]

    has_structure = any(rule_counts.get(name) for name in ["KindChecker", "DefaultPrimChecker", "LayerSpecChecker"])
    has_material = any(
        rule_counts.get(name)
        for name in ["MissingReferenceChecker", "MaterialPathChecker", "UsdDanglingMaterialBinding", "UsdMaterialBindingApi"]
    )
    has_topology = any(rule_counts.get(name) for name in ["ManifoldChecker", "ValidateTopologyChecker"])
    has_mesh_cleanup = any(rule_counts.get(name) for name in ["ZeroAreaFaceChecker", "NormalsValidChecker", "WeldChecker"])

    static = "可用"
    static_reason = "主要用于背景或静态摆放时，当前问题更偏材质、结构或网格清理质量。"
    if has_structure or has_material:
        static = "能预览，但不建议直接交付"
        static_reason = "静态使用通常还能预览，但结构和依赖问题会影响正式资产交付质量。"
    if payload["status"] == "passed":
        static = "可直接使用"
        static_reason = "当前检查范围内没有发现会阻碍静态使用的问题。"

    collision = "基本可用"
    collision_reason = "当前没有明显阻断碰撞流程的问题。"
    if has_mesh_cleanup:
        collision = "建议先修"
        collision_reason = "网格存在清理项，碰撞近似和后续处理稳定性可能受影响。"
    if has_topology:
        collision = "不建议直接使用"
        collision_reason = "mesh 存在 non-manifold 或拓扑问题，碰撞和物理稳定性风险较高。"
    if payload["status"] == "passed":
        collision = "可直接使用"
        collision_reason = "当前检查范围内没有发现明显的碰撞相关阻塞。"

    movable = "基本可用"
    movable_reason = "如果只是整体移动，当前问题多数不会立刻阻断。"
    if has_structure or has_material or has_mesh_cleanup:
        movable = "建议先修"
        movable_reason = "可移动资产对完整性和几何质量更敏感，当前问题会放大返工成本。"
    if has_topology:
        movable = "不建议直接使用"
        movable_reason = "mesh 拓扑存在明显风险，继续做搬运、抓取或物理配置不稳妥。"
    if payload["status"] == "passed":
        movable = "可直接使用"
        movable_reason = "当前检查范围内没有发现会阻碍整体移动使用的问题。"

    return [
        {"name": "静态资产", "status": static, "reason": static_reason},
        {"name": "可碰撞资产", "status": collision, "reason": collision_reason},
        {"name": "可移动资产", "status": movable, "reason": movable_reason},
    ]


def format_rule_with_reason(rule_name: str, count: int) -> str:
    explanation = RULE_EXPLANATIONS.get(rule_name)
    if explanation:
        return f"- `{rule_name}`: {count} 个。{explanation['why']}"
    return f"- `{rule_name}`: {count} 个。"


def build_markdown_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    issues = payload["issues"]
    severity_counts = summary["severity_counts"]
    top_issues = issues[:8]
    next_steps = infer_next_steps(payload)
    grouped_rules = collect_rules_by_priority(payload)
    assessments = asset_use_assessments(payload)
    profile_rationale = build_profile_rationale(payload["config"].get("profile"))
    static_profile_advice = build_static_profile_advice(payload)
    stage1_furniture_advice = build_stage1_furniture_advice(payload)
    search_paths = payload["config"].get("pxr_ar_default_search_path", [])

    lines = [
        "# SimReady 资产可用性报告",
        "",
        f"资产：`{payload['asset']}`  ",
        f"检查耗时：`{payload['elapsed_seconds']}` 秒  ",
        f"总体结论：`{payload['status']}`",
        "",
    ]
    if profile_rationale:
        lines.extend(["## 当前场景与启用规则", ""])
        lines.extend(profile_rationale)
        lines.extend([""])

    if search_paths:
        lines.extend(["## 解析器搜索路径", ""])
        lines.append(f"- `PXR_AR_DEFAULT_SEARCH_PATH`：`{os.pathsep.join(search_paths)}`")
        lines.append("- 这有助于减少 MDL、材质依赖和外部引用因搜索路径缺失导致的误报。")
        lines.append("")

    lines.extend(
        [
        "## 一句话结论",
        "",
        build_one_line_conclusion(payload),
        "",
        "## 按 Stage 1 流程看影响" if payload["config"].get("profile") == "stage1-furniture" else "## 按资产用途看影响",
        "",
        ]
    )
    for assessment in assessments:
        lines.append(f"### {assessment['name']}")
        lines.append("")
        lines.append(f"- 结论：`{assessment['status']}`")
        lines.append(f"- 原因：{assessment['reason']}")
        lines.append("")

    if static_profile_advice:
        lines.extend(["## 静态资产交付建议", ""])
        lines.extend(static_profile_advice)
        lines.append("")

    if stage1_furniture_advice:
        lines.extend(["## Stage 1 家具/摆件建议", ""])
        lines.extend(stage1_furniture_advice)
        lines.append("")

    lines.extend(["## 问题按优先级分类", ""])
    for heading in ["必须修复", "建议修复", "可暂缓"]:
        lines.append(f"### {heading}")
        lines.append("")
        if not grouped_rules[heading]:
            lines.append("- 当前没有这一类问题。")
        else:
            for rule_name, count in grouped_rules[heading]:
                lines.append(format_rule_with_reason(rule_name, count))
        lines.append("")

    lines.extend(["## 代表问题", ""])
    if not top_issues:
        lines.append("- 未发现具体问题。")
    else:
        for issue in top_issues:
            rule_name = issue["rule"] or "UnknownRule"
            severity = issue["severity"] or "UNKNOWN"
            location = issue["at"] or "N/A"
            lines.append(f"- [{severity}] `{rule_name}`: {issue['message']}")
            lines.append(f"  位置：`{location}`")

    lines.extend(["", "## 建议的处理顺序", ""])
    for step in next_steps:
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "## 附加信息",
            "",
            f"- 问题总数：`{summary['issue_count']}`",
            f"- 严重级别统计：`{json.dumps(severity_counts, ensure_ascii=False)}`",
            "- JSON 结果仍保留原始 rule 明细，便于 Agent、CI 或后处理程序读取。",
        ]
    )

    return "\n".join(lines) + "\n"


def format_human_summary(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    status = payload["validation_status"]
    lines = [
        f"ExecutionStatus: {payload['execution_status']}",
        f"ValidationStatus: {status}",
        f"Target: {payload['asset']}",
        f"ElapsedSeconds: {payload['elapsed_seconds']}",
        f"IssueCount: {summary['issue_count']}",
        f"SeverityCounts: {json.dumps(summary['severity_counts'], ensure_ascii=False)}",
    ]
    search_paths = payload["config"].get("pxr_ar_default_search_path", [])
    if search_paths:
        lines.append(f"PXR_AR_DEFAULT_SEARCH_PATH: {os.pathsep.join(search_paths)}")
    profile_name = payload["config"].get("profile")
    if profile_name:
        preset = PROFILE_PRESETS[profile_name]
        lines.append(f"Profile: {profile_name} ({preset['label']})")
        lines.append(f"ProfileRules: {', '.join(preset['rules'])}")
        for reason in preset["reasons"]:
            lines.append(f"ProfileReason: {reason}")

    issues = payload["issues"]
    if not issues:
        lines.append("Summary:")
        lines.append("- 未发现校验问题。")
        return "\n".join(lines)

    lines.append("Summary:")
    for issue in issues[:5]:
        rule_name = issue["rule"] or "UnknownRule"
        severity = issue["severity"] or "UNKNOWN"
        lines.append(f"- [{severity}] {rule_name}: {issue['message']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    search_paths = configure_search_paths(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md = args.output_md or args.output_json.with_suffix(".md")
    output_md.parent.mkdir(parents=True, exist_ok=True)
    start = time.time()
    try:
        engine = build_engine(args)
        results = engine.validate(str(args.asset))
        elapsed = time.time() - start

        issues = [issue_to_dict(issue) for issue in results.issues]
        payload = build_payload(args, elapsed, issues, search_paths)
    except Exception as exc:
        elapsed = time.time() - start
        payload = {
            "status": "blocked",
            "validation_status": "blocked",
            "execution_status": "error",
            "asset": str(args.asset),
            "elapsed_seconds": round(elapsed, 3),
            "config": {
                "profile": args.profile,
                "rules": get_effective_rules(args),
                "user_rules": args.rule,
                "categories": args.category,
                "predicate": args.predicate,
                "init_rules": should_enable_default_rules(args),
                "variants": args.variants,
                "pxr_ar_default_search_path": search_paths,
            },
            "summary": {
                "issue_count": 0,
                "severity_counts": {},
                "rule_counts": {},
            },
            "issues": [],
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }

    with args.output_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    with output_md.open("w", encoding="utf-8") as handle:
        handle.write(build_markdown_report(payload))

    print(format_human_summary(payload))
    print(f"MarkdownReport: {output_md}")

    if payload["execution_status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
