"""Background worker for collision runtime jobs."""

from __future__ import annotations

import json
import mimetypes
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .config import ServiceConfig
from .db import Database, json_loads
from .domain.artifacts import RUNTIME_REPORT_FILENAME, SUMMARY_FILENAME, artifact_kind
from .domain.collision import normalize_collision_request
from .domain.reports import normalize_job_summary
from .domain.status import classify_summary, classify_validation_summary
from .storage import job_artifacts_dir, job_work_dir, stage_asset_package


DEFAULT_TEMPLATE_SCENE = "examples/mini_test.usda"


class CollisionRunner:
    def __init__(self, config: ServiceConfig):
        self.config = config

    def build_command(
        self,
        *,
        request: dict[str, Any],
        staged_asset: Path,
        artifacts_dir: Path,
        container: str,
    ) -> list[str]:
        request = normalize_collision_request(request)
        template_scene = self.resolve_template_scene(str(request.get("template_scene") or DEFAULT_TEMPLATE_SCENE))
        command = [
            self.config.host_python,
            str(self.config.repo_root / "omni_asset_cli.py"),
            "physics-hit-test",
            str(staged_asset),
            "--template-scene",
            str(template_scene),
            "--placement-mode",
            str(request.get("placement_mode") or "replace-table"),
            "--hit-mode",
            str(request.get("hit_mode") or "top-drop"),
            "--size-policy",
            str(request.get("size_policy") or "preserve"),
            "--frames",
            str(request.get("frames") or 240),
            "--out",
            str(artifacts_dir),
            "--runtime-docker-container",
            container,
            "--runtime-docker-preflight",
            str(request.get("runtime_docker_preflight") or "auto"),
            "--docker-workspace",
            self.config.docker_workspace,
            "--docker-python",
            self.config.docker_python,
        ]
        if request.get("render_frames") or request.get("render_video"):
            command.append("--render-frames")
            command.extend(["--render-every-n-frames", str(request.get("render_every_n_frames") or 20)])
        for item in request.get("render_camera_preset") or []:
            command.extend(["--render-camera-preset", str(item)])
        if request.get("render_backend"):
            command.extend(["--render-backend", str(request["render_backend"])])
        if request.get("render_width") is not None:
            command.extend(["--render-width", str(request["render_width"])])
        if request.get("render_height") is not None:
            command.extend(["--render-height", str(request["render_height"])])
        if request.get("render_rt_subframes") is not None:
            command.extend(["--render-rt-subframes", str(request["render_rt_subframes"])])
        if request.get("render_wait_updates") is not None:
            command.extend(["--render-wait-updates", str(request["render_wait_updates"])])
        if request.get("render_video"):
            command.append("--render-video")
        if request.get("render_video_style"):
            command.extend(["--render-video-style", str(request["render_video_style"])])
        if request.get("render_video_fps") is not None:
            command.extend(["--render-video-fps", str(request["render_video_fps"])])
        if request.get("render_video_crf") is not None:
            command.extend(["--render-video-crf", str(request["render_video_crf"])])
        return command

    def resolve_template_scene(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("template_scene must be a repository-relative path")
        return self.config.repo_root / path

    def run(
        self,
        *,
        request: dict[str, Any],
        staged_asset: Path,
        artifacts_dir: Path,
        container: str,
    ) -> subprocess.CompletedProcess[str]:
        command = self.build_command(
            request=request,
            staged_asset=staged_asset,
            artifacts_dir=artifacts_dir,
            container=container,
        )
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=self.config.job_timeout_seconds,
        )


class MeshValidationRunner:
    def __init__(self, config: ServiceConfig):
        self.config = config

    def build_command(
        self,
        *,
        request: dict[str, Any],
        staged_asset: Path,
        artifacts_dir: Path,
    ) -> list[str]:
        command = [
            self.config.host_python,
            str(self.config.repo_root / "omni_asset_cli.py"),
            "validate",
            str(staged_asset),
            "--output-json",
            str(artifacts_dir / SUMMARY_FILENAME),
            "--output-md",
            str(artifacts_dir / "validation.md"),
        ]
        profile = request.get("profile") or "stage1-furniture"
        if profile:
            command.extend(["--profile", str(profile)])
        for item in request.get("pxr_ar_default_search_path") or []:
            command.extend(["--pxr-ar-default-search-path", str(item)])
        for item in request.get("rule") or []:
            command.extend(["--rule", str(item)])
        for item in request.get("category") or []:
            command.extend(["--category", str(item)])
        if request.get("predicate"):
            command.extend(["--predicate", str(request["predicate"])])
        if request.get("init_rules"):
            command.append("--init-rules")
        if request.get("variants"):
            command.append("--variants")
        return command

    def run(
        self,
        *,
        request: dict[str, Any],
        staged_asset: Path,
        artifacts_dir: Path,
    ) -> subprocess.CompletedProcess[str]:
        command = self.build_command(request=request, staged_asset=staged_asset, artifacts_dir=artifacts_dir)
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=self.config.job_timeout_seconds,
        )


