# Testing

This project intentionally separates host-safe tests from Isaac Sim runtime
validation.

Host Python is responsible for CLI/API orchestration, storage, job state, and
artifact bookkeeping. Isaac Sim and `omni.*` Python modules are runtime
dependencies that belong inside Isaac Sim Docker, not the host virtual
environment.

## Host-Safe Validation

Run these checks from the repository root:

```bash
python3 -m compileall omni_asset_cli.py omni_asset_service
python3 -m unittest discover -s tests
```

For the current service worker coverage, this is equivalent to:

```bash
python3 -m unittest tests/test_service_storage_worker.py
```

Do not use bare repository-wide discovery as the default host test command:

```bash
python3 -m unittest discover
```

That command can import packages outside `tests/`, including `physxdemos`,
which imports Isaac Sim modules such as `omni.kit.app`. Those modules are not
expected to exist in host Python.

## Runtime Validation

Authoritative physics validation must run through Isaac Sim Docker or an
already-running Isaac Sim container.

Preferred preflight in this workspace:

```bash
python3 omni_asset_cli.py physics-env \
  --runtime-docker-container isaac-sim
```

Standard Stage 1 runtime check:

```bash
python3 omni_asset_cli.py physics-hit-test path/to/asset.usd \
  --template-scene examples/mini_test.usda \
  --placement-mode replace-table \
  --hit-mode top-drop \
  --size-policy preserve \
  --frames 240 \
  --out out/asset_docker_hit \
  --runtime-docker-container isaac-sim \
  --docker-workspace /workspace/omni-asset-cli
```

For routine repeated checks, prefer the fixed workflow wrapper:

```bash
python3 omni_asset_cli.py stage1-runtime path/to/asset.usd \
  --out out/asset_stage1_runtime
```

The wrapper runs `physics-env`, then the standard top-drop `physics-hit-test`,
and records `workflow_report.json`, `workflow_commands.json`, step logs,
`summary.json`, `runtime_report.json`, and `timeline.csv`. By default it uses
the `standard` evidence preset: Docker access diagnostics, PhysX contact
evidence, front/side/top/iso videos, and physics bbox overlays. Use
`--evidence-preset contact-only` to skip video capture.

Runtime validation should preserve `summary.json`, `runtime_report.json`,
`timeline.csv`, rendered evidence when requested, the generated stage path, and
the process log.

## Evidence Rule

For collision conclusions, prefer structured PhysX contact report evidence over
visual or motion-based inference. A strong collision pass requires
`checks.contact_report_detected == true` and
`contact_evidence_level == "detected"` in `summary.json`, with supporting
detail in `runtime_report.json`.

Rendered frames, videos, bbox overlays, and motion-only inference are useful for
review and debugging, but they are not stronger than PhysX contact report
evidence.
