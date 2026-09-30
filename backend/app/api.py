"""HTTP contract for projects, immutable scripts, approvals and status."""

import json
import os
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from app.script_contract import validate_script


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
    duration_seconds: int | None = Field(default=None, ge=3, le=12)
    pexels_queries: list[Text] | None = Field(default=None, min_length=2, max_length=4)


class ScriptInput(StrictModel):
    expected_version: int = Field(ge=0)
    title: Text
    narration: Text
    scenes: list[SceneInput] = Field(min_length=6, max_length=10)
    language: Literal["de-DE"] = "de-DE"
    target_duration_seconds: int | None = Field(default=None, ge=30, le=60)


class SceneOutput(StrictModel):
    position: int
    narration: str
    visual_description: str
    media_type: MediaType
    pexels_query: str | None
    wan_prompt: str | None
    duration_seconds: int | None = None
    pexels_queries: list[str] | None = None


class ScriptOutput(StrictModel):
    id: UUID
    project_id: UUID
    version: int
    title: str
    narration: str
    language: str = "de-DE"
    target_duration_seconds: int | None = None
    scenes: list[SceneOutput]
    created_at: datetime


class ScriptSummary(StrictModel):
    id: UUID
    version: int
    title: str
    created_at: datetime


class ScriptGenerationOutput(StrictModel):
    id: UUID
    project_id: UUID
    state: Literal["QUEUED", "RUNNING", "FAILED", "COMPLETED"]
    error_code: str | None
    error_message: str | None
    script_version: int | None
    created_at: datetime
    updated_at: datetime


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


class ProductionStepOutput(StrictModel):
    id: UUID
    position: int
    name: Literal['SCENES', 'SPEECH', 'GRAPHICS', 'ENCODING', 'STORAGE']
    state: Literal['PENDING', 'RUNNING', 'FAILED', 'COMPLETED']
    attempts: int
    max_attempts: int
    timeout_seconds: int
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class ProductionRunOutput(StrictModel):
    id: UUID
    project_id: UUID
    state: Literal['QUEUED', 'RUNNING', 'FAILED', 'COMPLETED']
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    can_resume: bool
    started_at: datetime | None
    deadline_at: datetime | None
    available_at: datetime
    steps: list[ProductionStepOutput]


class ProjectStatus(StrictModel):
    project_id: UUID
    latest_script_version: int | None
    script_approved: bool
    production_run_id: UUID | None
    production_state: Literal["QUEUED", "RUNNING", "FAILED", "COMPLETED"] | None
    production_error: str | None
    final_artifact_id: UUID | None
    video_approved: bool
    production_steps: list[ProductionStepOutput] = Field(default_factory=list)
    production_error_code: str | None = None
    production_can_resume: bool = False
    production_cancel_requested: bool = False


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


