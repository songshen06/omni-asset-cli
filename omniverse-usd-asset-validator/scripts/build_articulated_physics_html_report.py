#!/usr/bin/env python3
"""Build a self-contained HTML report for the articulated physics structure workflow."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


REPAIRS = {
    "RB.006": {
        "title": "嵌套刚体 transform stack",
        "class": "manual",
        "summary": "当前不修改 USD。需要选择扁平 body-link 层级，或 reset transform stack 后重算子刚体世界姿态与 joint frame。",
    },
    "RB.COL.002": {
        "title": "非 Mesh 使用 MeshCollisionAPI",
        "class": "safe",
        "summary": "可生成非破坏性候选：从 Cylinder/Cube/Sphere 移除 PhysicsMeshCollisionAPI，保留 PhysicsCollisionAPI、可视外形和材质绑定。",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def prim_list(prims: list[str]) -> str:
    if not prims:
        return "<p class='muted'>无。</p>"
    items = "".join(f"<li><code>{html.escape(prim)}</code></li>" for prim in prims)
    return f"<details><summary>受影响 prim（{len(prims)}）</summary><ul>{items}</ul></details>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    workflow = load_json(args.workflow)
    policy = load_json(args.policy)
    root = args.out.resolve().parent
    findings = {item.get("requirement_id"): item for item in policy.get("findings", []) if isinstance(item, dict)}
    status = str(workflow.get("status", "blocked")).upper()
    cards: list[str] = []
    for requirement, repair in REPAIRS.items():
        finding = findings.get(requirement, {})
        prims = finding.get("prims", []) if isinstance(finding.get("prims", []), list) else []
        result = "发现待修复项" if finding else "本次 gate 通过"
        cards.append(
            "<section class='card'>"
            f"<div class='card-head'><h2>{requirement} · {repair['title']}</h2><span class='tag {repair['class']}'>{repair['class']}</span></div>"
            f"<p class='result'>{result}：<strong>{len(prims)}</strong> 个 prim</p>"
            f"<p>{repair['summary']}</p>{prim_list(prims)}</section>"
        )
    profile = workflow.get("profile", {})
    scope = workflow.get("scope", {})
    artifacts = workflow.get("artifacts", {})
    safe_repair = workflow.get("safe_repair", {}) if isinstance(workflow.get("safe_repair"), dict) else {}
    artifact_links = "".join(
        f"<li><a href='{html.escape(rel(Path(path), root))}'>{html.escape(name)}</a></li>"
        for name, path in artifacts.items() if isinstance(path, str)
    )
    deferred = " · ".join(html.escape(str(item)) for item in scope.get("deferred", []))
    candidate = safe_repair.get("candidate", {}) if isinstance(safe_repair.get("candidate"), dict) else {}
    geometry_path = artifacts.get("geometry_fidelity")
    try:
        geometry = load_json(Path(str(geometry_path))) if geometry_path else {}
    except (OSError, ValueError, json.JSONDecodeError):
        geometry = {}
    geometry_summary = geometry.get("summary", {}) if isinstance(geometry.get("summary"), dict) else {}
    geometry_findings = geometry.get("findings", []) if isinstance(geometry.get("findings"), list) else []
    geometry_bodies = geometry.get("bodies", []) if isinstance(geometry.get("bodies"), list) else []
    geometry_rows = "".join(
        "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(item.get("body", ""))),
            html.escape(str(item.get("requirement_id", ""))),
            html.escape(str(item.get("message", ""))),
            html.escape(str(item.get("overflow_world", item.get("undercoverage_world", "n/a")))),
    ) for item in geometry_findings if isinstance(item, dict)
    ) or "<tr><td colspan='4'>没有发现 collider 外包络超过视觉 AABB 的静态证据。</td></tr>"
    body_rows = "".join(
        "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td><td><code>{}</code></td></tr>".format(
            html.escape(str(item.get("path", ""))),
            html.escape(str(item.get("classification", ""))),
            html.escape(str(item.get("visual_prim_count", 0))),
            html.escape(str(item.get("collider_prim_count", 0))),
            html.escape(str(item.get("collider_overflow_world", "n/a"))),
        ) for item in geometry_bodies if isinstance(item, dict)
    ) or "<tr><td colspan='5'>未生成逐刚体几何数据。</td></tr>"
    remaining = safe_repair.get("candidate_remaining_focus_findings", [])
    remaining_text = "、".join(html.escape(str(item)) for item in remaining) if remaining else "无"
    report = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Articulated Physics Structure Report</title><style>
:root {{ --bg:#f4f6f8; --ink:#15202b; --muted:#586775; --card:#fff; --line:#d9e1e8; --red:#ad2931; --amber:#9a6500; --blue:#145b8a; --green:#137333; }} *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}} main{{max-width:1100px;margin:auto;padding:32px 20px 48px}} header{{background:#102b42;color:#fff;padding:28px;border-radius:14px}} h1{{margin:0;font-size:28px}} h2{{font-size:18px;margin:0}} .meta,.muted{{color:var(--muted)}} .meta{{margin:8px 0 0;color:#d8e5ed}} .status{{display:inline-block;margin-top:15px;padding:4px 10px;border-radius:999px;background:{'#f4b4b4' if status == 'FAILED' else '#bfe5c8'};color:#15202b;font-weight:700}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px;margin-top:18px}} .card,.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px}} .card-head{{display:flex;gap:12px;justify-content:space-between;align-items:flex-start}} .tag{{padding:3px 8px;border-radius:999px;font-size:12px;font-weight:700;color:#fff}} .manual{{background:var(--amber)}} .safe{{background:var(--green)}} .result{{color:var(--red)}} code{{font-size:12px;overflow-wrap:anywhere}} details{{border-top:1px solid var(--line);padding-top:10px}} ul{{padding-left:20px}} a{{color:var(--blue)}} ol{{padding-left:22px}} table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{border:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}} th{{background:#edf3f7}} </style></head>
<body><main><header><h1>Articulated Physics Structure Workflow</h1><p class="meta">上游基线：{html.escape(str(profile.get('id')))} v{html.escape(str(profile.get('version')))} · {html.escape(str(profile.get('tag')))}</p><span class="status">当前 scope：{status}</span></header>
<section class="panel" style="margin-top:18px"><h2>本轮边界</h2><p>仅以 <code>RB.006</code> 与 <code>RB.COL.002</code> 决定 workflow 结果。以下项仅保留在上游原始报告中，不参与本轮 gate：{deferred or '无'}。</p><p><strong>修复状态：尚未对源 USD 写入任何修改。</strong>本报告区分可安全生成候选的 schema 修复与必须人工批准的机构重构。</p></section>
<div class="grid">{''.join(cards)}</div>
<section class="panel" style="margin-top:18px"><h2>刚体物理形态 vs 视觉形态：空气墙静态审计</h2><p>证据级别：<strong>{html.escape(str(geometry.get('evidence_level', 'not-run')))}</strong>。按每个刚体的最近拥有关系，将可见几何与 collider 几何分别取世界坐标 AABB，并使用 <strong>{html.escape(str(geometry.get('tolerance_world_units', 'n/a')))}</strong> world-unit 容差比对。</p><p>结果：检查 {html.escape(str(geometry_summary.get('rigid_body_count', 0)))} 个刚体；collider 超出视觉外包络：<strong>{html.escape(str(geometry_summary.get('collider_overflow_body_count', 0)))}</strong>；视觉范围未被 collider 覆盖：<strong>{html.escape(str(geometry_summary.get('undercoverage_body_count', 0)))}</strong>。</p><table><thead><tr><th>刚体</th><th>规则</th><th>解释</th><th>最大差值（世界单位）</th></tr></thead><tbody>{geometry_rows}</tbody></table><p><strong>如何解读：</strong>RB.GEO.001 才是“作者几何本身大于可见物体”的静态空气墙证据。RB.GEO.002 表示物理形态可能比视觉更小（简化碰撞、漏 collider 或有意忽略装饰）。即使两者均为零，也不能证明运行时没有空气墙：PhysX cooking、SDF/HACD、contactOffset/restOffset、碰撞层和 joint 运动姿态都不在 AABB 静态检查范围内。</p><p><strong>当前资产的关键结论：</strong>现有 primitive collider 与可见 primitive 共享同一个 prim；因此如果本表没有 RB.GEO.001，问题不应被归因于“单独 author 了一个更大的 collider 网格”。下一步应在 Isaac Sim 中使用推进/接触距离实验，记录首次接触时 visual 表面之间的间隙和 contact report，才能确认是否是 runtime cooking 或 contact offset。</p></section>
<section class="panel" style="margin-top:18px"><h2>逐刚体覆盖台账</h2><p>本台账用于把“哪个刚体的物理范围不对”变成可追踪项。视觉 prim 与 collider prim 相同并不表示运行时接触距离为零；它只证明作者的基础几何没有额外放大。</p><table><thead><tr><th>刚体</th><th>静态分类</th><th>视觉 prim</th><th>collider prim</th><th>collider 外溢</th></tr></thead><tbody>{body_rows}</tbody></table></section>
<section class="panel" style="margin-top:18px"><h2>已生成的安全修复候选</h2><p>状态：<strong>{html.escape(str(safe_repair.get('status', 'not-run')))}</strong>；已处理 <strong>{html.escape(str(safe_repair.get('applied_count', 0)))}</strong> 个 prim。</p><p>候选文件：<code>{html.escape(str(candidate.get('path', '未生成')))}</code></p><p>候选复扫仍存在的本轮 finding：<strong>{remaining_text}</strong>。预期应只剩 <code>RB.006</code>；这证明 collider schema 修复与嵌套刚体重构被分离处理。</p><p>候选也已再次运行完整上游 Profile（返回码：<code>{html.escape(str(safe_repair.get('candidate_official_profile_returncode')))}</code>）。非零返回码仍预期存在，因为 <code>RB.006</code> 与 deferred 项尚未修复；请通过下方 candidate Foundation 工件确认 <code>RB.COL.002</code> 不再出现。</p></section>
<section class="panel" style="margin-top:18px"><h2>RB.006 人工决策记录：为什么不自动修复</h2><p>无法从 USD 文本唯一推断“正确”的 link 坐标系与 joint frame，因此工具不会自动写入 reset stack 或移动刚体。必须由资产负责人在以下方案中选择：</p><ol><li><strong>扁平 body-link 层级（推荐）</strong>：将 12 个可动刚体移到并列 physics links；保留视觉结构或以引用绑定；随后更新 12 条 joint 的 body target 与 local frame。</li><li><strong>保留嵌套层级</strong>：为每个子刚体 author <code>!resetXformStack!</code>，按原世界姿态重算其 local transform，并重新校准各 joint 的 local position/rotation。</li></ol><p>两种方案均须证明：四个 caster 的 swivel/wheel 轴仍正确、静态姿态未漂移、无关节爆炸/穿透，并完成 Docker contact 与 motion 复验。未完成这些证据前，<code>RB.006</code> 保持失败。</p></section>
<section class="panel" style="margin-top:18px"><h2>执行链</h2><ol><li>运行冻结的 <code>Prop-Robotics-Physx</code>，保留完整原始 finding。</li><li>按最近刚体祖先扫描 body ownership、嵌套刚体和 collider schema。</li><li>先生成 <code>RB.COL.002</code> 非破坏性修复候选并静态复验。</li><li>批准后再重构 <code>RB.006</code>，复算 transform 与 12 条 joint frame。</li><li>完成后用同一 Profile 复验，并执行 Isaac Sim Docker contact/joint-motion 验证。</li></ol></section>
<section class="panel" style="margin-top:18px"><h2>审计工件</h2><ul>{artifact_links}</ul></section>
</main></body></html>"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
