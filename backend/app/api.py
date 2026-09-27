"""HTTP contract for projects, immutable scripts, approvals and status."""

import os
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from psycopg.rows import dict_row


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Mode = Literal["LOKAL", "CLOUD"]
MediaType = Literal["STOCK_VIDEO", "AI_GENERATED_VIDEO"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInput(StrictModel):
    idea: Text
    mode: Mode


class ProjectOutput(StrictModel):
    id: UUID
    idea: str
    mode: Mode
    media_type: MediaType
    created_at: datetime


class SceneInput(StrictModel):
    narration: Text
    visual_description: Text
    pexels_query: Text | None = None
    wan_prompt: Text | None = None


class ScriptInput(StrictModel):
    expected_version: int = Field(ge=0)
    title: Text
    narration: Text
    scenes: list[SceneInput] = Field(min_length=6, max_length=10)


class SceneOutput(StrictModel):
    position: int
    narration: str
    visual_description: str
    media_type: MediaType
    pexels_query: str | None
    wan_prompt: str | None


class ScriptOutput(StrictModel):
    id: UUID
    project_id: UUID
    version: int
    title: str
    narration: str
    scenes: list[SceneOutput]
    created_at: datetime


class ScriptSummary(StrictModel):
    id: UUID
    version: int
    title: str
    created_at: datetime


class ScriptApprovalOutput(StrictModel):
    id: UUID
    project_id: UUID
    script_version_id: UUID
    production_run_id: UUID
    production_state: Literal["QUEUED", "RUNNING", "FAILED", "COMPLETED"]


class VideoApprovalInput(StrictModel):
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class VideoApprovalOutput(StrictModel):
    id: UUID
    project_id: UUID
    artifact_id: UUID
    checksum_sha256: str


class ProjectStatus(StrictModel):
    project_id: UUID
    latest_script_version: int | None
    script_approved: bool
    production_run_id: UUID | None
    production_state: Literal["QUEUED", "RUNNING", "FAILED", "COMPLETED"] | None
    final_artifact_id: UUID | None
    video_approved: bool


class ArtifactOutput(StrictModel):
    id: UUID
    project_id: UUID
    kind: Literal["SOURCE", "INTERMEDIATE", "FINAL"]
    media_type: Literal["STOCK_VIDEO", "AI_GENERATED_VIDEO", "FINAL_VIDEO"]
    checksum_sha256: str
    created_at: datetime
    content_available: bool = False


class ErrorInfo(StrictModel):
    code: str
    message: str
    fields: list[str] | None = None


class ErrorEnvelope(StrictModel):
    error: ErrorInfo


router = APIRouter(
    prefix="/api",
    responses={
        404: {"model": ErrorEnvelope, "description": "Resource not found"},
        409: {"model": ErrorEnvelope, "description": "Version or state conflict"},
        422: {"model": ErrorEnvelope, "description": "Invalid request"},
    },
)


def database():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def problem(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def install_error_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "code": "HTTP_ERROR", "message": str(exc.detail),
        }
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        fields = [".".join(map(str, error["loc"])) for error in exc.errors()]
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": "Invalid request", "fields": fields}},
            status_code=422,
        )

    @app.exception_handler(psycopg.IntegrityError)
    async def constraint_error(_request: Request, _exc: psycopg.IntegrityError):
        return JSONResponse(
            {"error": {"code": "CONFLICT", "message": "Data conflicts with the current project state"}},
            status_code=409,
        )

    @app.exception_handler(psycopg.errors.RaiseException)
    async def state_error(_request: Request, _exc: psycopg.errors.RaiseException):
        return JSONResponse(
            {"error": {"code": "STATE_CONFLICT", "message": "Operation violates project state"}},
            status_code=409,
        )


def require_project(conn, project_id: UUID, lock: bool = False):
    suffix = " FOR UPDATE" if lock else ""
    row = conn.execute("SELECT * FROM projects WHERE id = %s" + suffix, (project_id,)).fetchone()
    if row is None:
        raise problem(404, "PROJECT_NOT_FOUND", "Project not found")
    return row


def require_artifact(conn, artifact_id: UUID):
    row = conn.execute(
        "SELECT id, project_id, kind, media_type, checksum_sha256, created_at "
        "FROM artifacts WHERE id = %s", (artifact_id,),
    ).fetchone()
    if row is None:
        raise problem(404, "ARTIFACT_NOT_FOUND", "Artifact not found")
    return row


