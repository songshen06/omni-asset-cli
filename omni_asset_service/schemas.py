"""API schemas for the runtime test service."""

from __future__ import annotations

from typing import Any, Literal

try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without api extra installed.
    raise RuntimeError("Install the 'api' extra to use omni_asset_service FastAPI schemas.") from exc


class AssetResponse(BaseModel):
    asset_id: str
    original_filename: str
    sha256: str
    size: int
    status: str


class CollisionTestRequest(BaseModel):
    asset_id: str
    asset_role: Literal["furniture", "prop"] | None = None
    template_scene: str = "examples/mini_test.usda"
    placement_mode: Literal["auto", "replace-table", "tabletop", "replace-box"] = "replace-table"
    hit_mode: Literal["side-hit", "top-drop"] = "top-drop"
    size_policy: Literal["template-fit", "preserve"] = "preserve"
    frames: int = Field(default=240, ge=1, le=100000)
    render_frames: bool = False
    render_every_n_frames: int = Field(default=20, ge=1)
    runtime_docker_preflight: Literal["auto", "check", "restart", "skip"] = "auto"
    render_camera_preset: list[str] = Field(default_factory=list)
    render_backend: Literal["replicator", "viewport"] = "replicator"
    render_width: int = Field(default=1280, ge=1)
    render_height: int = Field(default=720, ge=1)
    render_rt_subframes: int = Field(default=4, ge=1)
    render_wait_updates: int = Field(default=20, ge=1)
    render_video: bool = False
    render_video_style: Literal["hit-test", "asset-table-drop"] = "hit-test"
    render_video_fps: float | None = Field(default=None, gt=0)
    render_video_crf: int = Field(default=23, ge=0, le=51)


class MeshValidationRequest(BaseModel):
    asset_id: str
    profile: Literal["stage1-furniture", "static", "collidable", "movable"] = "stage1-furniture"
    rule: list[str] = Field(default_factory=list)
    category: list[str] = Field(default_factory=list)
    predicate: Literal["Any", "IsError", "IsFailure", "IsWarning", "HasRootLayer"] | None = None
    init_rules: bool = False
    variants: bool = False
    pxr_ar_default_search_path: list[str] = Field(default_factory=list)


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobResponse(BaseModel):
    job_id: str
    asset_id: str
    test_type: str
    status: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ArtifactResponse(BaseModel):
    artifact_id: str
    kind: str
    filename: str
    content_type: str
    size: int


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactResponse]
