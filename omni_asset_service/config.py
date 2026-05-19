"""Configuration for the multi-tenant runtime test service."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_ROOT = REPO_ROOT / "out" / "omni-asset-service"
DEFAULT_JOB_TIMEOUT_SECONDS = 60 * 60 * 2


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class ServiceConfig:
    storage_root: Path = DEFAULT_STORAGE_ROOT
    database_path: Path | None = None
    repo_root: Path = REPO_ROOT
    isaac_containers: tuple[str, ...] = ()
    docker_workspace: str = "/workspace/omni-asset-cli"
    docker_python: str = "/isaac-sim/python.sh"
    host_python: str = sys.executable or "python3"
    worker_poll_seconds: float = 1.0
    job_timeout_seconds: float | None = DEFAULT_JOB_TIMEOUT_SECONDS
    start_worker: bool = True

    @property
    def resolved_database_path(self) -> Path:
        if self.database_path is not None:
            return self.database_path
        return self.storage_root / "service.sqlite3"


def load_config_from_env() -> ServiceConfig:
    repo_root = Path(os.environ.get("OMNI_SERVICE_REPO_ROOT", str(REPO_ROOT)))
    storage_root = Path(os.environ.get("OMNI_SERVICE_STORAGE_ROOT", str(repo_root / "out" / "omni-asset-service")))
    database_path = os.environ.get("OMNI_SERVICE_DB")
    timeout_raw = os.environ.get("OMNI_SERVICE_JOB_TIMEOUT_SECONDS", str(DEFAULT_JOB_TIMEOUT_SECONDS))
    return ServiceConfig(
        storage_root=storage_root,
        database_path=Path(database_path) if database_path else None,
        repo_root=repo_root,
        isaac_containers=tuple(_split_csv(os.environ.get("ISAAC_CONTAINERS"))),
        docker_workspace=os.environ.get("DOCKER_WORKSPACE", "/workspace/omni-asset-cli"),
        docker_python=os.environ.get("DOCKER_PYTHON", "/isaac-sim/python.sh"),
        host_python=os.environ.get("OMNI_SERVICE_HOST_PYTHON", sys.executable or "python3"),
        worker_poll_seconds=float(os.environ.get("OMNI_SERVICE_WORKER_POLL_SECONDS", "1.0")),
        job_timeout_seconds=None if timeout_raw in {"0", "none", "None", ""} else float(timeout_raw),
        start_worker=os.environ.get("OMNI_SERVICE_START_WORKER", "1") not in {"0", "false", "False"},
    )