@router.post("/projects", response_model=ProjectOutput, status_code=201)
def create_project(body: ProjectInput):
    media_type = "STOCK_VIDEO" if body.mode == "LOKAL" else "AI_GENERATED_VIDEO"
    with database() as conn:
        row = conn.execute(
            "INSERT INTO projects (idea, mode, media_type) VALUES (%s, %s, %s) RETURNING *",
            (body.idea, body.mode, media_type),
        ).fetchone()
    return row


@router.get("/projects/{project_id}", response_model=ProjectOutput)
def get_project(project_id: UUID):
    with database() as conn:
        return require_project(conn, project_id)


@router.get("/projects/{project_id}/scripts", response_model=list[ScriptSummary])
def list_scripts(project_id: UUID):
    with database() as conn:
        require_project(conn, project_id)
        return conn.execute(
            "SELECT id, version, title, created_at FROM script_versions "
            "WHERE project_id = %s ORDER BY version DESC", (project_id,),
        ).fetchall()


@router.post("/projects/{project_id}/scripts", response_model=ScriptOutput, status_code=201)
def create_script(project_id: UUID, body: ScriptInput):
    with database() as conn:
        project = require_project(conn, project_id, lock=True)
        current = conn.execute(
            "SELECT coalesce(max(version), 0) AS version FROM script_versions WHERE project_id = %s",
            (project_id,),
        ).fetchone()["version"]
        if body.expected_version != current:
            raise problem(409, "VERSION_CONFLICT", "Script version changed; reload the project")
        for scene in body.scenes:
            if project["mode"] == "LOKAL" and (scene.pexels_query is None or scene.wan_prompt is not None):
                raise problem(422, "MODE_MISMATCH", "LOKAL scenes need a Pexels query only")
            if project["mode"] == "CLOUD" and (scene.wan_prompt is None or scene.pexels_query is not None):
                raise problem(422, "MODE_MISMATCH", "CLOUD scenes need a Wan prompt only")
        script = conn.execute(
            "INSERT INTO script_versions (project_id, version, title, narration) "
            "VALUES (%s, %s, %s, %s) RETURNING *",
            (project_id, current + 1, body.title, body.narration),
        ).fetchone()
        scenes = []
        for position, scene in enumerate(body.scenes, 1):
            saved = conn.execute(
                "INSERT INTO scenes (project_id, script_version_id, position, narration, "
                "visual_description, media_type, pexels_query, wan_prompt) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING position, narration, visual_description, media_type, pexels_query, wan_prompt",
                (project_id, script["id"], position, scene.narration, scene.visual_description,
                 project["media_type"], scene.pexels_query, scene.wan_prompt),
            ).fetchone()
            scenes.append(saved)
    return {**script, "scenes": scenes}


@router.get("/projects/{project_id}/scripts/{version}", response_model=ScriptOutput)
def get_script(project_id: UUID, version: int):
    with database() as conn:
        require_project(conn, project_id)
        script = conn.execute(
            "SELECT * FROM script_versions WHERE project_id = %s AND version = %s",
            (project_id, version),
        ).fetchone()
        if script is None:
            raise problem(404, "SCRIPT_NOT_FOUND", "Script version not found")
        scenes = conn.execute(
            "SELECT position, narration, visual_description, media_type, pexels_query, wan_prompt "
            "FROM scenes WHERE script_version_id = %s ORDER BY position", (script["id"],),
        ).fetchall()
    return {**script, "scenes": scenes}


@router.post(
    "/projects/{project_id}/scripts/{version}/approval",
    response_model=ScriptApprovalOutput,
    status_code=201,
    responses={200: {"model": ScriptApprovalOutput, "description": "Existing approval"}},
)
def approve_script(project_id: UUID, version: int, response: Response):
    with database() as conn:
        require_project(conn, project_id, lock=True)
        script = conn.execute(
            "SELECT id, version FROM script_versions WHERE project_id = %s "
            "ORDER BY version DESC LIMIT 1", (project_id,),
        ).fetchone()
        if script is None or script["version"] != version:
            raise problem(409, "VERSION_CONFLICT", "Only the current script version can be approved")
        existing = conn.execute(
            "SELECT a.id, a.project_id, a.script_version_id, r.id AS production_run_id, "
            "r.state AS production_state FROM approvals a "
            "JOIN production_runs r ON r.script_approval_id = a.id "
            "WHERE a.script_version_id = %s AND a.kind = 'SCRIPT'", (script["id"],),
        ).fetchone()
        if existing:
            response.status_code = 200
            return existing
        approval = conn.execute(
            "INSERT INTO approvals (project_id, kind, script_version_id) "
            "VALUES (%s, 'SCRIPT', %s) RETURNING id", (project_id, script["id"]),
        ).fetchone()
        run = conn.execute(
            "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
            "VALUES (%s, %s, %s) RETURNING id, state",
            (project_id, script["id"], approval["id"]),
        ).fetchone()
    return {
        "id": approval["id"], "project_id": project_id,
        "script_version_id": script["id"], "production_run_id": run["id"],
        "production_state": run["state"],
    }