@router.post(
    "/projects/{project_id}/script-generations",
    response_model=ScriptGenerationOutput, status_code=202,
    responses={200: {"model": ScriptGenerationOutput, "description": "Existing active job"}},
)
def start_script_generation(project_id: UUID, response: Response):
    with database() as conn:
        require_project(conn, project_id, lock=True)
        existing_script = conn.execute(
            "SELECT 1 FROM script_versions WHERE project_id = %s LIMIT 1", (project_id,),
        ).fetchone()
        if existing_script:
            raise problem(409, "SCRIPT_EXISTS", "Project already has a script")
        active = conn.execute(
            "SELECT * FROM script_generation_jobs WHERE project_id = %s "
            "AND state IN ('QUEUED', 'RUNNING') ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if active:
            response.status_code = 200
            return active
        job = conn.execute(
            "INSERT INTO script_generation_jobs (project_id) VALUES (%s) RETURNING *",
            (project_id,),
        ).fetchone()
    try:
        queue = Queue("default", connection=Redis.from_url(os.environ["REDIS_URL"]))
        queue.enqueue("app.script_jobs.run_generation", str(job["id"]),
                      job_id=str(job["id"]), job_timeout=300, result_ttl=0)
    except (RedisError, OSError, KeyError) as exc:
        with database() as conn:
            conn.execute(
                "UPDATE script_generation_jobs SET state = 'FAILED', error_code = 'QUEUE_UNAVAILABLE', "
                "error_message = 'Skript-Worker nicht erreichbar. Bitte erneut versuchen.', "
                "updated_at = now() WHERE id = %s", (job["id"],),
            )
        raise problem(503, "QUEUE_UNAVAILABLE", "Script worker is unavailable") from exc
    return job


@router.get("/projects/{project_id}/script-generations/{job_id}", response_model=ScriptGenerationOutput)
def get_script_generation(project_id: UUID, job_id: UUID):
    with database() as conn:
        require_project(conn, project_id)
        conn.execute(
            "UPDATE script_generation_jobs SET state = 'FAILED', error_code = 'WORKER_INTERRUPTED', "
            "error_message = 'Der Skriptauftrag wurde unterbrochen. Bitte erneut versuchen.', "
            "updated_at = now() WHERE id = %s AND project_id = %s AND "
            "((state = 'RUNNING' AND updated_at < now() - interval '6 minutes') OR "
            "(state = 'QUEUED' AND updated_at < now() - interval '15 minutes'))",
            (job_id, project_id),
        )
        job = conn.execute(
            "SELECT * FROM script_generation_jobs WHERE id = %s AND project_id = %s",
            (job_id, project_id),
        ).fetchone()
        if job is None:
            raise problem(404, "JOB_NOT_FOUND", "Script generation job not found")
        return job


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
            if project["mode"] == "LOKAL" and ((scene.pexels_query is None and scene.pexels_queries is None) or scene.wan_prompt is not None):
                raise problem(422, "MODE_MISMATCH", "LOKAL scenes need a Pexels query only")
            if project["mode"] == "CLOUD" and (scene.wan_prompt is None or scene.pexels_query is not None or scene.pexels_queries is not None):
                raise problem(422, "MODE_MISMATCH", "CLOUD scenes need a Wan prompt only")
        if current and body.target_duration_seconds is None:
            latest = conn.execute(
                "SELECT target_duration_seconds FROM script_versions WHERE project_id = %s AND version = %s",
                (project_id, current),
            ).fetchone()
            if latest["target_duration_seconds"] is not None:
                raise problem(422, "INVALID_SCRIPT", "Bitte Dauer und vollständige Szenenfelder beim Bearbeiten erhalten.")
        if body.target_duration_seconds is not None:
            payload = {
                "title": body.title, "language": body.language, "mode": project["mode"],
                "target_duration_seconds": body.target_duration_seconds,
                "scenes": [
                    {"index": position, "duration_seconds": scene.duration_seconds,
                     "narration": scene.narration, "visual_description": scene.visual_description,
                     "media_type": project["media_type"],
                     **({"pexels_queries": scene.pexels_queries} if project["mode"] == "LOKAL"
                        else {"wan_prompt": scene.wan_prompt})}
                    for position, scene in enumerate(body.scenes, 1)
                ],
            }
            try:
                validate_script(json.dumps(payload), project["mode"])
            except ValueError as exc:
                raise problem(422, "INVALID_SCRIPT", f"Bitte Skript prüfen: {exc}") from exc
            if body.narration != " ".join(scene.narration for scene in body.scenes):
                raise problem(422, "INVALID_SCRIPT", "Der gesamte Sprechertext muss den Szenentexten entsprechen.")
            if any(scene.pexels_queries and scene.pexels_query not in (None, scene.pexels_queries[0]) for scene in body.scenes):
                raise problem(422, "INVALID_SCRIPT", "Der erste Pexels-Suchbegriff muss mit der Suchliste übereinstimmen.")
        script = conn.execute(
            "INSERT INTO script_versions (project_id, version, title, narration, language, target_duration_seconds) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
            (project_id, current + 1, body.title, body.narration, body.language, body.target_duration_seconds),
        ).fetchone()
        scenes = []
        for position, scene in enumerate(body.scenes, 1):
            saved = conn.execute(
                "INSERT INTO scenes (project_id, script_version_id, position, narration, "
                "visual_description, media_type, pexels_query, wan_prompt, duration_seconds, pexels_queries) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "RETURNING position, narration, visual_description, media_type, pexels_query, wan_prompt, duration_seconds, pexels_queries",
                (project_id, script["id"], position, scene.narration, scene.visual_description,
                 project["media_type"], scene.pexels_queries[0] if scene.pexels_queries else scene.pexels_query,
                 scene.wan_prompt, scene.duration_seconds, Jsonb(scene.pexels_queries) if scene.pexels_queries else None),
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
            "SELECT position, narration, visual_description, media_type, pexels_query, wan_prompt, "
            "duration_seconds, pexels_queries "
            "FROM scenes WHERE script_version_id = %s ORDER BY position", (script["id"],),
        ).fetchall()
    return {**script, "scenes": scenes}


@router.post(
    "/projects/{project_id}/scripts/{version}/approval",
    response_model=ScriptApprovalOutput,
    status_code=201,
    responses={
        200: {"model": ScriptApprovalOutput, "description": "Existing approval"},
        503: {"model": ErrorEnvelope, "description": "Approval saved; retry dispatch with the same version"},
    },
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
        else:
            approval = conn.execute(
                "INSERT INTO approvals (project_id, kind, script_version_id) "
                "VALUES (%s, 'SCRIPT', %s) RETURNING id", (project_id, script["id"]),
            ).fetchone()
            run = conn.execute(
                "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
                "VALUES (%s, %s, %s) RETURNING id, state",
                (project_id, script["id"], approval["id"]),
            ).fetchone()
            from app.production_jobs import ensure_steps
            ensure_steps(conn, run['id'])
            existing = {
                "id": approval["id"], "project_id": project_id,
                "script_version_id": script["id"], "production_run_id": run["id"],
                "production_state": run["state"],
            }
    # Commit first: a fast worker must be able to see the approval and its run.
    # A second project lock serializes dispatch, including retries after Redis errors.
    with database() as conn:
        require_project(conn, project_id, lock=True)
        run = conn.execute("SELECT * FROM production_runs WHERE id = %s",
                           (existing["production_run_id"],)).fetchone()
        existing["production_state"] = run["state"]
        if run["state"] == "QUEUED":
            try:
                connection = Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=3, socket_timeout=3)
                queue = Queue("default", connection=connection)
                from app.production_dispatch import dispatch_locked
                dispatch_locked(conn, run, queue)
            except (RedisError, OSError, KeyError) as exc:
                raise problem(503, "QUEUE_UNAVAILABLE",
                              "Freigabe gespeichert. Der Produktionsauftrag konnte noch nicht übergeben werden. "
                              "Bitte dieselbe Version erneut freigeben.") from exc
    return existing


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
            "SELECT s.id, s.version, a.id AS approval_id, r.id AS run_id, r.state, r.error_message, "
            "f.id AS final_id, va.id AS video_approval_id "
            "FROM script_versions s "
            "LEFT JOIN approvals a ON a.script_version_id = s.id AND a.kind = 'SCRIPT' "
            "LEFT JOIN production_runs r ON r.script_approval_id = a.id "
            "LEFT JOIN artifacts f ON f.production_run_id = r.id AND f.kind = 'FINAL' "
            "LEFT JOIN approvals va ON va.artifact_id = f.id AND va.kind = 'VIDEO' "
            "WHERE s.project_id = %s ORDER BY s.version DESC LIMIT 1", (project_id,),
        ).fetchone()
        production = production_output(conn, project_id, row['run_id']) if row and row['run_id'] else None
    return {
        "project_id": project_id,
        "latest_script_version": row["version"] if row else None,
        "script_approved": bool(row and row["approval_id"]),
        "production_run_id": row["run_id"] if row else None,
        "production_state": row["state"] if row else None,
        "production_error": row["error_message"] if row else None,
        "final_artifact_id": row["final_id"] if row else None,
        "video_approved": bool(row and row["video_approval_id"]),
        "production_steps": production['steps'] if production else [],
        "production_error_code": production['error_code'] if production else None,
        "production_can_resume": production['can_resume'] if production else False,
        "production_cancel_requested": production['cancel_requested'] if production else False,
    }


