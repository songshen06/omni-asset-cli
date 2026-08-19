---
name: omniverse-usd-asset-validator
description: Validate OpenUSD or USDZ assets with NVIDIA Omniverse Asset Validator. Use this skill when the user wants to validate a USD asset, map natural-language validation requests into deterministic CLI arguments, or explain validation results for human and agent workflows.
---

# Omniverse USD Asset Validator

Use this skill to validate USD assets, map natural-language requests into deterministic commands, and return outputs that work well for both human operators and AI agents. The current Stage 1 path is static furniture, furnishings, and decorative props.

## Default Entry Point

Prefer the installed `omni-asset-cli`.

If the console script is not installed yet, fall back to:

```bash
python3 omni_asset_cli.py ...
```

## Foundation Profile Deployment Boundary

Foundation-backed work requires a separately pinned Foundation checkout; it is
not installed by `.[validator]`. For the current physics-prop/articulated-cart
path, deploy Foundation `v2026.04.1` with Python 3.12 and
`simready-validate==2026.4.8`, then use `Prop-Robotics-Physx v1.0.0` through
`foundation-validate --official-cli --shadow`. This skill owns the profile
execution, evidence normalization, native PhysX visual evidence, and Isaac Sim
Docker contact validation. The inspector only performs controlled candidate
repair from findings and does not itself declare Foundation conformance. See
`DEPLOYMENT.md` section 4a before running profile-dependent commands.

## Workflow

1. Identify the target asset.
2. Check the runtime first, especially Python, `omniverse-asset-validator`, and `omni_asset_validate`.
3. If the user starts from natural language, use `map` or `validate-from-prompt`.
4. Use synchronous `validate` by default for single assets.
5. Use `validate-async` only when you explicitly need to observe timeout behavior from the raw CLI path.

## Recommended Commands

Check the environment:

```bash
omni-asset-cli env
```

Run Stage 1 furniture/prop validation:

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
```

Legacy profile validation remains available:

```bash
omni-asset-cli validate path/to/asset.usd --profile stage1-furniture
omni-asset-cli validate path/to/asset.usd --profile static
omni-asset-cli validate path/to/asset.usd --profile collidable
omni-asset-cli validate path/to/asset.usd --profile movable
```

Map natural language:

```bash
omni-asset-cli map path/to/asset.usd "check references"
omni-asset-cli map path/to/asset.usd "validate this as static furniture and decor props"
omni-asset-cli map path/to/asset.usd "check Isaac Sim structure"
```

Map and execute directly:

```bash
omni-asset-cli validate-from-prompt path/to/asset.usd "validate this as static furniture and decor props"
```

Run the Stage 1 top-drop runtime check when a physics runtime is available:

```bash
omni-asset-cli physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --out out/asset_top_drop \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

Audit primitive collider schema without modifying the asset:

```bash
omni-asset-cli physics-collider-audit path/to/asset.usd \
  --out out/asset_collider_audit
```

`primitive_collider_audit.json` contains `RB.COL.002` safe repair contracts for
non-mesh primitive colliders that incorrectly carry `PhysicsMeshCollisionAPI`
and `physics:approximation`. This command is intentionally read-only. Pass its
JSON to `usd-simready-inspector collider-repair` to export a repair candidate,
then re-run this audit against that candidate. A clean re-audit only confirms
the authoring/schema condition; runtime collision proof still requires Isaac
Sim Docker contact evidence.

The same audit always runs `RB.COL.003`: a manual-review check for Mesh
colliders authored as `convexHull` or `convexDecomposition`. It detects that a
runtime-cooked convex shape may bridge visual concavities; it does not pretend
to measure the final cooked geometry from static USD alone. Create an
explainable artifact by passing the audit and optional three-view output to:

```bash
omni-asset-cli physics-convex-collider-report \
  --audit out/asset_collider_audit/primitive_collider_audit.json \
  --render-dir out/asset_physx_three_view \
  --upstream-profile Prop-Robotics-Physx \
  --expected-mesh-approximation sdf \
  --out out/asset_convex_collider_analysis.html
```

Treat the profile comparison as approximation authoring conformance only. Keep
`RB.COL.003` separate: it is local evidence that the selected convex cooking
strategy may deviate from visual geometry and requires native PhysX display or
targeted runtime probe evidence.

Capture the native Kit viewport collider display for review:

```bash
omni-asset-cli physics-collider-view path/to/asset.usd \
  --out out/asset_physics_colliders \
  --physics-colliders selected \
  --runtime-docker-container isaac-sim
```

This creates `orbit_frames/frame_0000.png` using the same state as Kit
**Physics > Colliders > Selected** and writes a manifest with the selected
`CollisionAPI` paths. It is a visual authoring diagnostic; use a Docker
contact test for runtime collision acceptance.

For the standard human/agent comparison artifact, use the fixed three-view
command instead of manually combining overlay flags:

```bash
omni-asset-cli physics-collider-three-view path/to/asset.usd \
  --out out/asset_physx_three_view \
  --runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0
```

