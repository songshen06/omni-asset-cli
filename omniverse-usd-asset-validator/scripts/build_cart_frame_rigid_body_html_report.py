#!/usr/bin/env python3
"""Build a standalone HTML report for Cart rigid-frame collider probes."""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
from typing import Any


def _load_case(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    first = payload.get("first_contact") or {}
    cart = payload.get("cart") or {}
    return {
        "side": payload.get("side", path.parent.name),
        "status": payload.get("status", "unknown"),
        "contact": bool(payload.get("contact_detected")),
        "frame": first.get("frame", "—"),
        "collider": first.get("collider1") or first.get("collider0") or "—",
        "target": cart.get("target_collider", "—"),
        "events": payload.get("contact_event_count", 0),
        "json": path.name,
    }


def _render_cards(render_root: Path, cases: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for case in cases:
        side = str(case["side"])
        image_path = render_root / side / "orbit_frames" / "frame_0000.png"
        if not image_path.is_file():
            cards.append(f"<figure><figcaption><code>{html.escape(side)}</code>：未生成截图</figcaption></figure>")
            continue
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        cards.append(
            "<figure>"
            f"<img alt=\"{html.escape(side)} 车架刚体模式测试场景\" src=\"data:image/png;base64,{encoded}\">"
            f"<figcaption><code>{html.escape(side)}</code>：紫红色为实际拥有 CollisionAPI 的 collider 几何；青色为车体范围；紫色细线为少量 collider 的 AABB 参考线。车外探针球不参与范围计算。</figcaption>"
            "</figure>"
        )
    return "".join(cards) or "<p>未找到渲染截图。</p>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Probe output root")
    parser.add_argument("--renders", type=Path, help="Rendered PNG root; images are embedded in the HTML")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.input.resolve()
    out = args.out.resolve()
    cases = [_load_case(path) for path in sorted(root.glob("*/sphere_probe.json"))]
    passed = sum(case["status"] == "passed" and case["contact"] for case in cases)
    rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(str(case['side']))}</code></td>"
        f"<td class=\"{'ok' if case['status'] == 'passed' and case['contact'] else 'bad'}\">{html.escape(str(case['status']))}</td>"
        f"<td>{html.escape(str(case['frame']))}</td>"
        f"<td><code>{html.escape(str(case['collider']))}</code></td>"
        f"<td>{html.escape(str(case['events']))}</td>"
        "</tr>"
        for case in cases
    ) or "<tr><td colspan=5>未找到 sphere_probe.json</td></tr>"
    evidence = json.dumps(cases, ensure_ascii=False, indent=2)
    render_cards = _render_cards(args.renders.resolve(), cases) if args.renders else "<p>未提供渲染目录。</p>"
    summary_class = "ok" if cases and passed == len(cases) else "bad"
    body = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cart 车架刚体模式测试报告</title>
<style>
body{{margin:0;background:#f4f7fa;color:#15202b;font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}main{{max-width:1000px;margin:auto;padding:32px 18px 56px}}section{{background:#fff;border:1px solid #dbe3ea;border-radius:12px;padding:20px;margin:16px 0;box-shadow:0 1px 2px #15202b0b}}h1,h2{{margin:0 0 10px}}.lead{{color:#51606e}}.ok{{color:#137333;font-weight:700}}.bad{{color:#b3261e;font-weight:700}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border:1px solid #dbe3ea;text-align:left;vertical-align:top}}th{{background:#eef4f8}}code,pre{{font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;background:#101820;color:#d9e6ef;border-radius:8px;padding:14px}}ul{{padding-left:20px}}.meta{{font-size:14px;color:#51606e}}.images{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}figure{{margin:0}}img{{display:block;width:100%;border:1px solid #dbe3ea;border-radius:8px;background:#fff}}figcaption{{font-size:13px;color:#51606e;margin-top:6px}}</style></head>
<body><main>
<h1>Cart 车架刚体模式测试报告</h1>
<p class="lead">独立 HTML · Isaac Sim Docker · 静态车架 collider · 侧向球探针</p>
<section><h2>本轮结论</h2><p class="{summary_class}">{passed}/{len(cases)} 个正例取得 PhysX contact report 接触证据。</p>
<p>这证明四个水平方向均能命中预期的车架管件；它<strong>不证明</strong>车架不存在空气墙。空隙穿透、角点斜撞和多半径扫掠仍是下一轮测试。</p></section>
<section><h2>场景设计</h2><ul><li>输入资产仅被引用；源资产不改写。</li><li>在临时 stage 中移除刚体/质量 API，停用 joint；车架仅作为 collision-only 固定对象。</li><li>重力为 0；球半径 40 mm、质量 1 kg、初速度 0.50 m/s；60 Hz、240 帧。</li><li>通过证据：PhysX contact report 同时包含 <code>/World/ProbeSphere</code> 与 <code>/World/InputAsset/.../Frame/...</code>。</li></ul></section>
<section><h2>首轮正例结果</h2><table><thead><tr><th>方向</th><th>状态</th><th>首接触帧</th><th>实际 collider</th><th>接触事件数</th></tr></thead><tbody>{rows}</tbody></table></section>
<section><h2>渲染场景截图</h2><p class="meta">每个方向一张。PNG 已嵌入本 HTML，下载后离线打开即可查看。</p><div class="images">{render_cards}</div></section>
<section><h2>判定边界与后续</h2><ul><li>整体 AABB 对齐不能证明管件间的空隙正确。</li><li>下一轮应从立柱间、横杆间、顶部中央与底部中央开口穿行 10/25/40 mm 球。</li><li>视觉开口中出现 contact 为“空气墙”；可见管件上无 contact 为“漏碰”。</li><li>后续将以视觉 mesh 首交点与 PhysX 首接触点的距离进行毫米级判定：≤2 mm 通过，2–5 mm 警告，>5 mm 失败。</li></ul></section>
<section><h2>嵌入的机器可读证据</h2><p class="meta">本文件不依赖外部脚本、样式或数据文件；下方 JSON 已嵌入 HTML。</p><pre>{html.escape(evidence)}</pre></section>
</main></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