def production_output(conn, project_id, run_id):
    run = conn.execute('SELECT * FROM production_runs WHERE id = %s AND project_id = %s',
                       (run_id, project_id)).fetchone()
    if run is None:
        raise problem(404, 'RUN_NOT_FOUND', 'Produktionsauftrag nicht gefunden.')
    steps = conn.execute('SELECT id, position, name, state, attempts, max_attempts, timeout_seconds, '
                         'error_code, error_message, updated_at FROM production_steps '
                         'WHERE production_run_id = %s ORDER BY position', (run_id,)).fetchall()
    current = conn.execute('SELECT id FROM script_versions WHERE project_id = %s ORDER BY version DESC LIMIT 1',
                           (project_id,)).fetchone()
    can_resume = (run['state'] == 'FAILED' and not run['cancel_requested']
                  and current['id'] == run['script_version_id']
                  and (run['deadline_at'] is None or run['deadline_at'] > datetime.now(timezone.utc))
                  and all(step['state'] == 'COMPLETED' or step['attempts'] < step['max_attempts'] for step in steps))
    return {**{name: run[name] for name in ('id', 'project_id', 'state', 'error_code', 'error_message',
                                           'cancel_requested', 'started_at', 'deadline_at', 'available_at')},
            'can_resume': can_resume, 'steps': steps}