@router.post(
    "/projects/{project_id}/videos/{artifact_id}/approval",
    response_model=VideoApprovalOutput,
    status_code=201,
    responses={200: {"model": VideoApprovalOutput, "description": "Existing approval"}},
)
def approve_video(project_id: UUID, artifact_id: UUID, body: VideoApprovalInput, response: Response):
    with database() as conn:
        require_project(conn, project_id)
        artifact = conn.execute(
            "SELECT id, project_id, kind, checksum_sha256, production_run_id "
            "FROM artifacts WHERE id = %s AND project_id = %s FOR UPDATE",
            (artifact_id, project_id),
        ).fetchone()
        if artifact is None:
            raise problem(404, "ARTIFACT_NOT_FOUND", "Artifact not found")
        if artifact["kind"] != "FINAL" or artifact["checksum_sha256"] != body.checksum_sha256:
            raise problem(409, "ARTIFACT_CONFLICT", "Final artifact or checksum does not match")
        run = conn.execute(
            "SELECT state FROM production_runs WHERE id = %s", (artifact["production_run_id"],),
        ).fetchone()
        if run["state"] != "COMPLETED":
            raise problem(409, "STATE_CONFLICT", "Final video is not complete")
        existing = conn.execute(
            "SELECT id, project_id, artifact_id, checksum_sha256 FROM approvals "
            "WHERE artifact_id = %s AND kind = 'VIDEO'", (artifact_id,),
        ).fetchone()
        if existing:
            response.status_code = 200
            return existing
        approval = conn.execute(
            "INSERT INTO approvals (project_id, kind, artifact_id, checksum_sha256) "
            "VALUES (%s, 'VIDEO', %s, %s) "
            "RETURNING id, project_id, artifact_id, checksum_sha256",
            (project_id, artifact_id, body.checksum_sha256),
        ).fetchone()
    return approval


@router.get("/projects/{project_id}/status", response_model=ProjectStatus)
def get_status(project_id: UUID):
    with database() as conn:
        require_project(conn, project_id)
        row = conn.execute(
            "SELECT s.id, s.version, a.id AS approval_id, r.id AS run_id, r.state, "
            "f.id AS final_id, va.id AS video_approval_id "
            "FROM script_versions s "
            "LEFT JOIN approvals a ON a.script_version_id = s.id AND a.kind = 'SCRIPT' "
            "LEFT JOIN production_runs r ON r.script_approval_id = a.id "
            "LEFT JOIN artifacts f ON f.production_run_id = r.id AND f.kind = 'FINAL' "
            "LEFT JOIN approvals va ON va.artifact_id = f.id AND va.kind = 'VIDEO' "
            "WHERE s.project_id = %s ORDER BY s.version DESC LIMIT 1", (project_id,),
        ).fetchone()
    return {
        "project_id": project_id,
        "latest_script_version": row["version"] if row else None,
        "script_approved": bool(row and row["approval_id"]),
        "production_run_id": row["run_id"] if row else None,
        "production_state": row["state"] if row else None,
        "final_artifact_id": row["final_id"] if row else None,
        "video_approved": bool(row and row["video_approval_id"]),
    }


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOutput)
def get_artifact(artifact_id: UUID):
    with database() as conn:
        artifact = require_artifact(conn, artifact_id)
    return artifact


@router.get(
    "/artifacts/{artifact_id}/content",
    responses={
        200: {"description": "MP4 file after task 18", "content": {"video/mp4": {}}},
        501: {"model": ErrorEnvelope, "description": "Media delivery awaits task 18"},
    },
)
def get_artifact_content(artifact_id: UUID):
    with database() as conn:
        require_artifact(conn, artifact_id)
    raise problem(501, "MEDIA_NOT_AVAILABLE", "Media delivery is implemented in task 18")
