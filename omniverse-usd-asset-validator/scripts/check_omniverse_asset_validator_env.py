#!/usr/bin/env python3
"""Report whether the current environment can run omniverse asset validation."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import os


def run_command(args: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 127, ""
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, output


def main() -> int:
    py = sys.version_info
    print(f"Python: {py.major}.{py.minor}.{py.micro}")
    print(f"Platform: {platform.platform()}")

    if (py.major, py.minor) < (3, 10) or (py.major, py.minor) > (3, 12):
        print("Python support: unsupported by NVIDIA docs (expected 3.10-3.12)")
    else:
        print("Python support: documented range")

    cli_path = shutil.which("omni_asset_validate")
    if cli_path:
        print(f"CLI: found at {cli_path}")
        code, output = run_command(["omni_asset_validate", "--version"])
        if code == 0 and output:
            print(f"CLI version: {output}")
        else:
            print("CLI version: unavailable")
    else:
        print("CLI: not found on PATH")

    code, output = run_command([sys.executable, "-m", "pip", "show", "omniverse-asset-validator"])
    if code == 0 and output:
        print("pip package: installed")
    else:
        print("pip package: not detected in this interpreter")

    search_path = os.environ.get("PXR_AR_DEFAULT_SEARCH_PATH")
    if search_path:
        print(f"PXR_AR_DEFAULT_SEARCH_PATH: {search_path}")
    else:
        print("PXR_AR_DEFAULT_SEARCH_PATH: not set")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