@router.get('/projects/{project_id}/production-runs/{run_id}', response_model=ProductionRunOutput)
def get_production(project_id: UUID, run_id: UUID):
    with database() as conn:
        require_project(conn, project_id)
        return production_output(conn, project_id, run_id)


@router.post('/projects/{project_id}/production-runs/{run_id}/resume', response_model=ProductionRunOutput,
             responses={503: {'model': ErrorEnvelope, 'description': 'Resume saved; automatic dispatch pending'}})
def resume_production(project_id: UUID, run_id: UUID):
    from app.production_dispatch import dispatch_locked
    from app.production_jobs import ensure_steps, try_lock
    with database() as conn:
        require_project(conn, project_id, lock=True)
        output = production_output(conn, project_id, run_id)
        if not try_lock(conn, run_id):
            raise problem(409, 'RUN_ACTIVE', 'Der Produktionsauftrag wird bereits verarbeitet.')
        if output['state'] != 'QUEUED':
            if not output['can_resume']:
                raise problem(409, 'RESUME_NOT_ALLOWED', 'Dieser Auftrag kann nicht wiederaufgenommen werden. Bitte Status und Skriptversion prüfen.')
            ensure_steps(conn, run_id)
            conn.execute("UPDATE production_runs SET state = 'QUEUED', available_at = now(), "
                         "error_code = NULL, error_message = NULL, dispatch_number = dispatch_number + 1 WHERE id = %s", (run_id,))
    # Persist the requested resume before talking to Redis.
    with database() as conn:
        require_project(conn, project_id, lock=True)
        run = conn.execute('SELECT * FROM production_runs WHERE id = %s', (run_id,)).fetchone()
        try:
            queue = Queue('default', connection=Redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=3, socket_timeout=3))
            dispatch_locked(conn, run, queue)
        except (RedisError, OSError, KeyError) as exc:
            raise problem(503, 'QUEUE_UNAVAILABLE', 'Wiederaufnahme gespeichert. Die Übergabe wird automatisch erneut versucht.') from exc
        return production_output(conn, project_id, run_id)


@router.post('/projects/{project_id}/production-runs/{run_id}/cancel', response_model=ProductionRunOutput)
def cancel_production(project_id: UUID, run_id: UUID):
    with database() as conn:
        require_project(conn, project_id, lock=True)
        output = production_output(conn, project_id, run_id)
        if output['cancel_requested']:
            return output
        if output['state'] not in ('QUEUED', 'RUNNING'):
            raise problem(409, 'CANCEL_NOT_ALLOWED', 'Dieser Produktionsauftrag ist bereits beendet.')
        if output['state'] == 'QUEUED':
            conn.execute("UPDATE production_runs SET state = 'FAILED', cancel_requested = true, "
                         "error_code = 'CANCELLED', error_message = 'Die Videoproduktion wurde abgebrochen.' WHERE id = %s", (run_id,))
        else:
            conn.execute('UPDATE production_runs SET cancel_requested = true WHERE id = %s', (run_id,))
        return production_output(conn, project_id, run_id)


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
