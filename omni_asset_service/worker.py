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
from .storage import job_artifacts_dir, job_work_dir, stage_asset_package


SUMMARY_FILENAME = "summary.json"
RUNTIME_REPORT_FILENAME = "runtime_report.json"
DEFAULT_TEMPLATE_SCENE = "examples/mini_test.usda"
PHYSICS_IMPACTING_VALIDATION_RULES = {
    "ExtentsChecker",
    "ManifoldChecker",
    "MissingReferenceChecker",
    "NormalsValidChecker",
    "StageMetadataChecker",
    "ValidateTopologyChecker",
    "ZeroAreaFaceChecker",
}
PHYSICS_BLOCKING_SEVERITIES = {"ERROR", "FAILURE"}


def classify_summary(summary: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    checks = summary.get("checks") if isinstance(summary.get("checks"), dict) else {}
    result = summary.get("result")
    contact_report_detected = checks.get("contact_report_detected") is True
    evidence_level = summary.get("contact_evidence_level")
    strong_contact_evidence = contact_report_detected and evidence_level == "detected"
    adapted = {
        "summary_result": result,
        "contact_report_detected": contact_report_detected,
        "contact_evidence_level": evidence_level,
        "strong_contact_evidence": strong_contact_evidence,
    }
    if result == "blocked":
        return "blocked", adapted, summary.get("error") if isinstance(summary.get("error"), str) else None
    if result == "passed" and strong_contact_evidence:
        return "passed", adapted, None
    return "failed", adapted, None


def classify_validation_summary(summary: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    validation_status = summary.get("validation_status") or summary.get("status")
    execution_status = summary.get("execution_status")
    issue_summary = summary.get("summary") if isinstance(summary.get("summary"), dict) else {}
    error_payload = summary.get("error") if isinstance(summary.get("error"), dict) else {}
    issues = summary.get("issues") if isinstance(summary.get("issues"), list) else []
    physics_blocking_issues = [
        issue
        for issue in issues
        if isinstance(issue, dict)
        and issue.get("rule") in PHYSICS_IMPACTING_VALIDATION_RULES
        and issue.get("severity") in PHYSICS_BLOCKING_SEVERITIES
    ]
    adapted = {
        "validation_status": validation_status,
        "execution_status": execution_status,
        "issue_count": issue_summary.get("issue_count"),
        "severity_counts": issue_summary.get("severity_counts") or {},
        "rule_counts": issue_summary.get("rule_counts") or {},
        "physics_blocking_issue_count": len(physics_blocking_issues),
        "physics_blocking_rules": sorted(
            {str(issue.get("rule")) for issue in physics_blocking_issues if issue.get("rule")}
        ),
    }
    if execution_status == "error" or validation_status == "blocked":
        return "blocked", adapted, error_payload.get("message") if error_payload else None
    if physics_blocking_issues:
        return "failed", adapted, "Mesh validation found issues that can affect physics collision."
    if validation_status in {"passed", "warning", "failed"}:
        return "passed", adapted, None
    return "failed", adapted, None


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
            "--docker-workspace",
            self.config.docker_workspace,
            "--docker-python",
            self.config.docker_python,
        ]
        if request.get("render_frames"):
            command.append("--render-frames")
            command.extend(["--render-every-n-frames", str(request.get("render_every_n_frames") or 20)])
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
                completed = self.collision_runner.run(
                    request=request,
                    staged_asset=staged_asset,
                    artifacts_dir=artifacts_dir,
                    container=container,
                )
                classifier = classify_summary
                missing_summary_error = "Runtime finished without summary.json."
            elif test_type == "mesh":
                completed = self.mesh_runner.run(
                    request=request,
                    staged_asset=staged_asset,
                    artifacts_dir=artifacts_dir,
                )
                classifier = classify_validation_summary
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
            status, adapted_result, error = classifier(summary)
            adapted_result["returncode"] = completed.returncode
            self._record_artifacts(job["id"], artifacts_dir)
            self.db.update_job_status(job["id"], status, result=adapted_result, error=error)
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
            kind = _artifact_kind(path)
            self.db.insert_artifact(
                job_id=job_id,
                kind=kind,
                filename=relative_name,
                path=path,
                content_type=content_type,
                size=path.stat().st_size,
            )


def _artifact_kind(path: Path) -> str:
    if path.name == SUMMARY_FILENAME:
        return "summary"
    if path.name == RUNTIME_REPORT_FILENAME:
        return "runtime_report"
    if path.suffix.lower() == ".csv":
        return "timeline"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return "image"
    if path.suffix.lower() == ".json":
        return "json"
    return "artifact"


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
