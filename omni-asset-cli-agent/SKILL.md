---
name: omni-asset-cli-agent
description: Guide agents to use this repository's omni_asset_cli.py tools for OpenUSD asset validation, mesh quality checks, Isaac Sim Docker physics hit tests, SimReady flywheel runs, topology debug renders, and report/artifact interpretation. Use when a user asks an agent to inspect USD/USDZ/USDA/USDC assets, validate mesh/material/reference quality, produce human-readable reports, run runtime physics evidence, or explain outputs from this CLI.
---

# Omni Asset CLI Agent

## Operating Rules

Work from the repository root. Prefer the project virtual environment when it exists:

```bash
.venv/bin/python omni_asset_cli.py ...
```

If `.venv` is missing or lacks `omni.asset_validator`, use `python3` only after running the env check. Keep generated artifacts under `out/`. Do not modify source assets unless the user explicitly asks for repair. Do not commit or push `out/` artifacts unless explicitly requested.

For assets outside the repository but under `/home`, stage the whole asset package into `out/runtime_inputs/<package>/` before Docker runtime or render work so textures and sidecars are inside the repo mount.

## Command Selection

Use these entry points:

- Environment check: `.venv/bin/python omni_asset_cli.py env`
- Static validator: `.venv/bin/python omni_asset_cli.py validate <asset> --profile stage1-furniture`
- Mesh/collision preflight: `.venv/bin/python omni_asset_cli.py validate <asset> --profile collidable`
- Natural language mapping: `.venv/bin/python omni_asset_cli.py map <asset> "check mesh topology"`
- Isaac Sim runtime readiness: `python3 omni_asset_cli.py physics-env --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0`
- Runtime top-drop hit test: `python3 omni_asset_cli.py physics-hit-test <asset> --template-scene examples/mini_test.usda --placement-mode replace-table --hit-mode top-drop --size-policy preserve --frames 240 --out out/<name>_hit --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0`
- SimReady flywheel: `python3 omni_asset_cli.py simready-flywheel <asset> --out out/<name>_flywheel --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0`
- Topology issue render: `.venv/bin/python omniverse-usd-asset-validator/scripts/render_mesh_topology_issues.py <staged_asset> --out out/<name>_mesh_wire_render --mesh-path <mesh_prim_path>`

## Validation Profiles

Use `stage1-furniture` by default for static furniture, furnishings, decor props, and Stage 1 SimReady checks. It covers entry metadata, default prim, dependencies, materials, topology, manifold, zero-area faces, normals, weldable points, and extents.

Use `collidable` when the user asks for mesh-level checks, physics/collider readiness, topology health, or "can this be used for collision?" It focuses on references plus `ValidateTopologyChecker`, `ManifoldChecker`, `ZeroAreaFaceChecker`, `NormalsValidChecker`, `WeldChecker`, and `ExtentsChecker`.

Use `static` only for display/background assets where mesh quality is not the focus. Use `movable` for robot interaction, grasping, moving, or articulated workflows.

## Output Expectations

`validate` writes:

- terminal summary
- JSON report via `--output-json`
- Markdown report via `--output-md`

Always surface these fields in the user-facing summary:

- `validation_status`
- `summary.issue_count`
- `summary.severity_counts`
- `summary.rule_counts`
- top issue rules and locations
- generated report paths

Each JSON issue includes `message`, `severity`, `rule`, `at`, `suggestion`, `requirement`, `code`, `tags`, and `explanation`. The Markdown report includes issue explanations and suggested fixes.

## Mesh Topology Debug Render

When the user wants a picture of mesh topology issues, run the topology render script against a staged asset:

```bash
mkdir -p out/runtime_inputs/<package>
cp -a /home/<user>/<package>/. out/runtime_inputs/<package>/
.venv/bin/python omniverse-usd-asset-validator/scripts/render_mesh_topology_issues.py \
  out/runtime_inputs/<package>/<asset>.usd \
  --out out/<asset>_mesh_wire_render \
  --mesh-path /path/to/mesh
```

The script creates:

- `<asset>.topology_wire.png`
- `<asset>.topology_debug.usda`
- `topology_render_summary.json`
- `topology_render_summary.md`
- `topology_render_summary.zh.md`

The red overlay marks faces and edges adjacent to vertices that match the validator-compatible `ManifoldChecker` definition. By default the original source asset is hidden so the issue overlay remains readable. Use `--show-source-asset` only when the user wants context behind the overlay.

For non-manifold interpretation, distinguish:

- `non_manifold_edge_count > 0`: an edge is shared by more than two faces.
- `non_manifold_vertex_count > 0`: faces around a vertex do not form one clean connected fan.

If `non_manifold_edge_count == 0` and vertices are nonzero, explain that the issue is disconnected face fans around shared vertices, often from duplicate shells, bad welds, internal faces, overlapping faces, or point-only contacts.

## Isaac Sim Runtime Policy

Authoritative runtime physics validation uses Linux + Isaac Sim Docker only. Start with:

```bash
python3 omni_asset_cli.py physics-env --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

For top-drop tests, prefer PhysX contact evidence:

- Strong pass: `checks.contact_report_detected == true` and `contact_evidence_level == "detected"`
- Weak evidence: motion-only inference

For rendered physics bbox evidence, stay inside `physics-hit-test` and add:

```bash
--render-frames --render-physics-bboxes
```

Use `--render-physics-bbox-fallback-default-prim` only for capture debugging when no collider paths exist. Do not report fallback bbox output as physics collider evidence.

## Report Style

Keep final summaries short and artifact-oriented:

- State pass/fail/blocked.
- Separate validator failures from environment failures.
- Mention missing dependencies before mesh cleanup if both exist.
- Include exact generated paths.
- Explain non-manifold and weld issues in practical terms for DCC repair.
- For failures, propose the next concrete command to rerun after repair.
