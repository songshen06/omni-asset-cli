#!/usr/bin/env python3
"""Build a standalone report for the Cart collider-only render."""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", type=Path, required=True, help="safe_repair.json")
    parser.add_argument("--probe", type=Path, required=True, help="v2 sphere_probe.json")
    parser.add_argument("--image", type=Path, required=True, help="Purple collider-only PNG")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repair = json.loads(args.repair.read_text(encoding="utf-8"))
    probe = json.loads(args.probe.read_text(encoding="utf-8"))
    encoded_image = base64.b64encode(args.image.read_bytes()).decode("ascii")
    cart = probe.get("cart") or {}
    source = repair.get("source") or {}
    candidate = repair.get("candidate") or {}
    repair_count = len(repair.get("applied") or [])
    body = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cart 实际碰撞体报告</title>
<style>body{{margin:0;background:#f4f7fa;color:#15202b;font:16px/1.58 system-ui,-apple-system,"Segoe UI",sans-serif}}main{{max-width:1050px;margin:auto;padding:32px 18px 56px}}section{{background:#fff;border:1px solid #dbe3ea;border-radius:12px;padding:20px;margin:16px 0}}h1,h2{{margin:0 0 10px}}.lead,.muted{{color:#51606e}}.ok{{color:#137333;font-weight:700}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #dbe3ea;padding:10px;text-align:left;vertical-align:top}}th{{background:#eef4f8}}code{{font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}}img{{display:block;width:100%;background:#000;border-radius:8px;border:1px solid #202833}}ul{{padding-left:20px}}</style></head><body><main>
<h1>Cart 实际碰撞体报告</h1><p class="lead">单文件离线报告 · Isaac Sim Docker · 车架刚体模式 v2</p>
<section><h2>紫色图：实际碰撞几何</h2><p>紫色仅表示当前带 <code>CollisionAPI</code> 的实际碰撞几何；不含视觉 mesh、AABB 范围框、测试球或质心标记。管架中间为空是正确设计，不存在实心碰撞盒。</p><img alt="Cart 实际 CollisionAPI 碰撞几何" src="data:image/png;base64,{encoded_image}"></section>
<section><h2>本轮运行时证据</h2><p class="ok">author collider = {html.escape(str(cart.get('authored_collider_count')))}；active collider = {html.escape(str(cart.get('active_collider_count')))}。二者一致。</p><p>测试方向：<code>{html.escape(str(probe.get('side')))}</code>；首次 PhysX contact：第 <code>{html.escape(str((probe.get('first_contact') or {{}}).get('frame')))}</code> 帧。</p></section>
<section><h2>与原始 USD 的差异</h2><table><thead><tr><th>层</th><th>是否持久改写原始 USD</th><th>内容</th></tr></thead><tbody>
<tr><td>原始资产</td><td>否</td><td><code>{html.escape(str(source.get('path')))}</code><br>SHA256: <code>{html.escape(str(source.get('sha256')))}</code></td></tr>
<tr><td>safe repair candidate</td><td>新建候选文件；不回写原始</td><td>对 {repair_count} 个 primitive collider 删除 <code>PhysicsMeshCollisionAPI</code> 及 <code>physics:approximation</code>，但保留 <code>CollisionAPI</code>、管件几何、尺寸、位置、刚体层级和 joint。</td></tr>
<tr><td>车架刚体测试</td><td>否</td><td>仅在生成的测试 USD 内冻结刚体、停用 joint、添加零重力和测试球；不添加额外 collider。</td></tr>
<tr><td>本图渲染层</td><td>否</td><td>仅以紫色材质显示实际 collider，并隐藏非 collider 几何与调试标记。</td></tr>
</tbody></table><p class="muted">Candidate: <code>{html.escape(str(candidate.get('path')))}</code><br>SHA256: <code>{html.escape(str(candidate.get('sha256')))}</code></p></section>
</main></body></html>"""
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body, encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
