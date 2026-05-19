#!/usr/bin/env python3
"""Generate a lightweight static gallery for images and videos under out/."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


IMAGE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}
VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogv",
    ".webm",
}
REPORT_FILENAMES = (
    "summary.json",
    "runtime_report.json",
    "timeline.csv",
    "flywheel_report.json",
)


@dataclass(frozen=True)
class MediaItem:
    path: str
    name: str
    kind: str
    group: str
    size: int
    size_label: str
    modified: str


@dataclass(frozen=True)
class ReportLink:
    path: str
    label: str
    group: str


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size} B"


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def media_group(relative_path: Path) -> str:
    parent = relative_path.parent
    if parent == Path("."):
        return "out"
    if parent.name == "render_frames" and parent.parent != Path("."):
        return parent.parent.as_posix()
    return parent.as_posix()


def scan_media(out_dir: Path, output_path: Path) -> list[MediaItem]:
    items: list[MediaItem] = []
    output_path = output_path.resolve()
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == output_path:
            continue
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            kind = "image"
        elif suffix in VIDEO_EXTENSIONS:
            kind = "video"
        else:
            continue

        relative = path.relative_to(out_dir)
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        items.append(
            MediaItem(
                path=relative.as_posix(),
                name=path.name,
                kind=kind,
                group=media_group(relative),
                size=stat.st_size,
                size_label=format_size(stat.st_size),
                modified=modified,
            )
        )

    return sorted(items, key=lambda item: (item.group, item.path))


def scan_reports(out_dir: Path, groups: set[str]) -> list[ReportLink]:
    links: list[ReportLink] = []
    for group in sorted(groups):
        group_dir = out_dir if group == "out" else out_dir / group
        if not group_dir.exists():
            continue
        for filename in REPORT_FILENAMES:
            report = group_dir / filename
            if report.is_file():
                links.append(ReportLink(path=relpath(report, out_dir), label=filename, group=group))
        for report in sorted(group_dir.glob("*.md")):
            links.append(ReportLink(path=relpath(report, out_dir), label=report.name, group=group))
    return links


def html_document(title: str, items: list[MediaItem], reports: list[ReportLink], source_dir: Path) -> str:
    safe_title = html.escape(title, quote=False)
    payload = {
        "title": title,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sourceDir": str(source_dir),
        "items": [asdict(item) for item in items],
        "reports": [asdict(report) for report in reports],
    }
    manifest = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f4;
      --fg: #1e2528;
      --muted: #667076;
      --line: #d9dedb;
      --panel: #ffffff;
      --accent: #176b87;
      --chip: #ecf3f0;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #121615;
        --fg: #edf2ef;
        --muted: #a8b3ad;
        --line: #2d3734;
        --panel: #1a201e;
        --accent: #6dc7d9;
        --chip: #25302c;
        --shadow: none;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: color-mix(in srgb, var(--bg) 92%, transparent);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .bar {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      max-width: 1500px;
      margin: 0 auto;
      padding: 14px 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 18px;
      font-weight: 650;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(180px, 360px) auto auto;
      gap: 8px;
      max-width: 1500px;
      margin: 0 auto;
      padding: 0 18px 14px;
    }}
    input, select {{
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      color: var(--fg);
      padding: 6px 10px;
      font: inherit;
    }}
    main {{
      max-width: 1500px;
      margin: 0 auto;
      padding: 18px;
    }}
    .group {{
      margin: 0 0 28px;
    }}
    .group-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 10px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h2 {{
      margin: 0;
      font-size: 15px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 6px;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    .links a, .pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      background: var(--chip);
      color: var(--fg);
      padding: 3px 8px;
      font-size: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 12px;
    }}
    .card {{
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .thumb {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 10;
      background: #0b0f10;
      object-fit: contain;
      cursor: zoom-in;
    }}
    video.thumb {{
      cursor: default;
    }}
    .caption {{
      display: grid;
      gap: 4px;
      padding: 9px 10px 10px;
    }}
    .name {{
      color: var(--fg);
      font-weight: 600;
      overflow-wrap: anywhere;
    }}
    .path {{
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .stats {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 36px;
      color: var(--muted);
      text-align: center;
    }}
    dialog {{
      width: min(96vw, 1400px);
      height: min(94vh, 980px);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0;
      background: var(--panel);
      color: var(--fg);
    }}
    dialog::backdrop {{
      background: rgba(0, 0, 0, 0.72);
    }}
    .viewer {{
      display: grid;
      grid-template-rows: auto 1fr auto;
      height: 100%;
    }}
    .viewer-bar {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding: 9px 12px;
    }}
    .viewer-title {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 650;
    }}
    .viewer-actions {{
      display: flex;
      gap: 6px;
      align-items: center;
      white-space: nowrap;
    }}
    button {{
      min-height: 32px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--chip);
      color: var(--fg);
      font: inherit;
      cursor: pointer;
      padding: 5px 9px;
    }}
    .viewer-stage {{
      display: grid;
      place-items: center;
      min-height: 0;
      background: #080b0c;
    }}
    .viewer-stage img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }}
    .viewer-foot {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid var(--line);
      padding: 8px 12px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 760px) {{
      .bar, .controls {{
        grid-template-columns: 1fr;
      }}
      .meta {{
        white-space: normal;
      }}
      .group-head {{
        display: grid;
      }}
      .links {{
        justify-content: flex-start;
      }}
      .grid {{
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <h1 id="title"></h1>
      <div class="meta" id="meta"></div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Filter by path or group">
      <select id="kind">
        <option value="all">All media</option>
        <option value="image">Images</option>
        <option value="video">Videos</option>
      </select>
      <select id="sort">
        <option value="path">Sort by path</option>
        <option value="modified">Sort by newest</option>
        <option value="size">Sort by size</option>
      </select>
    </div>
  </header>
  <main id="gallery"></main>
  <dialog id="viewer">
    <div class="viewer">
      <div class="viewer-bar">
        <div class="viewer-title" id="viewer-title"></div>
        <div class="viewer-actions">
          <button id="prev" type="button">Prev</button>
          <button id="next" type="button">Next</button>
          <button id="close" type="button">Close</button>
        </div>
      </div>
      <div class="viewer-stage"><img id="viewer-image" alt=""></div>
      <div class="viewer-foot">
        <span id="viewer-path"></span>
        <a id="viewer-open" href="">Open original</a>
      </div>
    </div>
  </dialog>
  <script>
    const MANIFEST = {manifest};
    const state = {{ filter: "", kind: "all", sort: "path", visibleImages: [], imageIndex: 0 }};
    const byId = (id) => document.getElementById(id);
    const gallery = byId("gallery");
    const reportsByGroup = new Map();
    for (const report of MANIFEST.reports) {{
      if (!reportsByGroup.has(report.group)) reportsByGroup.set(report.group, []);
      reportsByGroup.get(report.group).push(report);
    }}

    function matches(item) {{
      const text = `${{item.path}} ${{item.group}} ${{item.name}}`.toLowerCase();
      return (state.kind === "all" || item.kind === state.kind) && text.includes(state.filter);
    }}

    function sortedItems() {{
      const items = MANIFEST.items.filter(matches).slice();
      if (state.sort === "modified") items.sort((a, b) => b.modified.localeCompare(a.modified) || a.path.localeCompare(b.path));
      else if (state.sort === "size") items.sort((a, b) => b.size - a.size || a.path.localeCompare(b.path));
      else items.sort((a, b) => a.group.localeCompare(b.group) || a.path.localeCompare(b.path));
      return items;
    }}

    function grouped(items) {{
      const groups = new Map();
      for (const item of items) {{
        if (!groups.has(item.group)) groups.set(item.group, []);
        groups.get(item.group).push(item);
      }}
      return groups;
    }}

    function card(item) {{
      const article = document.createElement("article");
      article.className = "card";
      let media;
      if (item.kind === "video") {{
        media = document.createElement("video");
        media.controls = true;
        media.preload = "metadata";
        media.src = item.path;
      }} else {{
        media = document.createElement("img");
        media.loading = "lazy";
        media.decoding = "async";
        media.src = item.path;
        media.alt = item.path;
        media.addEventListener("click", () => openImage(item.path));
      }}
      media.className = "thumb";
      article.appendChild(media);

      const caption = document.createElement("div");
      caption.className = "caption";
      const name = document.createElement("a");
      name.className = "name";
      name.href = item.path;
      name.textContent = item.name;
      const path = document.createElement("div");
      path.className = "path";
      path.textContent = item.path;
      const stats = document.createElement("div");
      stats.className = "stats";
      stats.innerHTML = `<span>${{item.kind}}</span><span>${{item.size_label}}</span><span>${{item.modified}}</span>`;
      caption.append(name, path, stats);
      article.appendChild(caption);
      return article;
    }}

    function render() {{
      const items = sortedItems();
      state.visibleImages = items.filter((item) => item.kind === "image").map((item) => item.path);
      gallery.replaceChildren();
      if (!items.length) {{
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No matching images or videos.";
        gallery.appendChild(empty);
        return;
      }}
      for (const [group, groupItems] of grouped(items)) {{
        const section = document.createElement("section");
        section.className = "group";
        const head = document.createElement("div");
        head.className = "group-head";
        const h2 = document.createElement("h2");
        h2.textContent = group;
        const links = document.createElement("div");
        links.className = "links";
        const count = document.createElement("span");
        count.className = "pill";
        count.textContent = `${{groupItems.length}} item${{groupItems.length === 1 ? "" : "s"}}`;
        links.appendChild(count);
        for (const report of reportsByGroup.get(group) || []) {{
          const a = document.createElement("a");
          a.href = report.path;
          a.textContent = report.label;
          links.appendChild(a);
        }}
        head.append(h2, links);
        const grid = document.createElement("div");
        grid.className = "grid";
        for (const item of groupItems) grid.appendChild(card(item));
        section.append(head, grid);
        gallery.appendChild(section);
      }}
    }}

    function itemForPath(path) {{
      return MANIFEST.items.find((item) => item.path === path);
    }}

    function openImage(path) {{
      const index = state.visibleImages.indexOf(path);
      state.imageIndex = index >= 0 ? index : 0;
      showCurrentImage();
      byId("viewer").showModal();
    }}

    function showCurrentImage() {{
      const path = state.visibleImages[state.imageIndex];
      const item = itemForPath(path);
      byId("viewer-image").src = path || "";
      byId("viewer-image").alt = path || "";
      byId("viewer-title").textContent = item ? item.name : "";
      byId("viewer-path").textContent = path || "";
      byId("viewer-open").href = path || "";
    }}

    function step(delta) {{
      if (!state.visibleImages.length) return;
      state.imageIndex = (state.imageIndex + delta + state.visibleImages.length) % state.visibleImages.length;
      showCurrentImage();
    }}

    byId("title").textContent = MANIFEST.title;
    byId("meta").textContent = `${{MANIFEST.items.length}} media files from ${{MANIFEST.sourceDir}} | generated ${{MANIFEST.generated}}`;
    byId("search").addEventListener("input", (event) => {{
      state.filter = event.target.value.trim().toLowerCase();
      render();
    }});
    byId("kind").addEventListener("change", (event) => {{
      state.kind = event.target.value;
      render();
    }});
    byId("sort").addEventListener("change", (event) => {{
      state.sort = event.target.value;
      render();
    }});
    byId("prev").addEventListener("click", () => step(-1));
    byId("next").addEventListener("click", () => step(1));
    byId("close").addEventListener("click", () => byId("viewer").close());
    document.addEventListener("keydown", (event) => {{
      if (!byId("viewer").open) return;
      if (event.key === "ArrowLeft") step(-1);
      if (event.key === "ArrowRight") step(1);
      if (event.key === "Escape") byId("viewer").close();
    }});
    render();
  </script>
</body>
</html>
"""


def build_gallery(out_dir: Path, output_path: Path, title: str) -> tuple[Path, int]:
    out_dir = out_dir.resolve()
    output_path = output_path.resolve()
    if not out_dir.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {out_dir}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    items = scan_media(out_dir, output_path)
    reports = scan_reports(out_dir, {item.group for item in items})
    output_path.write_text(html_document(title, items, reports, out_dir), encoding="utf-8")
    return output_path, len(items)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a static HTML gallery for out/ media artifacts.")
    parser.add_argument("--out-dir", default="out", help="Directory to scan for media artifacts")
    parser.add_argument("--output", default="out/gallery.html", help="HTML file to write")
    parser.add_argument("--title", default="Omni Asset Output Gallery", help="Page title")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_path, count = build_gallery(Path(args.out_dir), Path(args.output), args.title)
    print(f"Wrote {output_path} with {count} media files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
