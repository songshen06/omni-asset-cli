#!/usr/bin/env python3
"""Build a standalone Chinese HTML report for RB.COL.003 convex collider review."""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any


RULE_ID = "RB.COL.003"


def image_data_uri(path: Path) -> str | None:
    if not path.is_file():
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path, help="Three-view artifact directory containing orbit_frames/")
    parser.add_argument("--upstream-profile", help="Selected upstream Foundation profile name")
    parser.add_argument("--expected-mesh-approximation", help="Approximation required by that selected upstream profile")
    parser.add_argument("--out", type=Path, required=True, help="Standalone HTML output path")
    parser.add_argument("--output-json", type=Path, help="Structured companion report path")
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    asset_path = str((audit.get("asset") or {}).get("path", ""))
    asset_label = Path(asset_path).stem or "USD asset"
    findings = [item for item in audit.get("findings", []) if item.get("rule_id") == RULE_ID]
    checks = audit.get("checks", {})
    images: list[tuple[str, str | None]] = []
    if args.render_dir:
        frame_dir = args.render_dir / "orbit_frames"
        for index, label in enumerate(("前视", "侧视", "顶视")):
            images.append((label, image_data_uri(frame_dir / f"frame_{index:04d}.png")))
    observed_approximations = sorted({str(item.get("physics_approximation")) for item in findings if item.get("physics_approximation")})
    upstream_alignment: dict[str, Any] = {
        "profile": args.upstream_profile,
        "expected_mesh_approximation": args.expected_mesh_approximation,
        "observed_mesh_approximations": observed_approximations,
        "status": "not_evaluated",
    }
    if args.upstream_profile and args.expected_mesh_approximation:
        upstream_alignment["status"] = "not_applicable" if not observed_approximations else (
            "conformant" if all(item == args.expected_mesh_approximation for item in observed_approximations)
            else "nonconformant"
        )

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "report_type": "convex-collider-analysis",
        "asset": audit.get("asset"),
        "audit": str(args.audit.resolve()),
        "rule_id": RULE_ID,
        "status": "review_required" if findings else "not_detected",
        "observed": {
            "collision_api_count": checks.get("collision_api_count"),
            "convex_mesh_collider_review_count": checks.get("convex_mesh_collider_review_count", 0),
            "findings": findings,
        },
        "upstream_profile_alignment": upstream_alignment,
        "conclusion": (
            "检测到运行时凸包/凸包分解碰撞器。USD 只记录烹饪策略，不保存最终 PhysX 凸体；"
            "因此该检查确认风险和验证路径，不能仅凭静态 USD 定量证明绿色线框每处偏离。"
            if findings else "未检测到凸包或凸包分解的 MeshCollider。"
        ),
        "recommendations": [
            "先用 physics-collider-three-view 检查绿色 PhysX 线框是否跨过车架孔洞、管件间隙或轮组空隙。",
            "对确认产生空气墙的区域，按车架管件、轮组和支撑板拆分为多个显式 collider；不要让整个小车只由一个凸包分解 collider 覆盖。",
            "动态刚体优先使用 primitive 或多个凸包 collider；不要把 triangle mesh 当作动态碰撞替代。",
            "修复后运行定向 A/B probe：探针球分别对准视觉表面内侧和疑似外扩位置，记录接触点；同时保留 PhysX contact evidence。",
            "此次项为 manual：自动移除 convexDecomposition 会改变物理行为，必须由资产作者确认拆分边界。",
        ],
    }
    json_path = args.output_json or args.out.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>人工修复</td></tr>".format(
            html.escape(str(item.get("prim", ""))),
            html.escape(str(item.get("prim_type", ""))),
            html.escape(str(item.get("physics_approximation", ""))),
        ) for item in findings
    ) or "<tr><td colspan='4'>未检测到 RB.COL.003</td></tr>"
    image_html = "".join(
        f"<figure><figcaption>{label}</figcaption>" + (f"<img src='{uri}' alt='{label} PhysX collider view'>" if uri else "<p>未提供该视图。</p>") + "</figure>"
        for label, uri in images
    )
    recommendations = "".join(f"<li>{html.escape(text)}</li>" for text in report["recommendations"])
    upstream_status = upstream_alignment["status"]
    upstream_summary = (
        f"Profile <code>{html.escape(str(upstream_alignment['profile']))}</code> 期望 mesh approximation 为 "
        f"<code>{html.escape(str(upstream_alignment['expected_mesh_approximation']))}</code>；当前观察到 "
        f"<code>{html.escape(', '.join(observed_approximations) or '无')}</code>。结论：<strong>{html.escape(str(upstream_status))}</strong>。"
        if args.upstream_profile and args.expected_mesh_approximation
        else "未提供上游 profile 及其 approximation 要求；本报告不对 Foundation 合规性下结论。"
    )
    page = f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'>
<title>Convex Collider Analysis</title><style>
body{{font:15px system-ui,sans-serif;margin:32px;color:#1b2630;max-width:1400px}}h1{{color:#153d2a}}h2{{margin-top:28px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #cbd5d9;padding:9px;text-align:left}}th{{background:#eef5f0}}.warn{{background:#fff5dc;padding:14px;border-left:5px solid #d79300}}.views{{display:flex;gap:14px;flex-wrap:wrap}}figure{{margin:0;width:31%;min-width:330px}}img{{width:100%;background:#000;border:1px solid #ccd}}figcaption{{font-weight:700;margin:8px 0}}</style>
<h1>{html.escape(asset_label)} 凸包 Collider 风险分析</h1>
<p>规则：<code>{RULE_ID}</code> · 审计状态：<strong>{html.escape(report['status'])}</strong> · 资产：<code>{html.escape(asset_path)}</code></p>
<div class='warn'><strong>结论：</strong>{html.escape(report['conclusion'])}</div>
<h2>上游 Foundation profile 对齐</h2><p>{upstream_summary}</p><p>这仅判断 authoring 的 approximation 合规性；它<strong>不</strong>证明最终 PhysX cooked collider 已贴合视觉 mesh。该运行时偏离仍由 <code>RB.COL.003</code>、绿色原生线框和 A/B probe 分层处理。</p>
<h2>固定检测结果</h2><p>CollisionAPI 数：{html.escape(str(checks.get('collision_api_count')))}；凸包 MeshCollider 审查项：{html.escape(str(checks.get('convex_mesh_collider_review_count', 0)))}</p>
<table><tr><th>Prim</th><th>类型</th><th>PhysX approximation</th><th>处置</th></tr>{rows}</table>
<h2>为什么可能出现“空气墙”</h2><p>当前碰撞器是视觉 Mesh 的 <code>convexDecomposition</code> 烹饪请求。PhysX 会把网格转换为一个或多个凸体；凸体不能表达任意凹槽、开孔和细小缝隙。当分块过少或包络跨越空腔时，绿色线框会落在视觉表面之外，探针会先于可见车架发生接触。</p>
<p>静态 USD 中没有最终 cooked convex pieces，因此本项严格区分：<strong>已检测到风险</strong> 与 <strong>已由三视图/A-B 运行时探针证明的偏离</strong>。后者需要 PhysX 运行时证据。</p>
<h2>PhysX 原生三视图证据</h2><div class='views'>{image_html or '<p>未提供渲染目录。</p>'}</div>
<h2>建议</h2><ol>{recommendations}</ol>
<p>结构化报告：<code>{html.escape(str(json_path.resolve()))}</code></p></html>"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(args.out.resolve())
    print(json_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
