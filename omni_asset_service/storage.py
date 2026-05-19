"""Local artifact and upload storage helpers."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path

from .db import new_id


USD_EXTENSIONS = {".usd", ".usda", ".usdc"}


class StorageError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scope_root(storage_root: Path, tenant_id: str, project_id: str) -> Path:
    return storage_root / "tenants" / tenant_id / "projects" / project_id


def asset_input_dir(storage_root: Path, tenant_id: str, project_id: str, asset_id: str) -> Path:
    return scope_root(storage_root, tenant_id, project_id) / "assets" / asset_id / "input"


def job_work_dir(storage_root: Path, tenant_id: str, project_id: str, job_id: str) -> Path:
    return scope_root(storage_root, tenant_id, project_id) / "jobs" / job_id / "work"


def job_artifacts_dir(storage_root: Path, tenant_id: str, project_id: str, job_id: str) -> Path:
    return scope_root(storage_root, tenant_id, project_id) / "jobs" / job_id / "artifacts"


def ensure_safe_relative(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise StorageError(f"unsafe archive member path: {path}")
    return candidate


def extract_zip_safely(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            relative = ensure_safe_relative(info.filename)
            if not relative.parts:
                continue
            target = destination / relative
            resolved = target.resolve()
            destination_resolved = destination.resolve()
            if destination_resolved not in resolved.parents and resolved != destination_resolved:
                raise StorageError(f"archive member escapes destination: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as sink:
                    shutil.copyfileobj(source, sink)


def find_usd_entrypoint(input_dir: Path) -> Path:
    matches = sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() in USD_EXTENSIONS)
    if not matches:
        raise StorageError("upload does not contain a .usd, .usda, or .usdc file")
    return matches[0]


def write_upload_bytes(
    *,
    storage_root: Path,
    tenant_id: str,
    project_id: str,
    filename: str,
    data: bytes,
) -> dict[str, object]:
    suffix = Path(filename).suffix.lower()
    if suffix not in USD_EXTENSIONS and suffix != ".zip":
        raise StorageError("asset upload must be .zip, .usd, .usda, or .usdc")

    asset_id = new_id("asset")
    input_dir = asset_input_dir(storage_root, tenant_id, project_id, asset_id)
    input_dir.mkdir(parents=True, exist_ok=False)
    original_file = input_dir / Path(filename).name
    original_file.write_bytes(data)

    if suffix == ".zip":
        zip_path = original_file
        extract_zip_safely(zip_path, input_dir)
        zip_path.unlink()
        entrypoint = find_usd_entrypoint(input_dir)
        checksum = hashlib.sha256(data).hexdigest()
    else:
        entrypoint = original_file
        checksum = sha256_file(original_file)

    return {
        "asset_id": asset_id,
        "input_dir": input_dir,
        "entrypoint": entrypoint,
        "entrypoint_relative": entrypoint.relative_to(input_dir),
        "sha256": checksum,
        "size": len(data),
    }


def stage_asset_package(asset_storage_path: Path, entrypoint_relative: Path, work_dir: Path) -> Path:
    staged_input = work_dir / "input"
    if staged_input.exists():
        shutil.rmtree(staged_input)
    shutil.copytree(asset_storage_path, staged_input)
    staged_asset = staged_input / entrypoint_relative
    if not staged_asset.exists():
        raise StorageError(f"asset entrypoint is missing after staging: {entrypoint_relative}")
    return staged_asset
