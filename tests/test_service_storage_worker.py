from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from omni_asset_service.config import ServiceConfig, load_config_from_env
from omni_asset_service.db import Database, json_loads
from omni_asset_service.storage import StorageError, write_upload_bytes
from omni_asset_service.worker import CollisionRunner, JobWorker, MeshValidationRunner, classify_summary, classify_validation_summary


class FakeRunner:
    def __init__(self, summary: dict[str, object] | None):
        self.summary = summary
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        request: dict[str, object],
        staged_asset: Path,
        artifacts_dir: Path,
        container: str,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(
            {
                "request": request,
                "staged_asset": staged_asset,
                "artifacts_dir": artifacts_dir,
                "container": container,
            }
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if self.summary is not None:
            (artifacts_dir / "summary.json").write_text(json.dumps(self.summary), encoding="utf-8")
        (artifacts_dir / "runtime_report.json").write_text('{"ok": true}', encoding="utf-8")
        (artifacts_dir / "timeline.csv").write_text("frame,event\n1,contact\n", encoding="utf-8")
        return subprocess.CompletedProcess(args=["fake"], returncode=0, stdout="ok", stderr="")


class TimeoutRunner:
    def run(
        self,
        *,
        request: dict[str, object],
        staged_asset: Path,
        artifacts_dir: Path,
        container: str,
    ) -> subprocess.CompletedProcess[str]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        raise subprocess.TimeoutExpired(cmd=["fake"], timeout=1.5, output="partial out", stderr="partial err")


class FakeMeshRunner:
    def __init__(self, summary: dict[str, object] | None):
        self.summary = summary
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        request: dict[str, object],
        staged_asset: Path,
        artifacts_dir: Path,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(
            {
                "request": request,
                "staged_asset": staged_asset,
                "artifacts_dir": artifacts_dir,
            }
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if self.summary is not None:
            (artifacts_dir / "summary.json").write_text(json.dumps(self.summary), encoding="utf-8")
        (artifacts_dir / "validation.md").write_text("# Validation\n", encoding="utf-8")
        return subprocess.CompletedProcess(args=["fake"], returncode=0, stdout="ok", stderr="")


class ServiceStorageWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = ServiceConfig(
            storage_root=self.root / "storage",
            database_path=self.root / "service.sqlite3",
            isaac_containers=("isaac-sim-0",),
            start_worker=False,
        )
        self.db = Database(self.config.resolved_database_path)
        self.db.initialize()
        self.db.create_tenant("tenant_a", "Tenant A")
        self.db.create_tenant("tenant_b", "Tenant B")
        self.db.create_project("project_a", "tenant_a", "Project A")
        self.db.create_project("project_b", "tenant_b", "Project B")
        self.db.create_api_key("secret-a", "tenant_a", "project_a")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def create_asset(self) -> str:
        stored = write_upload_bytes(
            storage_root=self.config.storage_root,
            tenant_id="tenant_a",
            project_id="project_a",
            filename="asset.usda",
            data=b"#usda 1.0\n",
        )
        return self.db.insert_asset(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=str(stored["asset_id"]),
            original_filename="asset.usda",
            storage_path=Path(stored["input_dir"]),
            entrypoint_path=Path(stored["entrypoint_relative"]),
            sha256=str(stored["sha256"]),
            size=int(stored["size"]),
        )

    def test_api_key_and_asset_queries_are_tenant_project_scoped(self) -> None:
        auth = self.db.authenticate_api_key("secret-a")
        self.assertIsNotNone(auth)
        self.assertEqual(auth["tenant_id"], "tenant_a")
        asset_id = self.create_asset()

        self.assertIsNotNone(self.db.get_asset("tenant_a", "project_a", asset_id))
        self.assertIsNone(self.db.get_asset("tenant_b", "project_b", asset_id))

    def test_zip_upload_rejects_path_traversal(self) -> None:
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("../escape.usda", "#usda 1.0\n")

        with self.assertRaises(StorageError):
            write_upload_bytes(
                storage_root=self.config.storage_root,
                tenant_id="tenant_a",
                project_id="project_a",
                filename="bad.zip",
                data=archive.read_bytes(),
            )

    def test_default_storage_root_stays_under_repo_root(self) -> None:
        repo_root = self.root / "repo"
        with patch.dict(
            "os.environ",
            {"OMNI_SERVICE_REPO_ROOT": str(repo_root)},
            clear=True,
        ):
            config = load_config_from_env()

        self.assertEqual(config.storage_root, repo_root / "out" / "omni-asset-service")

    def test_worker_marks_strong_contact_pass_and_records_artifacts(self) -> None:
        asset_id = self.create_asset()
        request = {
            "asset_id": asset_id,
            "template_scene": "examples/mini_test.usda",
            "placement_mode": "replace-table",
            "hit_mode": "top-drop",
            "size_policy": "preserve",
            "frames": 240,
        }
        job_id = self.db.insert_job(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=asset_id,
            test_type="collision",
            request=request,
        )
        runner = FakeRunner(
            {
                "result": "passed",
                "checks": {"contact_report_detected": True},
                "contact_evidence_level": "detected",
            }
        )
        worker = JobWorker(db=self.db, config=self.config, runner=runner)

        self.assertTrue(worker.run_once("isaac-sim-0"))
        job = self.db.get_job("tenant_a", "project_a", job_id)
        self.assertEqual(job["status"], "passed")
        result = json_loads(job["result_json"])
        self.assertTrue(result["strong_contact_evidence"])
        self.assertEqual(runner.calls[0]["container"], "isaac-sim-0")
        self.assertTrue(Path(runner.calls[0]["staged_asset"]).exists())

        artifacts = self.db.list_artifacts("tenant_a", "project_a", job_id)
        kinds = {artifact["kind"] for artifact in artifacts}
        self.assertIn("summary", kinds)
        self.assertIn("runtime_report", kinds)
        self.assertIn("timeline", kinds)

    def test_worker_does_not_pass_inferred_or_missing_contact(self) -> None:
        status, adapted, error = classify_summary(
            {
                "result": "passed",
                "checks": {"contact_report_detected": False, "contact_detected_or_inferred": True},
                "contact_evidence_level": "inferred",
            }
        )
        self.assertEqual(status, "failed")
        self.assertFalse(adapted["strong_contact_evidence"])
        self.assertIsNone(error)

    def test_worker_blocks_when_no_container_is_configured(self) -> None:
        asset_id = self.create_asset()
        job_id = self.db.insert_job(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=asset_id,
            test_type="collision",
            request={"asset_id": asset_id},
        )
        worker = JobWorker(db=self.db, config=self.config, containers=[])

        self.assertTrue(worker.run_once())
        job = self.db.get_job("tenant_a", "project_a", job_id)
        self.assertEqual(job["status"], "blocked")
        self.assertIn("No Isaac Sim Docker container", job["error"])

    def test_worker_runs_mesh_validation_without_isaac_container(self) -> None:
        asset_id = self.create_asset()
        job_id = self.db.insert_job(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=asset_id,
            test_type="mesh",
            request={"asset_id": asset_id, "profile": "stage1-furniture"},
        )
        mesh_runner = FakeMeshRunner(
            {
                "status": "passed",
                "validation_status": "passed",
                "execution_status": "completed",
                "summary": {"issue_count": 0, "severity_counts": {}, "rule_counts": {}},
                "issues": [],
            }
        )
        worker = JobWorker(db=self.db, config=self.config, containers=[], mesh_runner=mesh_runner)

        self.assertTrue(worker.run_once())
        job = self.db.get_job("tenant_a", "project_a", job_id)
        self.assertEqual(job["status"], "passed")
        result = json_loads(job["result_json"])
        self.assertEqual(result["validation_status"], "passed")
        self.assertEqual(result["issue_count"], 0)
        self.assertTrue(Path(mesh_runner.calls[0]["staged_asset"]).exists())

        artifacts = self.db.list_artifacts("tenant_a", "project_a", job_id)
        filenames = {artifact["filename"] for artifact in artifacts}
        self.assertIn("summary.json", filenames)
        self.assertIn("validation.md", filenames)

    def test_validation_warning_is_a_passing_mesh_job(self) -> None:
        status, adapted, error = classify_validation_summary(
            {
                "status": "warning",
                "validation_status": "warning",
                "execution_status": "completed",
                "summary": {
                    "issue_count": 1,
                    "severity_counts": {"WARNING": 1},
                    "rule_counts": {"WeldChecker": 1},
                },
            }
        )
        self.assertEqual(status, "passed")
        self.assertEqual(adapted["validation_status"], "warning")
        self.assertEqual(adapted["severity_counts"], {"WARNING": 1})
        self.assertEqual(adapted["physics_blocking_issue_count"], 0)
        self.assertIsNone(error)

    def test_physics_impacting_validation_failure_fails_mesh_job(self) -> None:
        status, adapted, error = classify_validation_summary(
            {
                "status": "failed",
                "validation_status": "failed",
                "execution_status": "completed",
                "summary": {
                    "issue_count": 1,
                    "severity_counts": {"FAILURE": 1},
                    "rule_counts": {"ValidateTopologyChecker": 1},
                },
                "issues": [
                    {
                        "severity": "FAILURE",
                        "rule": "ValidateTopologyChecker",
                        "message": "invalid topology",
                    }
                ],
            }
        )
        self.assertEqual(status, "failed")
        self.assertEqual(adapted["physics_blocking_issue_count"], 1)
        self.assertEqual(adapted["physics_blocking_rules"], ["ValidateTopologyChecker"])
        self.assertIn("physics collision", error)

    def test_non_physics_validation_failure_does_not_fail_mesh_job(self) -> None:
        status, adapted, error = classify_validation_summary(
            {
                "status": "failed",
                "validation_status": "failed",
                "execution_status": "completed",
                "summary": {
                    "issue_count": 1,
                    "severity_counts": {"FAILURE": 1},
                    "rule_counts": {"MaterialPathChecker": 1},
                },
                "issues": [
                    {
                        "severity": "FAILURE",
                        "rule": "MaterialPathChecker",
                        "message": "missing material texture",
                    }
                ],
            }
        )
        self.assertEqual(status, "passed")
        self.assertEqual(adapted["physics_blocking_issue_count"], 0)
        self.assertIsNone(error)

    def test_missing_summary_becomes_error(self) -> None:
        asset_id = self.create_asset()
        job_id = self.db.insert_job(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=asset_id,
            test_type="collision",
            request={"asset_id": asset_id},
        )
        worker = JobWorker(db=self.db, config=self.config, runner=FakeRunner(summary=None))

        self.assertTrue(worker.run_once("isaac-sim-0"))
        job = self.db.get_job("tenant_a", "project_a", job_id)
        self.assertEqual(job["status"], "error")
        self.assertIn("summary.json", job["error"])

    def test_worker_marks_timeout_error_and_records_process_artifact(self) -> None:
        asset_id = self.create_asset()
        job_id = self.db.insert_job(
            tenant_id="tenant_a",
            project_id="project_a",
            asset_id=asset_id,
            test_type="collision",
            request={"asset_id": asset_id},
        )
        worker = JobWorker(db=self.db, config=self.config, runner=TimeoutRunner())

        self.assertTrue(worker.run_once("isaac-sim-0"))
        job = self.db.get_job("tenant_a", "project_a", job_id)
        self.assertEqual(job["status"], "error")
        self.assertIn("exceeded timeout", job["error"])
        result = json_loads(job["result_json"])
        self.assertEqual(result["timeout_seconds"], 1.5)
        artifacts = self.db.list_artifacts("tenant_a", "project_a", job_id)
        self.assertIn("process.json", {artifact["filename"] for artifact in artifacts})

    def test_collision_runner_builds_existing_cli_command(self) -> None:
        runner = CollisionRunner(self.config)
        command = runner.build_command(
            request={
                "template_scene": "examples/mini_test.usda",
                "placement_mode": "replace-table",
                "hit_mode": "top-drop",
                "size_policy": "preserve",
                "frames": 240,
                "render_frames": True,
                "render_every_n_frames": 20,
            },
            staged_asset=self.root / "asset.usda",
            artifacts_dir=self.root / "artifacts",
            container="isaac-sim-0",
        )

        self.assertIn("physics-hit-test", command)
        self.assertIn("--runtime-docker-container", command)
        self.assertIn("isaac-sim-0", command)
        self.assertIn("--docker-workspace", command)
        self.assertIn("--render-frames", command)

    def test_collision_runner_rejects_unsafe_template_scene_path(self) -> None:
        runner = CollisionRunner(self.config)
        with self.assertRaises(ValueError):
            runner.build_command(
                request={"template_scene": "../outside.usda"},
                staged_asset=self.root / "asset.usda",
                artifacts_dir=self.root / "artifacts",
                container="isaac-sim-0",
            )

    def test_mesh_validation_runner_builds_existing_cli_command(self) -> None:
        runner = MeshValidationRunner(self.config)
        command = runner.build_command(
            request={
                "profile": "stage1-furniture",
                "rule": ["ManifoldChecker"],
                "category": ["mesh"],
                "predicate": "IsFailure",
                "init_rules": True,
                "variants": True,
                "pxr_ar_default_search_path": ["deps"],
            },
            staged_asset=self.root / "asset.usda",
            artifacts_dir=self.root / "artifacts",
        )

        self.assertIn("validate", command)
        self.assertIn("--output-json", command)
        self.assertIn(str(self.root / "artifacts" / "summary.json"), command)
        self.assertIn("--output-md", command)
        self.assertIn("--profile", command)
        self.assertIn("stage1-furniture", command)
        self.assertIn("--rule", command)
        self.assertIn("ManifoldChecker", command)
        self.assertIn("--variants", command)


if __name__ == "__main__":
    unittest.main()