It always captures front, side, and top PNGs in `orbit_frames/`: neutral grey
visual mesh plus Kit's native **Physics > Colliders > All** green display.
This is visual authoring evidence only, not a contact test.

## Natural-Language Handling Rules

- Default to read-only validation and do not add `--fix` unless the user asks.
- Keep the default rules unless the user explicitly narrows the scope.
- Map furniture, furnishings, decor props, Stage 1, 家具, 摆件, 装饰道具 prompts to `--profile stage1-furniture`.
- For Stage 1 runtime checks, use Linux + Isaac Sim Docker only. Do not substitute host Python or non-container runtimes for authoritative physics results.
- Prefer `--runtime-docker-container isaac-sim --docker-workspace /workspace/omni-asset-cli` when a mounted Isaac Sim container is available. Use `--runtime-docker-image nvcr.io/nvidia/isaac-sim:5.1.0` for one-shot container runs.
- Use `--runtime-docker-preflight restart` for a clean default, `auto` to restart only when stale Kit/Isaac processes exist, `check` to block on stale processes, and `skip` only when explicitly requested.
- For Docker runtime checks, make the input asset container-readable. Prefer repository paths; for assets elsewhere under the host home directory, stage the package directory under `out/runtime_inputs/` or rely on the runtime harness auto-staging and report the staged path.
- For Stage 1 runtime checks, prefer `--hit-mode top-drop --size-policy preserve` so the asset keeps its real bbox and the box is aimed above the bbox center.
- Use `--placement-mode replace-table` for furniture/support surfaces, `tabletop` for small decor props placed on the template table, and `replace-box` only when debugging the input asset as the falling dynamic actor.
- Use `--asset-rotation-y-deg` or `--asset-rotation-z-deg` when orientation correction is needed before collecting runtime evidence.
- For rendered physics bbox evidence, use the existing runtime render path with `--render-frames --render-physics-bboxes`. The harness writes bbox curves only to the Kit session layer and clears them before shutdown; do not create or save debug prims in the source USD.
- For `RB.COL.002` primitive-collider ambiguity, run `physics-collider-audit` before runtime work. Do not repair in this validator package: hand its finding JSON to `~/usd-simready-inspector/apply_primitive_collider_repair.py`, require a new output USD, then re-audit the candidate.
- For repeatable collider comparison, prefer `physics-collider-three-view`; do not replace its native green PhysX overlay with an inferred AABB or synthetic proxy wireframe.
- Use `--render-physics-bbox-fallback-default-prim` only as a capture-path debug aid when no collider paths exist. Do not describe fallback default-prim bbox as physics collider evidence.
- For multi-camera PNG/MP4 evidence, add repeated `--render-camera-preset` values plus `--render-video`. Prefer `--render-video-style asset-table-drop` for the validated falling-asset visual style, but keep `summary.json` and `runtime_report.json` PhysX contact evidence as the authoritative collision result.
- For customer reports, only attach videos from the same workflow output directory as the accepted runtime JSON, or from a documented retry using the same input USD and same SimReady output USD. Never substitute synthetic placeholder videos, old videos from another run, or videos for a different asset. If the render log stops at `capture-first-frame-start` with `cudaErrorNoDevice`, keep the contact evidence and regenerate video via a stable hit-test host-encode retry or rerun on a CUDA-capable render container.
- For customer demos, prefer `stage1-runtime` with `--evidence-preset standard`, `--contact-timeout-seconds 900`, and a shorter `--visual-timeout-seconds` such as `180`. The contact pass writes required proof under `OUT/contact_evidence/`; the visual pass is optional and may time out without invalidating the contact result.
- Use `--render-backend replicator` by default. Tune output with `--render-width`, `--render-height`, `--render-rt-subframes`, `--render-wait-updates`, `--render-video-fps`, `--render-video-crf`, `--render-material-mode`, and asset-table-drop camera options when the user asks for specific visual evidence.
- Use `render_asset_setup_orbit.py` for setup/orbit inspection renders and `check_stage_mdl_load.py` for Isaac Sim stage/MDL load probes.
- Fall back to standard validation if the prompt does not match a specific rule.
- Prefer `KindChecker` only when the user explicitly asks about Isaac Sim, SimReady, hierarchy, or component semantics.

## Response Pattern

Include:

- `Target`
- `Command`
- `Result`
- `Next step`

If JSON or Markdown output was produced, mention the output path as well.

## Environment Contract

- Recommended Python: 3.10
- Acceptable range: 3.10 to 3.12
- Recommended install command:

```bash
python3 -m pip install --no-build-isolation -e ".[validator]"
```

## Long-Running Policy

- Default structured validation: `omni-asset-cli validate`
- CLI timeout observation: `omni-asset-cli validate-async`

Operational states:

- `completed`
- `timed_out`
- `blocked`

## References

- `references/environment-and-setup.md`
- `references/cli-mapping.md`
- `references/human-operator-guide.md`
- `references/natural-language-to-args.md`
- `references/kind-checker-explained.md`
- `references/agent-bootstrap-deployment.md`
- `references/test-environment-deployment.md`
