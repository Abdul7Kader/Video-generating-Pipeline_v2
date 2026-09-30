"""PostgreSQL checkpoints and bounded, approval-bound RQ production."""

from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from app.api import database, require_project
from app.production_stages import STAGES, RUN_TIMEOUT, StageFailure, StageResult, kill_process_tree


def try_lock(conn, identity):
    return conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 13)) AS locked",
                        (str(identity),)).fetchone()["locked"]


def ensure_steps(conn, run_id):
    for position, (name, timeout) in enumerate(STAGES, 1):
        conn.execute("INSERT INTO production_steps (production_run_id, position, name, timeout_seconds) "
                     "VALUES (%s, %s, %s, %s) ON CONFLICT (production_run_id, name) DO NOTHING",
                     (run_id, position, name, timeout))


def check_run(conn, run_id):
    row = conn.execute("SELECT r.*, s.id AS latest_id FROM production_runs r "
                       "JOIN LATERAL (SELECT id FROM script_versions WHERE project_id = r.project_id "
                       "ORDER BY version DESC LIMIT 1) s ON true WHERE r.id = %s", (run_id,)).fetchone()
    if row["cancel_requested"]:
        raise StageFailure("CANCELLED", "Die Videoproduktion wurde abgebrochen.")
    if row["latest_id"] != row["script_version_id"]:
        raise StageFailure("VERSION_SUPERSEDED", "Eine neuere Skriptversion liegt vor. Bitte diese Version prüfen und neu freigeben.")
    if row["deadline_at"] and row["deadline_at"] <= datetime.now(timezone.utc):
        raise StageFailure("RUN_TIMEOUT", "Die maximale Produktionslaufzeit von drei Stunden wurde überschritten.")
    return row


def fail_run(conn, run_id, failure, step=None):
    if failure.retryable:
        try:
            check_run(conn, run_id)
        except StageFailure as blocked:
            failure = blocked
    if step:
        conn.execute("UPDATE production_steps SET state = 'FAILED', error_code = %s, error_message = %s, "
                     "updated_at = now() WHERE id = %s AND state = 'RUNNING'",
                     (failure.code, str(failure), step["id"]))
        conn.execute("UPDATE production_attempts SET state = 'FAILED', error_code = %s, error_message = %s, "
                     "finished_at = now() WHERE step_id = %s AND number = %s AND state = 'RUNNING'",
                     (failure.code, str(failure), step["id"], step["attempts"]))
    conn.execute("UPDATE production_runs SET state = 'FAILED', error_code = %s, error_message = %s WHERE id = %s",
                 (failure.code, str(failure), run_id))
    if failure.retryable and step and step["attempts"] < step["max_attempts"]:
        delay = 5 if step["attempts"] == 1 else 30
        conn.execute("UPDATE production_runs SET state = 'QUEUED', available_at = now() + %s * interval '1 second', "
                     "dispatch_number = dispatch_number + 1 WHERE id = %s", (delay, run_id))


def stage_command():
    return [sys.executable, "-m", "app.production_stage_runner"]


