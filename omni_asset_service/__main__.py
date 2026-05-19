"""Run the FastAPI service with uvicorn."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the omni-asset runtime test REST API.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depends on optional extra.
        raise SystemExit("Install the 'api' extra to run the service: python -m pip install -e '.[api]'") from exc

    uvicorn.run("omni_asset_service.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
