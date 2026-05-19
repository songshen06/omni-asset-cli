"""FastAPI application for the multi-tenant USD runtime test service."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

try:
    from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
    from fastapi.responses import FileResponse
except ImportError as exc:  # pragma: no cover - exercised only without api extra installed.
    raise RuntimeError("Install the 'api' extra to run the FastAPI service.") from exc

from .config import ServiceConfig, load_config_from_env
from .db import Database, json_loads
from .schemas import (
    ArtifactListResponse,
    ArtifactResponse,
    AssetResponse,
    CollisionTestRequest,
    JobCreateResponse,
    JobResponse,
    MeshValidationRequest,
)
from .storage import StorageError, write_upload_bytes
from .worker import DEFAULT_TEMPLATE_SCENE, JobWorker


class ServiceState:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.db = Database(config.resolved_database_path)
        self.worker = JobWorker(db=self.db, config=config)

    def initialize(self) -> None:
        self.config.storage_root.mkdir(parents=True, exist_ok=True)
        self.db.initialize()
        seed_from_env(self.db)
        if self.config.start_worker:
            self.worker.start()

    def shutdown(self) -> None:
        self.worker.stop()


def seed_from_env(db: Database) -> None:
    """Seed simple local credentials from OMNI_SERVICE_API_KEYS.

    Format: key:tenant_id:project_id[:tenant_name[:project_name]],...
    """

    raw = os.environ.get("OMNI_SERVICE_API_KEYS")
    if not raw:
        return
    for item in raw.split(","):
        parts = [part.strip() for part in item.split(":")]
        if len(parts) < 3 or not all(parts[:3]):
            continue
        key, tenant_id, project_id = parts[:3]
        tenant_name = parts[3] if len(parts) > 3 and parts[3] else tenant_id
        project_name = parts[4] if len(parts) > 4 and parts[4] else project_id
        db.create_tenant(tenant_id, tenant_name)
        db.create_project(project_id, tenant_id, project_name)
        db.create_api_key(key, tenant_id, project_id)


def create_app(config: ServiceConfig | None = None) -> FastAPI:
    state = ServiceState(config or load_config_from_env())
    app = FastAPI(
        title="Omni Asset Runtime Test API",
        version="0.1.0",
        description="Multi-tenant REST API for Isaac Sim Docker-backed OpenUSD runtime collision tests.",
    )
    app.state.service_state = state

    @app.on_event("startup")
    def startup() -> None:
        state.initialize()

    @app.on_event("shutdown")
    def shutdown() -> None:
        state.shutdown()

    return register_routes(app)


def register_routes(app: FastAPI) -> FastAPI:
    def state_dep() -> ServiceState:
        return app.state.service_state

    async def require_project_access(
        project_id: str,
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
        state: ServiceState = Depends(state_dep),
    ) -> dict[str, str]:
        if not x_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header.")
        key_record = state.db.authenticate_api_key(x_api_key)
        if key_record is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
        tenant_id = key_record["tenant_id"]
        allowed_project_id = key_record["project_id"]
        if allowed_project_id and allowed_project_id != project_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API key cannot access this project.")
        if state.db.get_project_for_tenant(tenant_id, project_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project was not found.")
        return {"tenant_id": tenant_id, "project_id": project_id}

    @app.post("/v1/projects/{project_id}/assets", response_model=AssetResponse)
    async def upload_asset(
        project_id: str,
        file: UploadFile = File(...),
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> AssetResponse:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded asset is empty.")
        try:
            stored = write_upload_bytes(
                storage_root=state.config.storage_root,
                tenant_id=scope["tenant_id"],
                project_id=project_id,
                filename=file.filename or "asset.usd",
                data=data,
            )
        except StorageError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        asset_id = state.db.insert_asset(
            tenant_id=scope["tenant_id"],
            project_id=project_id,
            asset_id=str(stored["asset_id"]),
            original_filename=file.filename or "asset.usd",
            storage_path=Path(stored["input_dir"]),
            entrypoint_path=Path(stored["entrypoint_relative"]),
            sha256=str(stored["sha256"]),
            size=int(stored["size"]),
        )
        return AssetResponse(
            asset_id=asset_id,
            original_filename=file.filename or "asset.usd",
            sha256=str(stored["sha256"]),
            size=int(stored["size"]),
            status="ready",
        )

    @app.post("/v1/projects/{project_id}/tests/collision", response_model=JobCreateResponse)
    def create_collision_job(
        project_id: str,
        request: CollisionTestRequest,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> JobCreateResponse:
        template_scene = Path(request.template_scene or DEFAULT_TEMPLATE_SCENE)
        if template_scene.is_absolute() or ".." in template_scene.parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="template_scene must be a repository-relative path.",
            )
        asset = state.db.get_asset(scope["tenant_id"], project_id, request.asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset was not found.")
        job_id = state.db.insert_job(
            tenant_id=scope["tenant_id"],
            project_id=project_id,
            asset_id=request.asset_id,
            test_type="collision",
            request=_model_to_dict(request),
        )
        return JobCreateResponse(job_id=job_id, status="queued")

    @app.post("/v1/projects/{project_id}/tests/mesh", response_model=JobCreateResponse)
    def create_mesh_validation_job(
        project_id: str,
        request: MeshValidationRequest,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> JobCreateResponse:
        asset = state.db.get_asset(scope["tenant_id"], project_id, request.asset_id)
        if asset is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset was not found.")
        job_id = state.db.insert_job(
            tenant_id=scope["tenant_id"],
            project_id=project_id,
            asset_id=request.asset_id,
            test_type="mesh",
            request=_model_to_dict(request),
        )
        return JobCreateResponse(job_id=job_id, status="queued")

    @app.get("/v1/projects/{project_id}/jobs/{job_id}", response_model=JobResponse)
    def get_job(
        project_id: str,
        job_id: str,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> JobResponse:
        job = state.db.get_job(scope["tenant_id"], project_id, job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job was not found.")
        return _job_response(job)

    @app.get("/v1/projects/{project_id}/jobs/{job_id}/report/summary")
    def get_summary_report(
        project_id: str,
        job_id: str,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> dict[str, object]:
        return _load_report_json(state, scope["tenant_id"], project_id, job_id, "summary")

    @app.get("/v1/projects/{project_id}/jobs/{job_id}/report/runtime")
    def get_runtime_report(
        project_id: str,
        job_id: str,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> dict[str, object]:
        return _load_report_json(state, scope["tenant_id"], project_id, job_id, "runtime_report")

    @app.get("/v1/projects/{project_id}/jobs/{job_id}/artifacts", response_model=ArtifactListResponse)
    def list_artifacts(
        project_id: str,
        job_id: str,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> ArtifactListResponse:
        if state.db.get_job(scope["tenant_id"], project_id, job_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job was not found.")
        return ArtifactListResponse(
            artifacts=[
                ArtifactResponse(
                    artifact_id=row["id"],
                    kind=row["kind"],
                    filename=row["filename"],
                    content_type=row["content_type"],
                    size=row["size"],
                )
                for row in state.db.list_artifacts(scope["tenant_id"], project_id, job_id)
            ]
        )

    @app.get("/v1/projects/{project_id}/jobs/{job_id}/artifacts/{artifact_id}")
    def download_artifact(
        project_id: str,
        job_id: str,
        artifact_id: str,
        scope: dict[str, str] = Depends(require_project_access),
        state: ServiceState = Depends(state_dep),
    ) -> FileResponse:
        artifact = state.db.get_artifact(scope["tenant_id"], project_id, job_id, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact was not found.")
        path = Path(artifact["path"])
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is missing.")
        return FileResponse(path, media_type=artifact["content_type"], filename=artifact["filename"])

    return app


def _job_response(job: object) -> JobResponse:
    return JobResponse(
        job_id=job["id"],
        asset_id=job["asset_id"],
        test_type=job["test_type"],
        status=job["status"],
        request=json_loads(job["request_json"]) or {},
        result=json_loads(job["result_json"]),
        error=job["error"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        started_at=job["started_at"],
        finished_at=job["finished_at"],
    )


def _model_to_dict(model: object) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _load_report_json(
    state: ServiceState,
    tenant_id: str,
    project_id: str,
    job_id: str,
    kind: str,
) -> dict[str, object]:
    if state.db.get_job(tenant_id, project_id, job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job was not found.")
    matches = [artifact for artifact in state.db.list_artifacts(tenant_id, project_id, job_id) if artifact["kind"] == kind]
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{kind} report was not found.")
    path = Path(matches[0]["path"])
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{kind} report file is missing.")
    return json.loads(path.read_text(encoding="utf-8"))


app = create_app()
