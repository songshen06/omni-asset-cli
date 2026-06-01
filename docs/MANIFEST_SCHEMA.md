# Manifest Schema

`manifest.json` is a future-facing portal and agent contract. This document is
documentation only; the current service does not require manifest generation.

The manifest should be an index over existing canonical artifacts, not a
replacement for validator JSON, runtime `summary.json`, `runtime_report.json`,
or `timeline.csv`.

## Top-Level Shape

```json
{
  "schema_version": "0.1",
  "asset_id": "asset_...",
  "job_id": "job_...",
  "test_type": "collision",
  "status": "passed",
  "input": {},
  "reports": [],
  "evidence": [],
  "videos": [],
  "thumbnails": [],
  "issues": [],
  "fix_plan": null,
  "created_at": "2026-05-28T00:00:00+00:00",
  "updated_at": "2026-05-28T00:00:00+00:00"
}
```

## Fields

### `schema_version`

String manifest schema version. Start with `"0.1"` until the portal contract is
implemented.

### `asset_id`

Stable asset identifier from the service asset record.

### `job_id`

Stable job identifier from the service job record.

### `test_type`

The job type. Current expected values:

- `mesh`: OpenUSD mesh/static validation through Asset Validator.
- `collision`: Isaac Sim Docker-backed `physics-hit-test` evidence generation.

### `status`

Stable job status. Expected values match the service job lifecycle:

- `queued`
- `running`
- `passed`
- `failed`
- `blocked`
- `error`
- `canceled`

### `input`

Object describing the uploaded/source asset and relevant request parameters.

Recommended fields:

```json
{
  "original_filename": "chair.usd",
  "entrypoint_path": "chair.usd",
  "sha256": "...",
  "size": 12345,
  "metadata": {
    "profile": "stage1-furniture",
    "template_scene": "examples/mini_test.usda",
    "placement_mode": "replace-table",
    "hit_mode": "top-drop",
    "size_policy": "preserve",
    "frames": 240
  }
}
```

`metadata` should contain request fields that help reproduce the job. It should
not duplicate full runtime reports.

### `reports`

Array of structured and human-readable reports.

Recommended item shape:

```json
{
  "kind": "summary",
  "filename": "summary.json",
  "content_type": "application/json",
  "href": "artifacts/artifact_...",
  "authoritative": true
}
```

Expected report kinds:

- `validator_json`: authoritative mesh/static validation report.
- `validator_markdown`: human-readable validation report.
- `summary`: authoritative runtime status summary for collision jobs.
- `runtime_report`: authoritative detailed runtime physics evidence.
- `timeline`: supporting frame trace.
- `process_log`: debug execution trace.

### `evidence`

Array of non-video evidence artifacts, especially rendered frames and selected
debug outputs.

Recommended item shape:

```json
{
  "kind": "rendered_frame",
  "filename": "render_frames/front/frame_0020.png",
  "content_type": "image/png",
  "href": "artifacts/artifact_...",
  "camera": "front",
  "role": "visual_evidence"
}
```

Allowed roles:

- `authoritative`: structured reports only.
- `visual_evidence`: rendered frames and thumbnails.
- `supporting_trace`: timeline-style traces.
- `debug_only`: process logs, temporary bbox fallback captures, or raw tool
  diagnostics.

Physics bbox overlays are visual/debug evidence. They must not be represented
as stronger than PhysX contact report evidence.

### `videos`

Array of rendered video artifacts.

Recommended item shape:

```json
{
  "kind": "rendered_video",
  "filename": "render_videos/front.mp4",
  "content_type": "video/mp4",
  "href": "artifacts/artifact_...",
  "camera": "front",
  "style": "asset-table-drop",
  "role": "visual_evidence"
}
```

Videos are visual evidence only.

### `thumbnails`

Array of portal preview images.

Recommended item shape:

```json
{
  "filename": "thumbnails/front.png",
  "content_type": "image/png",
  "href": "artifacts/artifact_...",
  "source": "render_frames/front/frame_0020.png"
}
```

Thumbnails are presentation artifacts. They should never be used for status
classification.

### `issues`

Array of normalized issues for portal display and agent summaries.

Recommended item shape:

```json
{
  "source": "validator_json",
  "severity": "FAILURE",
  "rule": "ValidateTopologyChecker",
  "message": "Invalid topology",
  "affects_physics": true,
  "artifact": "summary.json"
}
```

For collision jobs, issues may also describe blocked runtime setup, missing
contact report evidence, placement problems, scale problems, or unreadable
asset dependencies.

### `fix_plan`

Placeholder for future repair guidance. It may be `null` until repair planning
is implemented.

Future shape:

```json
{
  "status": "not_started",
  "items": []
}
```

### `created_at` and `updated_at`

ISO 8601 timestamps. They should be generated in UTC and updated when the
manifest is regenerated or artifact references change.

## Invariants

- `manifest.json` must reference canonical artifacts instead of embedding full
  reports.
- The `status` field must match the service job status.
- Collision `passed` must be backed by `summary.json` contact report evidence,
  not only video, bbox, or motion evidence.
- Every artifact reference should include enough metadata for portal display:
  kind, filename, content type, href, and role.
- Manifest generation should be deterministic for the same job artifacts.