class JobWorker:
    def __init__(
        self,
        *,
        db: Database,
        config: ServiceConfig,
        containers: Sequence[str] | None = None,
        runner: CollisionRunner | None = None,
        collision_runner: CollisionRunner | None = None,
        mesh_runner: MeshValidationRunner | None = None,
    ):
        self.db = db
        self.config = config
        self.containers = list(containers if containers is not None else config.isaac_containers)
        self.collision_runner = collision_runner or runner or CollisionRunner(config)
        self.mesh_runner = mesh_runner or MeshValidationRunner(config)
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        worker_slots = self.containers or [None]
        self._threads = []
        for index, container in enumerate(worker_slots):
            thread = threading.Thread(
                target=self.run_forever,
                args=(container,),
                name=f"omni-asset-job-worker-{index}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=timeout)

    def run_forever(self, container: str | None = None) -> None:
        while not self._stop_event.is_set():
            did_work = self.run_once(container)
            if not did_work:
                self._stop_event.wait(self.config.worker_poll_seconds)

    def run_once(self, container: str | None = None) -> bool:
        job = self.db.claim_next_job()
        if job is None:
            return False
        container = container or (self.containers[0] if self.containers else None)
        if job["test_type"] == "collision" and not container:
            self.db.update_job_status(
                job["id"],
                "blocked",
                result={"blocked_reason": "no_isaac_container_configured"},
                error="No Isaac Sim Docker container is configured for the service.",
            )
            return True
        self._run_claimed_job(job, container)
        return True

    def _run_claimed_job(self, job: Any, container: str | None) -> None:
        request = json_loads(job["request_json"]) or {}
        artifacts_dir: Path | None = None
        try:
            asset = self.db.get_asset(job["tenant_id"], job["project_id"], job["asset_id"])
            if asset is None:
                self.db.update_job_status(job["id"], "error", error="Asset record was not found.")
                return

            work_dir = job_work_dir(self.config.storage_root, job["tenant_id"], job["project_id"], job["id"])
            artifacts_dir = job_artifacts_dir(self.config.storage_root, job["tenant_id"], job["project_id"], job["id"])
            work_dir.mkdir(parents=True, exist_ok=True)
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            staged_asset = stage_asset_package(Path(asset["storage_path"]), Path(asset["entrypoint_path"]), work_dir)

            test_type = job["test_type"]
            if test_type == "collision":
                if container is None:
                    raise ValueError("collision job requires an Isaac Sim Docker container")
                request = normalize_collision_request(request)
                completed = self.collision_runner.run(
                    request=request,
                    staged_asset=staged_asset,
                    artifacts_dir=artifacts_dir,
                    container=container,
                )
                missing_summary_error = "Runtime finished without summary.json."
            elif test_type == "mesh":
                completed = self.mesh_runner.run(
                    request=request,
                    staged_asset=staged_asset,
                    artifacts_dir=artifacts_dir,
                )
                missing_summary_error = "Mesh validation finished without summary.json."
            else:
                self.db.update_job_status(job["id"], "error", error=f"Unsupported test_type: {test_type}")
                return

            self._write_process_log(artifacts_dir, completed)
            summary_path = artifacts_dir / SUMMARY_FILENAME
            if not summary_path.exists():
                self._record_artifacts(job["id"], artifacts_dir)
                self.db.update_job_status(
                    job["id"],
                    "error",
                    result={"returncode": completed.returncode},
                    error=missing_summary_error,
                )
                return

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            normalized_report = normalize_job_summary(test_type, summary, returncode=completed.returncode)
            self._record_artifacts(job["id"], artifacts_dir)
            self.db.update_job_status(
                job["id"],
                normalized_report.status,
                result=normalized_report.result,
                error=normalized_report.error,
            )
        except subprocess.TimeoutExpired as exc:
            if artifacts_dir is not None:
                self._write_timeout_log(artifacts_dir, exc)
                self._record_artifacts(job["id"], artifacts_dir)
            self.db.update_job_status(
                job["id"],
                "error",
                result={
                    "timeout_seconds": exc.timeout,
                    "command": _timeout_command(exc.cmd),
                },
                error=f"Runtime exceeded timeout of {exc.timeout} seconds.",
            )
        except Exception as exc:  # pragma: no cover - defensive worker boundary.
            self.db.update_job_status(job["id"], "error", error=str(exc))

    def _write_process_log(self, artifacts_dir: Path, completed: subprocess.CompletedProcess[str]) -> None:
        payload = {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (artifacts_dir / "process.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _write_timeout_log(self, artifacts_dir: Path, exc: subprocess.TimeoutExpired) -> None:
        payload = {
            "timeout_seconds": exc.timeout,
            "cmd": _timeout_command(exc.cmd),
            "stdout": _decode_timeout_output(exc.stdout),
            "stderr": _decode_timeout_output(exc.stderr),
        }
        (artifacts_dir / "process.json").write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _record_artifacts(self, job_id: str, artifacts_dir: Path) -> None:
        for path in sorted(item for item in artifacts_dir.rglob("*") if item.is_file()):
            relative_name = str(path.relative_to(artifacts_dir))
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            kind = artifact_kind(path)
            self.db.insert_artifact(
                job_id=job_id,
                kind=kind,
                filename=relative_name,
                path=path,
                content_type=content_type,
                size=path.stat().st_size,
            )


def _decode_timeout_output(value: bytes | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _timeout_command(value: object) -> object:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return _decode_timeout_output(value) if isinstance(value, (bytes, str)) else value
