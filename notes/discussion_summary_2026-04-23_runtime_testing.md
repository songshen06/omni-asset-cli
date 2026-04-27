# Runtime Testing Discussion Summary

Date: 2026-04-23

## Context

Current development happens inside WSL Codex, while Isaac Sim is installed on Windows at `C:\isaacsim\`.

The current goal is not a full physics scoring system yet. The goal is to establish a minimal runtime validation path that can later evolve into a stable automated test workflow.

## What Was Confirmed

- The current `physics-hit-test` is no longer an empty scaffold.
- It already performs meaningful work:
  - reads an input USD
  - builds a minimal physics test stage
  - applies static collision to the input asset subtree
  - creates a dynamic rigid box
  - attempts to run simulation through Isaac Sim runtime
  - writes `summary.json`, `runtime_report.json`, and `timeline.csv`
- The current harness is sufficient for first-pass validation of whether the runtime test chain works.
- It is not yet a strict collision-quality validator.

## Current Runtime Constraint

- In the current WSL environment, the bridge from WSL to Windows Isaac Sim runtime is failing.
- The actual probe result shows a WSL/runtime bridge error rather than a harness logic error.
- A new `physics-env` command was added to verify this explicitly before running the full hit test.

## Testing Strategy We Discussed

We separated testing into two layers:

1. Lightweight validation
   - syntax
   - CLI wiring
   - USD authoring
   - artifact generation

2. Runtime integration validation
   - actual Isaac Sim startup
   - simulation stepping
   - physics result output

We also discussed that long term these should ideally run in a dedicated test environment, potentially via self-hosted runners.

## Headless Validation Principles

We agreed that headless validation cannot rely on rendered output.

Instead, result confirmation should rely on:

- `summary.json`
- `runtime_report.json`
- `timeline.csv`

For the current first version, the minimum pass criteria are:

- `asset_loaded == true`
- `static_colliders_applied == true`
- `dynamic_box_created == true`
- `simulation_advanced == true`
- `result == "passed"`

This is enough to prove the runtime chain is functioning.

It is not yet enough to strictly prove collision correctness.

## Human Review Flow

We aligned on a layered human review process:

1. Read `summary.json`
   - overall result
   - checks
   - notes

2. Read `runtime_report.json`
   - input USD
   - asset prim path
   - box prim path
   - box initial position
   - box initial velocity
   - sampling summary
   - final state

3. Only inspect `timeline.csv` when needed
   - suspicious result
   - platform mismatch
   - debugging unstable motion

## Ubuntu Migration Discussion

We discussed that moving development from WSL to native Ubuntu would simplify:

- path handling
- runtime launching
- artifact writing
- consistency between development and runtime testing

However, for now the practical constraint is that development remains in WSL, so the current implementation must support that path first.

## Mini Test Scene Discussion

The file `C:\test\mini_test.usda` was examined.

It already contains:

- a `PhysicsScene`
- a table with collision
- a dynamic box with rigid body and mass APIs

This makes it a useful authored scene, not just a raw asset.

We concluded that this scene is valuable because it is intuitive and visually understandable as a testing template.

## Key Design Decision

We discussed two possible approaches:

1. Generated harness scene
   - code creates a minimal world
   - input USD is treated as the static test asset
   - dynamic box is created by the harness

2. Authored template scene
   - use a scene like `mini_test.usda`
   - preserve the table, layout, and intuitive test semantics
   - inject a target USD asset into a predefined slot

We concluded that these two approaches should be combined, not treated as mutually exclusive.

## Preferred Direction

Preferred direction:

- keep the current generated `physics-hit-test` path
- but evolve toward using `mini_test.usda` as a reusable template scene
- inject a target USD asset into that template instead of always generating the full scene from scratch

This would preserve:

- the intuitive testing setup
- stable scene semantics
- easier human review
- easier regression testing

## Immediate Minimal-Change Plan

For the current phase, the agreed near-term direction is:

- keep development in WSL
- keep Isaac Sim on Windows at `C:\isaacsim\`
- use `physics-env` to verify whether the runtime bridge is functional
- keep `physics-hit-test` as the minimal generated-scene harness
- later add a template-scene-based mode rather than discarding the current harness

## Suggested Future Enhancement

The most natural next extension is a template-scene-based runtime command, conceptually similar to:

```bash
omni-asset-cli physics-hit-test-using-scene <template_scene.usda> <target_asset.usd> --out <dir>
```

This mode would:

- open the authored scene template
- inject a target asset into a predefined slot
- keep the scene layout and test logic stable
- run the simulation
- emit the same structured artifacts

## Current Conclusion

As of 2026-04-23:

- first-pass runtime validation capability exists
- artifact-based headless validation exists
- WSL to Windows Isaac Sim bridge is still the immediate blocker for real runtime execution in the current environment
- `mini_test.usda` should likely become the basis of a future template-scene workflow

## Progress Update

Date: 2026-04-24

The template-scene direction has now been implemented as an extension of the existing `physics-hit-test` command.

New command shape:

```bash
omni-asset-cli physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --replace-prim /World/roomScene/colliders/table \
  --frames 240 \
  --out out/asset_template_hit