def run_stage(conn, step, context, timeout):
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(stage_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8", **flags)
    started = time.monotonic()
    try:
        process.stdin.write(json.dumps({"name": step["name"], "context": context,
                                       "timeout_seconds": timeout}, default=str) + "\n")
        process.stdin.flush()
        while True:
            check_run(conn, context["run_id"])
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise StageFailure("STEP_TIMEOUT", "Das Zeitlimit des Produktionsschritts wurde überschritten.", True)
            try:
                output, _ = process.communicate(timeout=min(1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            if time.monotonic() - started >= timeout - 1:
                raise StageFailure("STEP_TIMEOUT", "Das Zeitlimit des Produktionsschritts wurde überschritten.", True)
            raise StageFailure("STAGE_PROCESS_FAILED", "Der Medienprozess wurde unerwartet beendet.", True)
        try:
            value = json.loads(output)
            if isinstance(value, dict) and "error" in value:
                error = value["error"]
                raise StageFailure(error["code"], error["message"], error["retryable"] is True)
            result = StageResult.model_validate(value)
            keys = [artifact.key for artifact in result.artifacts]
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate artifact keys")
            for artifact in result.artifacts:
                if artifact.kind == 'SOURCE' and artifact.media_type != context['media_type']:
                    raise StageFailure('MODE_MISMATCH', 'Die Szenenquelle passt nicht zum freigegebenen Videomodus.')
                if artifact.kind == 'FINAL' and step['name'] != 'STORAGE':
                    raise ValueError('only the storage checkpoint publishes final artifacts')
            if result.sources:
                if step['name'] != 'SCENES' or context['mode'] != 'LOKAL':
                    raise ValueError('Pexels manifest outside LOKAL scenes')
                expected = {s['position']: s['duration_seconds'] for s in context['scenes']}
                actual = {s.scene_position: s.scene_duration_seconds for s in result.sources}
                source_keys = {s.artifact_key for s in result.sources}
                if (expected != actual or len(actual) != len(result.sources) or source_keys != set(keys)
                        or len(source_keys) != len(result.sources) or any(a.kind != 'SOURCE' for a in result.artifacts)):
                    raise ValueError('incomplete scene manifest')
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise StageFailure("INVALID_STAGE_RESULT", "Der Produktionsschritt hat ein ungültiges Ergebnis geliefert.") from exc
    finally:
        if process.poll() is None:
            kill_process_tree(process.pid)
        process.wait(timeout=10)
        for stream in (process.stdin, process.stdout):
            if stream and not stream.closed:
                stream.close()


def run_production(run_id: str):
    # Session lock survives transaction commits, but is released on process death.
    with database() as conn:
        conn.autocommit = True
        if not try_lock(conn, run_id):
            return
        run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (run_id,)).fetchone()
        if run is None or run["state"] != "QUEUED" or run["available_at"] > datetime.now(timezone.utc):
            return
        step = None
        try:
            with conn.transaction():
                project = require_project(conn, run["project_id"], lock=True)
                check_run(conn, run_id)
                ensure_steps(conn, run_id)
                run = conn.execute("UPDATE production_runs SET state = 'RUNNING', error_code = NULL, error_message = NULL, "
                                   "started_at = coalesce(started_at, now()), "
                                   "deadline_at = coalesce(deadline_at, now() + %s * interval '1 second') "
                                   "WHERE id = %s RETURNING *", (RUN_TIMEOUT, run_id)).fetchone()
            steps = conn.execute("SELECT * FROM production_steps WHERE production_run_id = %s ORDER BY position",
                                 (run_id,)).fetchall()
            script = conn.execute("SELECT * FROM script_versions WHERE id = %s", (run["script_version_id"],)).fetchone()
            scenes = conn.execute("SELECT * FROM scenes WHERE script_version_id = %s ORDER BY position",
                                  (run["script_version_id"],)).fetchall()
            results = {}
            for saved in steps:
                step = None
                if saved["state"] == "COMPLETED":
                    results[saved["name"]] = saved["result"]
                    continue
                with conn.transaction():
                    require_project(conn, run["project_id"], lock=True)
                    check_run(conn, run_id)
                    if saved["attempts"] >= saved["max_attempts"]:
                        raise StageFailure("RETRY_LIMIT", "Die maximale Anzahl von drei Versuchen wurde erreicht.")
                    step = conn.execute("UPDATE production_steps SET state = 'RUNNING', attempts = attempts + 1, "
                                        "error_code = NULL, error_message = NULL, updated_at = now() "
                                        "WHERE id = %s RETURNING *", (saved["id"],)).fetchone()
                    conn.execute("INSERT INTO production_attempts (step_id, number, state) VALUES (%s, %s, 'RUNNING')",
                                 (step["id"], step["attempts"]))
                context = {"run_id": run_id, "step_id": str(step["id"]), "attempt": step["attempts"],
                           "project_id": str(project["id"]), "mode": project["mode"], "media_type": project["media_type"],
                           "script": script, "scenes": scenes, "previous_results": results}
                timeout = min(step["timeout_seconds"], (run["deadline_at"] - datetime.now(timezone.utc)).total_seconds())
                result = run_stage(conn, step, context, timeout)
                with conn.transaction():
                    require_project(conn, run["project_id"], lock=True)
                    check_run(conn, run_id)
                    for artifact in result.artifacts:
                        saved_artifact = conn.execute("INSERT INTO artifacts (id, project_id, production_run_id, production_step_id, "
                                     "artifact_key, kind, media_type, storage_path, checksum_sha256) "
                                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                                     "ON CONFLICT (production_step_id, artifact_key) DO NOTHING RETURNING id",
                                     (uuid5(UUID(str(step["id"])), artifact.key), project["id"], run_id, step["id"],
                                      artifact.key, artifact.kind, artifact.media_type, artifact.storage_path, artifact.checksum_sha256)).fetchone()
                        if saved_artifact is None:
                            existing = conn.execute('SELECT kind, media_type, storage_path, checksum_sha256 FROM artifacts '
                                                    'WHERE production_step_id = %s AND artifact_key = %s', (step['id'], artifact.key)).fetchone()
                            if dict(existing) != artifact.model_dump(exclude={'key'}):
                                raise StageFailure('ARTIFACT_CONFLICT', 'Ein gespeichertes Zwischenergebnis stimmt nicht mit der Wiederaufnahme überein.')
                    results[step["name"]] = result.model_dump()
                    conn.execute("UPDATE production_steps SET state = 'COMPLETED', result = %s, updated_at = now() WHERE id = %s",
                                 (Jsonb(results[step["name"]]), step["id"]))
                    conn.execute("UPDATE production_attempts SET state = 'COMPLETED', finished_at = now() "
                                 "WHERE step_id = %s AND number = %s", (step["id"], step["attempts"]))
                step = None
            with conn.transaction():
                require_project(conn, run["project_id"], lock=True)
                check_run(conn, run_id)
                final = conn.execute("SELECT 1 FROM artifacts a JOIN production_steps s ON s.id = a.production_step_id "
                                     "WHERE a.production_run_id = %s AND a.kind = 'FINAL' AND s.name = 'STORAGE'", (run_id,)).fetchone()
                if not final:
                    raise StageFailure("FINAL_ARTIFACT_MISSING", "Die Produktion hat keine finale Videodatei bereitgestellt.")
                conn.execute("UPDATE production_runs SET state = 'COMPLETED' WHERE id = %s", (run_id,))
        except StageFailure as exc:
            with conn.transaction():
                require_project(conn, run['project_id'], lock=True)
                fail_run(conn, run_id, exc, step)
        except Exception:
            with conn.transaction():
                require_project(conn, run['project_id'], lock=True)
                fail_run(conn, run_id, StageFailure("STAGE_ERROR", "Der Produktionsschritt ist fehlgeschlagen."), step)
