"""Persist validated script generations run by RQ."""

import os
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.antigravity import GenerationFailure, generate


def _database():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def _fail(job_id: UUID, code: str, message: str) -> None:
    with _database() as conn:
        conn.execute(
            "UPDATE script_generation_jobs SET state = 'FAILED', error_code = %s, "
            "error_message = %s, updated_at = now() WHERE id = %s AND state <> 'COMPLETED'",
            (code, message, job_id),
        )


def run_generation(job_id: str) -> None:
    job_uuid = UUID(job_id)
    with _database() as conn:
        job = conn.execute(
            "SELECT j.*, p.idea, p.mode, p.media_type FROM script_generation_jobs j "
            "JOIN projects p ON p.id = j.project_id WHERE j.id = %s FOR UPDATE OF j",
            (job_uuid,),
        ).fetchone()
        if job is None or job["state"] != "QUEUED":
            return
        conn.execute(
            "UPDATE script_generation_jobs SET state = 'RUNNING', updated_at = now() WHERE id = %s",
            (job_uuid,),
        )

    try:
        script = generate(job["idea"], job["mode"])
        with _database() as conn:
            conn.execute("SELECT id FROM projects WHERE id = %s FOR UPDATE", (job["project_id"],))
            current = conn.execute(
                "SELECT coalesce(max(version), 0) AS version FROM script_versions WHERE project_id = %s",
                (job["project_id"],),
            ).fetchone()["version"]
            if current:
                raise GenerationFailure("SCRIPT_EXISTS", "Dieses Projekt hat bereits ein Skript. Bitte die vorhandene Version prüfen.")
            saved = conn.execute(
                "INSERT INTO script_versions (project_id, version, title, narration, language, target_duration_seconds) "
                "VALUES (%s, 1, %s, %s, %s, %s) RETURNING id",
                (job["project_id"], script["title"],
                 " ".join(scene["narration"] for scene in script["scenes"]),
                 script["language"], script["target_duration_seconds"]),
            ).fetchone()
            for scene in script["scenes"]:
                queries = scene.get("pexels_queries")
                conn.execute(
                    "INSERT INTO scenes (project_id, script_version_id, position, narration, "
                    "visual_description, media_type, pexels_query, wan_prompt, duration_seconds, pexels_queries) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (job["project_id"], saved["id"], scene["index"], scene["narration"],
                     scene["visual_description"], job["media_type"],
                     queries[0] if queries else None, scene.get("wan_prompt"),
                     scene["duration_seconds"], Jsonb(queries) if queries else None),
                )
            conn.execute(
                "UPDATE script_generation_jobs SET state = 'COMPLETED', script_version = 1, "
                "updated_at = now() WHERE id = %s", (job_uuid,),
            )
    except GenerationFailure as exc:
        _fail(job_uuid, exc.code, str(exc))
    except Exception:
        _fail(job_uuid, "GENERATION_FAILED", "Skriptauftrag fehlgeschlagen. Bitte bewusst erneut versuchen.")
        raise