```

### What Changed

- `examples/mini_test.usda` was added to the repository as the authored template scene.
- The template scene now includes a fixed injection slot:
  - `/World/TestAssetSlot`
- Template mode defaults to replacing the authored table prim with the target asset:
  - `/World/roomScene/colliders/table`
- Replacement mode now performs default size alignment:
  - reads the original table bbox
  - computes a uniform scale so the target asset fits the table X/Y footprint
  - aligns the target asset bottom to the original table top
- Template mode reuses the authored dynamic rigid body:
  - `/World/boxActor`
- The fixed injection slot remains available when `--replace-prim` is passed as an empty value:
  - `/World/TestAssetSlot`
- The existing generated-scene mode remains available when `--template-scene` is not provided.
- `summary.json`, `runtime_report.json`, and `timeline.csv` remain the standard output artifacts.
- `runtime_report.json` now records template-specific fields such as:
  - `template_scene_path`
  - `asset_slot_path`
- `box_prim_path`
- `fit_mode`
- `fit_scale`
- `replaced_bbox_min`
- `replaced_bbox_max`
- bbox before and after alignment
  - generated working stage path

### Validation Performed

The following non-runtime checks were completed successfully:

- Python compilation:
  - `python3 -m py_compile omni_asset_cli.py omniverse-usd-asset-validator/scripts/run_physics_hit_test.py omniverse-usd-asset-validator/scripts/runtime_physics_harness.py`
- CLI help check:
  - `python3 omni_asset_cli.py physics-hit-test --help`
- Generated harness local blocked-path check:
  - `python3 omniverse-usd-asset-validator/scripts/run_physics_hit_test.py examples/minimal_scene.usda --frames 2 --out out/minimal_scene_generated_local_probe --external-runtime-child`
- Template harness local blocked-path check:
  - `python3 omniverse-usd-asset-validator/scripts/run_physics_hit_test.py examples/minimal_scene.usda --template-scene examples/mini_test.usda --replace-prim /World/roomScene/colliders/table --frames 2 --out out/minimal_scene_replace_table_local_probe --external-runtime-child`

The template local check confirmed:

- `asset_loaded == true`
- `static_colliders_applied == true`
- `dynamic_box_created == true`
- `test_type == "template_scene_dynamic_box_hits_asset"`
- `replaced_prim_path == "/World/roomScene/colliders/table"`
- `fit_mode == "uniform_footprint_to_replaced_prim"`

An additional local fit check was run with `examples/boat_test/boat.usd` because `examples/minimal_scene.usda` has no geometry bbox. The boat asset was scaled to the table footprint:

- original table bbox: approximately `[-100, -50, -75]` to `[100, 50, 0]`
- fit scale: approximately `82.88`
- fitted asset bbox: approximately `[-100, -45.5, 0]` to `[100, 45.5, 69.6]`

### Current Runtime Status

Full Isaac Sim simulation has still not been verified in the current WSL environment.

The known blocker remains:

- WSL to Windows Isaac Sim runtime bridge failure
- observed error includes:
  - `WSL ... UtilBindVsockAnyPort ... socket failed`

This is still considered an environment/runtime bridge issue, not evidence that the template harness logic is invalid.

### Current Interpretation

As of 2026-04-24:

- generated-scene mode and template-scene mode now coexist
- `mini_test.usda` has moved from future direction to implemented template fixture
- template mode now supports the intended table-replacement test semantics
- v1 pass criteria still prove runtime-chain execution, not strict collision-quality correctness
- the next meaningful milestone is running template mode inside a working Isaac Sim runtime environment and inspecting non-empty `timeline.csv`
