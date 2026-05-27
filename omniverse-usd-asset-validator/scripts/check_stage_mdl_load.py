#!/usr/bin/env python3
"""Open a USD stage in Isaac Sim long enough to trigger MDL loading."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a USD stage in Isaac Sim and report whether it loaded.")
    parser.add_argument("stage", type=Path)
    parser.add_argument("--updates", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from isaacsim import SimulationApp  # type: ignore

    app = SimulationApp({"headless": True, "width": 320, "height": 240})
    try:
        import omni.usd  # type: ignore

        context = omni.usd.get_context()
        context.open_stage(str(args.stage))
        for _ in range(max(args.updates, 1)):
            app.update()
        stage = context.get_stage()
        default_prim = stage.GetDefaultPrim() if stage is not None else None
        print(json.dumps({"opened": stage is not None, "default_prim": str(default_prim.GetPath()) if default_prim else None}))
        return 0 if stage is not None else 1
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
