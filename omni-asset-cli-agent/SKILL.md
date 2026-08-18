---
name: omni-asset-cli-agent
description: Guide agents to use this repository's omni_asset_cli.py tools for OpenUSD asset validation, mesh quality checks, primitive-collider schema audits, Isaac Sim Docker physics hit tests, SimReady flywheel runs, topology debug renders, and report/artifact interpretation. Use when a user asks an agent to inspect USD/USDZ/USDA/USDC assets, validate mesh/material/reference quality, detect collider schema ambiguity, produce human-readable reports, run runtime physics evidence, or explain outputs from this CLI.
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
- Primitive-collider schema audit (read-only): `.venv/bin/python omni_asset_cli.py physics-collider-audit <asset> --out out/<name>_collider_audit`
- Natural language mapping: `.venv/bin/python omni_asset_cli.py map <asset> "check mesh topology"`
- Isaac Sim runtime readiness, preferred in this workspace: `python3 omni_asset_cli.py physics-env --runtime-docker-container isaac-sim`
- Isaac Sim runtime readiness by image: `python3 omni_asset_cli.py physics-env --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0`
- Fixed Stage 1 runtime workflow: `python3 omni_asset_cli.py stage1-runtime <asset> --out out/<name>_stage1_runtime`
- Runtime top-drop hit test: `python3 omni_asset_cli.py physics-hit-test <asset> --template-scene examples/mini_test.usda --placement-mode replace-table --hit-mode top-drop --size-policy preserve --frames 240 --out out/<name>_hit --runtime-docker-container isaac-sim --docker-workspace /workspace/omni-asset-cli`
- SimReady flywheel: `python3 omni_asset_cli.py simready-flywheel <asset> --out out/<name>_flywheel --runtime-docker-container isaac-sim --docker-workspace /workspace/omni-asset-cli`
- Topology issue render: `.venv/bin/python omniverse-usd-asset-validator/scripts/render_mesh_topology_issues.py <staged_asset> --out out/<name>_mesh_wire_render --mesh-path <mesh_prim_path>`
- Asset setup orbit render: `python3 omniverse-usd-asset-validator/scripts/render_asset_setup_orbit.py <asset> --out out/<name>_setup_orbit`
- Isaac Sim MDL load probe: `python3 omniverse-usd-asset-validator/scripts/check_stage_mdl_load.py <stage>`

## Primitive Collider Schema Audit And Repair Handoff

For `RB.COL.002`, this CLI is the **detector and revalidator**, not the repair
writer. The audit identifies collision prims that are not `UsdGeom.Mesh` but
still carry `PhysicsMeshCollisionAPI` and `physics:approximation`. Such schema
is ambiguous on primitive colliders and can mislead downstream physics tools.

Run the read-only audit first:

```bash
.venv/bin/python omni_asset_cli.py physics-collider-audit INPUT_USD \
  --out out/<name>_collider_audit
```

The command writes `primitive_collider_audit.json`. A conflict is an expected
nonzero audit result; report the JSON path and finding count instead of treating
it as a CLI crash. Do **not** modify the source USD from this repository.

Hand the JSON to `usd-simready-inspector`, which owns the controlled candidate
export:

```bash
cd ~/usd-simready-inspector
.venv/bin/python usd_simready_cli.py collider-repair INPUT_USD \
  --findings /absolute/path/primitive_collider_audit.json \
  --output OUTPUT_CANDIDATE.usda \
  --report OUTPUT_CANDIDATE.collider_repair.json
```

That repair accepts only safe findings owned by `usd-simready-inspector`; it
creates a new USD and removes only `PhysicsMeshCollisionAPI` plus
`physics:approximation` from the selected non-mesh colliders. It preserves
`PhysicsCollisionAPI`, geometry, transforms, materials, rigid bodies, and
joints. Re-run this CLI's audit on the candidate. A zero finding count proves
the schema repair only; it is not Isaac Sim contact evidence.

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

Authoritative runtime physics validation uses Linux + Isaac Sim Docker only. In this workspace, first try the running container path:

```bash
python3 omni_asset_cli.py physics-env --runtime-docker-container isaac-sim
```

If no container is available, use the Isaac Sim image:

