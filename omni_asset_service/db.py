"""SQLite persistence for the runtime test service."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_JOB_STATUSES = {"passed", "failed", "blocked", "error", "canceled"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def json_loads(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


class Database:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    hashed_key TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    entrypoint_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    test_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (asset_id) REFERENCES assets(id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_projects_tenant ON projects(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_assets_scope ON assets(tenant_id, project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_scope ON jobs(tenant_id, project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_artifacts_job ON artifacts(job_id);
                """
            )

    @contextmanager
    def connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def create_tenant(self, tenant_id: str, name: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tenants (id, name, created_at) VALUES (?, ?, ?)",
                (tenant_id, name, utc_now()),
            )

    def create_project(self, project_id: str, tenant_id: str, name: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, tenant_id, name, created_at) VALUES (?, ?, ?, ?)",
                (project_id, tenant_id, name, utc_now()),
            )

    def create_api_key(self, api_key: str, tenant_id: str, project_id: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO api_keys (hashed_key, tenant_id, project_id, status, created_at)
                VALUES (?, ?, ?, 'active', ?)
                """,
                (hash_api_key(api_key), tenant_id, project_id, utc_now()),
            )

    def authenticate_api_key(self, api_key: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT hashed_key, tenant_id, project_id, status
                FROM api_keys
                WHERE hashed_key = ? AND status = 'active'
                """,
                (hash_api_key(api_key),),
            ).fetchone()

    def get_project_for_tenant(self, tenant_id: str, project_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT id, tenant_id, name, created_at FROM projects WHERE id = ? AND tenant_id = ?",
                (project_id, tenant_id),
            ).fetchone()

    def insert_asset(
        self,
        *,
        tenant_id: str,
        project_id: str,
        asset_id: str | None = None,
        original_filename: str,
        storage_path: Path,
        entrypoint_path: Path,
        sha256: str,
        size: int,
        status: str = "ready",
    ) -> str:
        asset_id = asset_id or new_id("asset")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO assets (
                    id, tenant_id, project_id, original_filename, storage_path, entrypoint_path,
                    sha256, size, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    tenant_id,
                    project_id,
                    original_filename,
                    str(storage_path),
                    str(entrypoint_path),
                    sha256,
                    size,
                    status,
                    utc_now(),
                ),
            )
        return asset_id

    def get_asset(self, tenant_id: str, project_id: str, asset_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM assets
                WHERE id = ? AND tenant_id = ? AND project_id = ?
                """,
                (asset_id, tenant_id, project_id),
            ).fetchone()

    def insert_job(
        self,
        *,
        tenant_id: str,
        project_id: str,
        asset_id: str,
        test_type: str,
        request: dict[str, Any],
    ) -> str:
        job_id = new_id("job")
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, tenant_id, project_id, asset_id, test_type, status, request_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (job_id, tenant_id, project_id, asset_id, test_type, json_dumps(request), now, now),
            )
        return job_id

    def get_job(self, tenant_id: str, project_id: str, job_id: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE id = ? AND tenant_id = ? AND project_id = ?
                """,
                (job_id, tenant_id, project_id),
            ).fetchone()

    def claim_next_job(self) -> sqlite3.Row | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1",
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            now = utc_now()
            conn.execute(
                "UPDATE jobs SET status = 'running', updated_at = ?, started_at = ? WHERE id = ?",
                (now, now, row["id"]),
            )
            conn.execute("COMMIT")
            return conn.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()

    def update_job_status(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        now = utc_now()
        finished_at = now if status in TERMINAL_JOB_STATUSES else None
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    result_json = COALESCE(?, result_json),
                    error = ?,
                    updated_at = ?,
                    finished_at = COALESCE(?, finished_at)
                WHERE id = ?
                """,
                (
                    status,
                    json_dumps(result) if result is not None else None,
                    error,
                    now,
                    finished_at,
                    job_id,
                ),
            )

    def insert_artifact(
        self,
        *,
        job_id: str,
        kind: str,
        filename: str,
        path: Path,
        content_type: str,
        size: int,
    ) -> str:
        artifact_id = new_id("artifact")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts (id, job_id, kind, filename, path, content_type, size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, job_id, kind, filename, str(path), content_type, size, utc_now()),
            )
        return artifact_id

    def list_artifacts(self, tenant_id: str, project_id: str, job_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT artifacts.*
                    FROM artifacts
                    JOIN jobs ON jobs.id = artifacts.job_id
                    WHERE artifacts.job_id = ? AND jobs.tenant_id = ? AND jobs.project_id = ?
                    ORDER BY artifacts.created_at, artifacts.filename
                    """,
                    (job_id, tenant_id, project_id),
                )
            )

    def get_artifact(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
        artifact_id: str,
    ) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT artifacts.*
                FROM artifacts
                JOIN jobs ON jobs.id = artifacts.job_id
                WHERE artifacts.id = ?
                  AND artifacts.job_id = ?
                  AND jobs.tenant_id = ?
                  AND jobs.project_id = ?
                """,
                (artifact_id, job_id, tenant_id, project_id),
            ).fetchone()
