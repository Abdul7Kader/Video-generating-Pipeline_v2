"""Approval-bound production entry point; media stages follow in step 13."""

from app.api import database, require_project


def run_production(run_id: str):
    with database() as conn:
        run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (run_id,)).fetchone()
        if run is None:
            return
        require_project(conn, run["project_id"], lock=True)
        # Re-read under the same lock used by edits and approval dispatch.
        run = conn.execute("SELECT * FROM production_runs WHERE id = %s", (run_id,)).fetchone()
        if run["state"] != "QUEUED":
            return
        current = conn.execute(
            "SELECT id FROM script_versions WHERE project_id = %s ORDER BY version DESC LIMIT 1",
            (run["project_id"],),
        ).fetchone()
        if current["id"] != run["script_version_id"]:
            message = "Eine neuere Skriptversion liegt vor. Bitte diese Version prüfen und neu freigeben."
        else:
            message = "Die Videoerzeugung ist noch nicht verfügbar. Deine Skriptfreigabe bleibt gespeichert."
        # No simulated success or external media calls before the production stages exist.
        conn.execute("UPDATE production_runs SET state = 'FAILED', error_message = %s WHERE id = %s",
                     (message, run_id))