```bash
python3 omni_asset_cli.py physics-env --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

Runtime Docker options:

- Prefer `--runtime-docker-container isaac-sim --docker-workspace /workspace/omni-asset-cli` when a mounted container is already running.
- Use `--runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0` when the CLI should launch a one-shot container.
- `--runtime-docker-preflight restart` is the CLI default for clean container execution. Use `auto` to restart only when stale Isaac/Kit processes are detected, `check` to block instead of restarting, and `skip` only when the user explicitly wants no preflight.
- Keep `--no-headless` off unless the user has configured a visible Isaac Sim session. The normal runtime path uses `SimulationApp({"headless": True})`.

Before choosing a runtime test, classify the asset from its filename, prompt
metadata, inspect report shape hints, dimensions, and a quick render when
available. Do not reuse one placement mode for a whole batch when the assets
are different object classes.

Stage 1 placement decision:

- Furniture that replaces a table or support object: use `--placement-mode replace-table`. This includes chairs, tables, desks, stools, benches, cabinets, shelves, sofas, and larger furniture. The asset should replace the template table target, then the box should top-drop onto the replaced asset.
- Small tabletop props: use `--placement-mode tabletop`. This includes cups, bottles, cans, vases, decor props, small tools, toys, and objects that should sit on an existing table.
- Round sports balls and similar props: usually use `--placement-mode tabletop` for prop-on-surface validation unless the user explicitly asks to test the asset as the falling dynamic actor.
- Dynamic actor debugging: use `--placement-mode replace-box` only when the user wants the input asset to be the falling object.
- If classification is uncertain, inspect or render first, state the assumption, and pick the most conservative placement for the asset's likely role. Re-run with the corrected placement when visual evidence or user feedback identifies the object class.

Stage 1 placement options:

- `--placement-mode replace-table`: furniture and larger support surfaces; replaces the template table target.
- `--placement-mode tabletop`: cups, decor props, and small objects; keeps the template table and places the asset on top.
- `--placement-mode replace-box`: use the input asset as the falling actor for debugging dynamic asset behavior.
- Add `--asset-rotation-y-deg` or `--asset-rotation-z-deg` only when orientation needs correction before runtime evidence is collected.

For top-drop tests, prefer PhysX contact evidence:

- Strong pass: `checks.contact_report_detected == true` and `contact_evidence_level == "detected"`
- Weak evidence: motion-only inference
- Do not count debug/default-prim/fallback bbox overlays as real collider contact evidence. Strong contact should hit the asset subtree or another registered real collider path. If contact only hits a guide bbox, treat it as a test-logic issue and rerun with the correct placement or harness settings.

When the user asks for the standard repeated Stage 1 runtime check, prefer
`stage1-runtime` over manually running `physics-env` and `physics-hit-test`.
It preserves the expanded commands in `workflow_commands.json`, writes logs for
Docker access, preflight, contact, and visual steps, and summarizes
pass/fail/contact evidence in `workflow_report.json`.

For reliable customer demos, treat PhysX contact report as the required proof
and video as optional presentation material. The `standard` evidence preset
runs a contact-only pass first and stores the authoritative files under
`OUT/contact_evidence/`. A strong pass requires
`checks.contact_report_detected == true` and
`contact_evidence_level == "detected"`.

Recommended stable demo command:

```bash
python3 omni_asset_cli.py stage1-runtime <asset> \
  --out out/<name>_stage1_runtime \
  --runtime-docker-container isaac-sim \
  --runtime-docker-preflight auto \
  --evidence-preset standard \
  --contact-timeout-seconds 900 \
  --visual-timeout-seconds 180
```

If the visual pass times out, use `OUT/contact_evidence/summary.json` and
`OUT/contact_evidence/runtime_report.json` for downstream customer reports.
Use `--evidence-preset contact-only` for the most stable structured-evidence
run when video is not required.

For rendered physics bbox evidence, stay inside `physics-hit-test` and add:

```bash
--render-frames --render-physics-bboxes
```

Use `--render-physics-bbox-fallback-default-prim` only for capture debugging when no collider paths exist. Do not report fallback bbox output as physics collider evidence.

For multi-camera rendered evidence or mp4 output, keep the same `physics-hit-test` command and add camera/video options:

```bash
--render-video \
--render-video-style asset-table-drop \
--render-camera-preset front \
--render-camera-preset side \
--render-camera-preset top \
--render-every-n-frames 2 \
--render-video-fps 30
```

Rendered PNGs are written under `OUT/render_frames/<camera>/` when camera presets are specified; mp4 files are written under `OUT/render_videos/`.
When the user wants the video to match the validated standalone falling-asset renderer, add `--render-video-style asset-table-drop`; keep using the hit-test `summary.json` and `runtime_report.json` for authoritative PhysX contact evidence.

Rendered evidence options:

- `--render-video-style hit-test` captures the same runtime hit-test scene.
- `--render-video-style asset-table-drop` delegates to `render_asset_table_drop.py` for the standalone falling-asset video style.
- `--render-camera-preset` accepts repeated or comma-separated values such as `front`, `side`, `top`, `iso`, and `all`.
- `--render-backend replicator` is the default and preferred for frame/video evidence; use `viewport` only when debugging capture compatibility.
- Use `--render-width`, `--render-height`, `--render-rt-subframes`, and `--render-wait-updates` to tune capture quality and write reliability.
- Use `--render-video-fps` and `--render-video-crf` for mp4 timing and compression control.
- Use `--render-material-mode material`, `transparent`, or `all` with `asset-table-drop` videos when the user wants material and translucent-bbox variants.
- Use `--render-camera-distance-scale`, `--render-camera-focal-length`, and `--render-camera-elevation-deg` to tune `asset-table-drop` camera framing.

Helper render scripts:

- `render_asset_table_drop.py` creates standalone falling-asset video evidence. Use it directly only when the user asks for visual-only evidence without running the full hit-test wrapper.
- `render_asset_setup_orbit.py` creates setup/orbit frames with bbox, collider bbox, and center marker overlays for asset inspection.
- `check_stage_mdl_load.py` opens a stage inside Isaac Sim long enough to catch MDL/material loading failures.

## Report Style

Keep final summaries short and artifact-oriented:

- State pass/fail/blocked.
- Separate validator failures from environment failures.
- Mention missing dependencies before mesh cleanup if both exist.
- Include exact generated paths.
- Explain non-manifold and weld issues in practical terms for DCC repair.
- For failures, propose the next concrete command to rerun after repair.
