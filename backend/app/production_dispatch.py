"""Recover the PostgreSQL outbox and interrupted runs through Redis/RQ."""

from datetime import datetime, timedelta, timezone

from app.api import database, require_project
from app.production_jobs import check_run, ensure_steps, fail_run, try_lock
from app.production_stages import RUN_TIMEOUT, StageFailure


def dispatch_locked(conn, run, queue):
    if run["state"] != "QUEUED" or run["available_at"] > datetime.now(timezone.utc):
        return
    number = run["dispatch_number"]
    job_id = str(run["id"]) + (f"-{number}" if number else "")
    job = queue.fetch_job(job_id)
    if job:
        status = job.get_status(refresh=True)
        if status in ("queued", "deferred", "scheduled"):
            return
        # A worker may be just about to acquire its PostgreSQL lock.
        if status == "started" and job.started_at and job.started_at > datetime.now(timezone.utc) - timedelta(seconds=30):
            return
        number += 1
        conn.execute("UPDATE production_runs SET dispatch_number = %s WHERE id = %s", (number, run["id"]))
        job_id = f"{run['id']}-{number}"
    # If enqueue succeeded but its response was lost, the next pass finds this same ID.
    queue.enqueue("app.production_jobs.run_production", str(run["id"]), job_id=job_id,
                  job_timeout=RUN_TIMEOUT + 60, result_ttl=86400, failure_ttl=86400)


def recover_productions(queue):
    with database() as conn:
        candidates = conn.execute("SELECT id FROM production_runs WHERE state IN ('QUEUED', 'RUNNING') "
                                  "AND available_at <= now() ORDER BY created_at LIMIT 100").fetchall()
    for candidate in candidates:
        with database() as conn:
            if not try_lock(conn, candidate["id"]):
                continue
            run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (candidate["id"],)).fetchone()
            require_project(conn, run["project_id"], lock=True)
            # Re-read after the project lock, which is shared with approvals and edits.
            run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (run["id"],)).fetchone()
            if run["state"] not in ("QUEUED", "RUNNING"):
                continue
            step = conn.execute("SELECT * FROM production_steps WHERE production_run_id = %s AND state = 'RUNNING'",
                                (run["id"],)).fetchone()
            if step and not try_lock(conn, step["id"]):
                # An orphaned stage process still owns this step; its watchdog bounds it.
                continue
            try:
                check_run(conn, run["id"])
            except StageFailure as exc:
                fail_run(conn, run["id"], exc, step)
                continue
            ensure_steps(conn, run["id"])
            if run["state"] == "RUNNING":
                interrupted = StageFailure("WORKER_INTERRUPTED", "Der Worker wurde unterbrochen; der Schritt wird wiederaufgenommen.", True)
                fail_run(conn, run["id"], interrupted, step)
                if step is None:
                    # Crash between two completed checkpoints consumes no stage attempt.
                    conn.execute("UPDATE production_runs SET state = 'QUEUED', available_at = now(), "
                                 "dispatch_number = dispatch_number + 1 WHERE id = %s", (run["id"],))
                run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (run["id"],)).fetchone()
            dispatch_locked(conn, run, queue)
