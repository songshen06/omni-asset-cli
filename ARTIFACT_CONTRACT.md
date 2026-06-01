# Artifact Contract

This document defines the canonical artifact model for jobs produced by
`omni-asset-cli` and `omni_asset_service`.

## Evidence Strength

PhysX contact report evidence is the strongest runtime collision evidence.
`checks.contact_report_detected == true` with
`contact_evidence_level == "detected"` in `summary.json`, supported by contact
details in `runtime_report.json`, is stronger than bbox overlap, rendered-frame
inspection, or motion-only inference.

Rendered frames, videos, and physics bbox overlays are visual evidence. They are
useful for review and debugging, but they must not override structured PhysX
contact report evidence.

## Canonical Artifacts

### Uploaded/source asset

Role: authoritative input.

The uploaded/source asset is the user-provided USD asset or asset package. It
may be a single `.usd`, `.usda`, `.usdc`, or a zip/package containing textures,
MDL files, GLB sidecars, and relative dependencies. The service records source
metadata such as original filename, entrypoint path, size, checksum, tenant,
project, and `asset_id`.

Consumers should use this as the provenance anchor for all derived artifacts.

### Validator JSON report

Role: authoritative mesh/static validation report.

The validator JSON report is written by `validate` through
`run_sync_validation.py`. In service jobs it is currently stored as
`summary.json` for mesh validation jobs. It contains validation status,
execution status, issue counts, severity counts, rule counts, individual
issues, and optional error information.

Consumers should use this report to classify mesh validation outcomes and
identify rules that may affect physics collision behavior.

### Validator Markdown report

Role: human-readable validation report.

The Markdown report, commonly `validation.md`, is a readable companion to the
validator JSON report. It is useful for review, sharing, and pull request
attachments. It is not the authoritative source for automated status
classification when the JSON report is available.

### Runtime `summary.json`

Role: authoritative runtime status summary.

`summary.json` is the first structured runtime artifact a consumer should read
for `physics-hit-test` jobs. It records the high-level result, selected checks,
contact evidence level, and runtime failure summaries.

For collision pass/fail classification, `summary.json` is authoritative at the
status level. A pass requires strong contact evidence, currently
`checks.contact_report_detected == true` and
`contact_evidence_level == "detected"`.

### `runtime_report.json`

Role: authoritative detailed runtime evidence.

`runtime_report.json` is the detailed physics evidence record. It contains the
runtime configuration, final state, hit analysis, contact report details, actor
or collider paths, and diagnostic context. It should be used to explain why a
runtime check passed, failed, or was blocked.

When `summary.json` and `runtime_report.json` disagree, treat that as a report
normalization defect. Do not silently prefer rendered media over either
structured report.

### `timeline.csv`

Role: supporting runtime trace.

`timeline.csv` is a frame-by-frame trace from the runtime harness. It is useful
for debugging timing, motion, contact onset, placement, and scale issues. It is
not the primary status source.

Consumers should inspect it after `summary.json` and `runtime_report.json`, or
when diagnosing runtime failures.

### Rendered frames and videos

Role: visual evidence.

Rendered PNG/JPEG frames and MP4 videos show what happened in the test scene.
They are intended for human review, portal display, gallery generation, and
agent summaries. Multi-camera rendered evidence may appear under directories
such as `render_frames/` and `render_videos/`.

Rendered media is not authoritative for collision status. It may support a
report, reveal suspicious placement or scaling, or help reproduce an issue, but
it must not be treated as stronger than PhysX contact report evidence.

### Process log

Role: execution/debug trace.

`process.json` captures subprocess return code, stdout, stderr, and timeout
details for service jobs. It is debug-only unless no structured report was
produced. In missing-report or timeout cases, it helps distinguish environment
failure, command failure, and runtime crash.

Process output must not become the canonical product report when JSON reports
exist.

### Future `manifest.json`

Role: portal and agent index.

`manifest.json` is a future-facing index that should reference the canonical
asset, job, reports, evidence, videos, thumbnails, issues, and fix plan
placeholder. It should not replace `summary.json`, validator JSON,
`runtime_report.json`, or `timeline.csv`; instead it should point to them and
summarize their stable fields.

See `docs/MANIFEST_SCHEMA.md`.

## Artifact Kinds

The service currently records artifact kinds from filenames and extensions:

- `summary`: `summary.json`
- `runtime_report`: `runtime_report.json`
- `timeline`: `.csv` files
- `image`: `.png`, `.jpg`, and `.jpeg` files
- `json`: other JSON files
- `artifact`: all other files

Future artifact registration should move to a core artifact registry so every
new artifact kind has a documented role and display expectation.

## Classification Rules

- Mesh validation jobs classify from validator JSON, not Markdown.
- Collision jobs classify from runtime `summary.json`, with detailed support
  from `runtime_report.json`.
- Runtime `blocked` means the check could not produce valid evidence, usually
  due to environment, asset readability, placement, scale, or authoring
  preconditions.
- Runtime `failed` means the run completed but did not produce strong enough
  collision evidence.
- Runtime `error` means the worker or subprocess failed to produce the expected
  structured report.
- Motion-only inference and bbox evidence can support diagnosis but should not
  produce a collision pass without contact report evidence.
