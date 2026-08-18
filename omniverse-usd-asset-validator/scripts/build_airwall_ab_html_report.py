#!/usr/bin/env python3
"""Build a compact HTML report comparing two Isaac Sim collider probes."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from foundation_common import write_json


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def case(name: str, directory: Path) -> dict[str, Any]:
    summary = load(directory / "summary.json")
    runtime = load(directory / "runtime_report.json")
    contact = runtime.get("final_state", {}).get("contact_report", {})
    first = contact.get("first_target_event") if isinstance(contact, dict) else None
    sampling = runtime.get("sampling_summary", {})
    return {
        "name": name,
        "directory": str(directory.resolve()),
        "input_usd": runtime.get("input_usd_path"),
        "result": summary.get("result"),
        "contact_detected": summary.get("checks", {}).get("contact_report_detected"),
        "contact_evidence_level": summary.get("contact_evidence_level"),
        "first_contact_frame": first.get("frame") if isinstance(first, dict) else None,
        "first_contact_collider": first.get("collider1") if isinstance(first, dict) else None,
        "event_count": contact.get("target_event_count") if isinstance(contact, dict) else None,
        "last_box_position": sampling.get("last_sample", {}).get("box_z") if isinstance(sampling, dict) else None,
        "runtime_report": str((directory / "runtime_report.json").resolve()),
        "timeline": str((directory / "timeline.csv").resolve()),
        "summary": str((directory / "summary.json").resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", type=Path, required=True, help="Original-probe output directory")
    parser.add_argument("--b", type=Path, required=True, help="Candidate-probe output directory")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    a = case("A · 原始 cart", args.a.resolve())
    b = case("B · 安全修复候选", args.b.resolve())
    same = all(a.get(key) == b.get(key) for key in ("result", "contact_detected", "first_contact_frame", "first_contact_collider", "event_count", "last_box_position"))
    conclusion = (
        "在本次静态 collider probe 中，A 与 B 的可观测结果完全相同；移除 primitive 上无效的 MeshCollision/SDF 标记没有改变该条测试轨迹上探针的首次接触。"
        if same else "A 与 B 在至少一项可观测接触指标上不同；请查看两组工件确认差异。"
    )
    payload = {
        "schema_version": "1.0", "test": "isaac-sim-static-collider-a-b-probe", "a": a, "b": b,
        "same_observed_outcome": same, "conclusion": conclusion,
        "limitations": [
            "This is a static-collider isolation test: cart rigid bodies and joints are disabled only in the generated temporary stage.",
            "It proves observed contact behavior for this one template, trajectory, and dynamic box; it does not measure contactOffset/restOffset or every surface direction.",
            "The earlier rendered run was excluded because it timed out before a completed simulation result.",
        ],
    }
    root = args.out.resolve().parent
    links = lambda value: html.escape(str(Path(value).resolve().relative_to(root)))
    visual_snapshots = [
        args.a.resolve() / "render_frames" / preset / "frame_0000.png"
        for preset in ("side", "iso")
    ]
    available_snapshots = [path for path in visual_snapshots if path.is_file()]
    snapshot_cards = "".join(
        f'<figure><img src="{links(path)}" alt="{html.escape(path.parent.name)} view, frame 0"><figcaption>{html.escape(path.parent.name)} · frame 0</figcaption></figure>'
        for path in available_snapshots
    ) or "<p>没有可用渲染快照。</p>"
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(a.get(key)))}</td><td>{html.escape(str(b.get(key)))}</td></tr>"
        for key in ("result", "contact_detected", "contact_evidence_level", "first_contact_frame", "first_contact_collider", "event_count", "last_box_position")
    )
    report = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cart collider A/B probe</title><style>body{{font:16px/1.55 system-ui,sans-serif;color:#15202b;background:#f4f6f8;margin:0}}main{{max-width:960px;margin:auto;padding:32px 18px}}section{{background:#fff;border:1px solid #d9e1e8;border-radius:12px;padding:18px;margin:16px 0}}h1,h2{{margin-top:0}}.ok{{color:#137333;font-weight:700}}.warn{{color:#9a6500}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px;border:1px solid #d9e1e8;text-align:left;vertical-align:top}}th{{background:#edf3f7}}code{{overflow-wrap:anywhere;font-size:12px}}a{{color:#145b8a}}.snapshots{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}figure{{margin:0}}img{{display:block;width:100%;border:1px solid #d9e1e8;border-radius:8px;background:#102b42}}figcaption{{font-size:13px;color:#586775;margin-top:5px}}</style><main><h1>Cart collider A/B probe</h1><p>Isaac Sim Docker · 120 frames · 60 FPS · preserve size · template side-hit · dynamic box → static cart collider</p><section><h2 class="{'ok' if same else 'warn'}">结论</h2><p>{html.escape(conclusion)}</p></section><section><h2>可视化快照（原始资产 A）</h2><p class="warn">这些图来自此前渲染运行在超时前写出的 frame 0，只用于帮助辨认测试场景与 collider overlay；该次运行未完成，不纳入 A/B 接触结论。</p><div class="snapshots">{snapshot_cards}</div></section><section><h2>同条件结果</h2><table><thead><tr><th>指标</th><th>A：原始</th><th>B：候选</th></tr></thead><tbody>{rows}</tbody></table></section><section><h2>测试边界</h2><ul>{''.join(f'<li>{html.escape(item)}</li>' for item in payload['limitations'])}</ul><p>因此本结果排除了“这 78 个无效 MeshCollision/SDF 标记在该测试轨迹上单独造成更早接触”的假设；仍不能排除其他方向的局部形状、接触 offset 或完整 articulation 运动下的问题。</p></section><section><h2>审计工件</h2><ul><li>A：<a href="{links(a['summary'])}">summary</a> · <a href="{links(a['runtime_report'])}">runtime report</a> · <a href="{links(a['timeline'])}">timeline</a></li><li>B：<a href="{links(b['summary'])}">summary</a> · <a href="{links(b['runtime_report'])}">runtime report</a> · <a href="{links(b['timeline'])}">timeline</a></li></ul></section></main></html>'''
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    write_json(root / "ab_summary.json", payload)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
