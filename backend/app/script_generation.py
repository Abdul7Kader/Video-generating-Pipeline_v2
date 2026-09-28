"""Validated Antigravity script generation executed by an RQ worker."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import UUID

class GenerationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def make_prompt(idea: str, mode: str) -> str:
    media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
    source = ('"pexels_queries": ["English query", "German query"]'
              if mode == "LOKAL" else '"wan_prompt": "Detailed English video prompt"')
    return f"""Erstelle ein deutsches Skript für ein vertikales Kurzvideo.
Idee: {idea}
Produktionsmodus: {mode}
Antworte ausschließlich mit einem JSON-Objekt ohne Markdown und exakt diesen Schlüsseln:
{{"title":"Titel","language":"de-DE","mode":"{mode}","target_duration_seconds":42,
"scenes":[{{"index":1,"duration_seconds":7,"narration":"Deutscher Text",
"visual_description":"Konkretes Bild","media_type":"{media}",{source}}}]}}
Regeln: 6 bis 10 lückenlos nummerierte Szenen; jede dauert ganzzahlig 3 bis 12 Sekunden,
insgesamt exakt 30 bis 60 Sekunden. Titel maximal 120, Sprechertext maximal 400 und
Bildbeschreibung maximal 600 Zeichen. Keine zusätzlichen Schlüssel oder andere Medienquelle.
LOKAL benötigt 2 bis 4 unterschiedliche Suchbegriffe (maximal 100 Zeichen); CLOUD genau
einen englischen Wan-Prompt (maximal 1000 Zeichen)."""


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Doppelter Schlüssel: {key}")
        result[key] = value
    return result


def validate_script(raw: str, mode: str) -> dict:
    try:
        data = json.loads(raw, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GenerationError("INVALID_RESPONSE", "Antigravity lieferte kein gültiges Skript.") from exc
    expected = {"title", "language", "mode", "target_duration_seconds", "scenes"}
    if not isinstance(data, dict) or set(data) != expected:
        raise GenerationError("INVALID_RESPONSE", "Das Skript hat fehlende oder unbekannte Felder.")
    if not isinstance(data["title"], str) or not data["title"].strip() or len(data["title"]) > 120:
        raise GenerationError("INVALID_RESPONSE", "Der Skripttitel ist ungültig.")
    if data["language"] != "de-DE" or data["mode"] != mode:
        raise GenerationError("INVALID_RESPONSE", "Sprache oder Produktionsmodus stimmen nicht.")
    scenes = data["scenes"]
    if not isinstance(scenes, list) or not 6 <= len(scenes) <= 10:
        raise GenerationError("INVALID_RESPONSE", "Das Skript muss 6 bis 10 Szenen enthalten.")
    media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
    source = "pexels_queries" if mode == "LOKAL" else "wan_prompt"
    total = 0
    for index, scene in enumerate(scenes, 1):
        keys = {"index", "duration_seconds", "narration", "visual_description", "media_type", source}
        if not isinstance(scene, dict) or set(scene) != keys or scene.get("index") != index:
            raise GenerationError("INVALID_RESPONSE", f"Szene {index} hat eine ungültige Struktur.")
        duration = scene["duration_seconds"]
        if type(duration) is not int or not 3 <= duration <= 12:
            raise GenerationError("INVALID_RESPONSE", f"Szene {index} hat eine ungültige Dauer.")
        total += duration
        for key, maximum in (("narration", 400), ("visual_description", 600)):
            if not isinstance(scene[key], str) or not scene[key].strip() or len(scene[key]) > maximum:
                raise GenerationError("INVALID_RESPONSE", f"Szene {index}: {key} ist ungültig.")
        if scene["media_type"] != media:
            raise GenerationError("INVALID_RESPONSE", f"Szene {index} verwendet die falsche Medienquelle.")
        value = scene[source]
        if mode == "LOKAL":
            if (not isinstance(value, list) or not 2 <= len(value) <= 4 or
                    len(set(value)) != len(value) or any(not isinstance(q, str) or not q.strip() or len(q) > 100 for q in value)):
                raise GenerationError("INVALID_RESPONSE", f"Szene {index} hat ungültige Pexels-Suchbegriffe.")
        elif not isinstance(value, str) or not value.strip() or len(value) > 1000:
            raise GenerationError("INVALID_RESPONSE", f"Szene {index} hat einen ungültigen Wan-Prompt.")
    target = data["target_duration_seconds"]
    if type(target) is not int or not 30 <= target <= 60 or total != target:
        raise GenerationError("INVALID_RESPONSE", "Szenendauer und Zieldauer stimmen nicht überein.")
    return data


def invoke_antigravity(prompt: str, timeout: int = 180) -> str:
    settings_path = Path(os.getenv("ANTIGRAVITY_SETTINGS_PATH", Path.home() / ".gemini/antigravity-cli/settings.json"))
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError("AUTH_REQUIRED", "Antigravity ist auf diesem Worker nicht angemeldet oder konfiguriert.") from exc
    if settings.get("useG1Credits") is not False:
        raise GenerationError("COST_GUARD", "Die automatische Credit-Überziehung ist nicht nachweislich deaktiviert.")
    env = os.environ.copy()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
        env.pop(name, None)
    try:
        with tempfile.TemporaryDirectory(prefix="video-script-") as scratch:
            result = subprocess.run(
                [os.getenv("ANTIGRAVITY_CLI", "agy"), "-p", prompt, "--model", "gemini-3.1-pro-low",
                 "--output-format", "json", "--print-timeout", f"{timeout}s", "--sandbox"],
                cwd=scratch, env=env, capture_output=True, text=True, timeout=timeout + 30, check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GenerationError("CLI_UNAVAILABLE", "Antigravity konnte nicht gestartet oder rechtzeitig beendet werden.") from exc
    if result.returncode != 0:
        error = result.stderr.lower()
        code = "QUOTA_EXHAUSTED" if "quota" in error or "limit" in error else "CLI_FAILED"
        message = ("Das Gemini-Pro-Kontingent ist erschöpft. Bitte später bewusst erneut versuchen."
                   if code == "QUOTA_EXHAUSTED" else "Antigravity konnte das Skript nicht erzeugen.")
        raise GenerationError(code, message)
    try:
        envelope = json.loads(result.stdout)
        if envelope.get("status") != "SUCCESS" or not isinstance(envelope.get("response"), str):
            raise ValueError
        return envelope["response"]
    except (json.JSONDecodeError, AttributeError, ValueError) as exc:
        raise GenerationError("INVALID_RESPONSE", "Antigravity lieferte keine auswertbare Antwort.") from exc


def generate_script(job_id: str) -> None:
    """RQ entry point. Failures are persisted rather than retried automatically."""
    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ["DATABASE_URL"]
    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            job = conn.execute(
                "SELECT j.id, j.project_id, p.idea, p.mode FROM script_generation_jobs j "
                "JOIN projects p ON p.id = j.project_id WHERE j.id = %s FOR UPDATE", (UUID(job_id),),
            ).fetchone()
            if not job or conn.execute("UPDATE script_generation_jobs SET state='RUNNING', updated_at=now() "
                                       "WHERE id=%s AND state='QUEUED' RETURNING id", (job_id,)).fetchone() is None:
                return
        script = validate_script(invoke_antigravity(make_prompt(job["idea"], job["mode"])), job["mode"])
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (job["project_id"],))
            version = conn.execute("SELECT coalesce(max(version),0)+1 AS next_version FROM script_versions WHERE project_id=%s",
                                   (job["project_id"],)).fetchone()["next_version"]
            narration = "\n\n".join(scene["narration"].strip() for scene in script["scenes"])
            saved = conn.execute("INSERT INTO script_versions(project_id,version,title,narration) VALUES(%s,%s,%s,%s) RETURNING id",
                                 (job["project_id"], version, script["title"].strip(), narration)).fetchone()
            for scene in script["scenes"]:
                query = " | ".join(scene["pexels_queries"]) if job["mode"] == "LOKAL" else None
                wan = scene.get("wan_prompt")
                conn.execute("INSERT INTO scenes(project_id,script_version_id,position,narration,visual_description,media_type,pexels_query,wan_prompt) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                             (job["project_id"], saved["id"], scene["index"], scene["narration"].strip(),
                              scene["visual_description"].strip(), "STOCK_VIDEO" if job["mode"] == "LOKAL" else "AI_GENERATED_VIDEO", query, wan))
            conn.execute("UPDATE script_generation_jobs SET state='COMPLETED',script_version_id=%s,updated_at=now() WHERE id=%s",
                         (saved["id"], job_id))
    except GenerationError as exc:
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE script_generation_jobs SET state='FAILED',error_code=%s,error_message=%s,updated_at=now() WHERE id=%s",
                         (exc.code, str(exc), job_id))
    except Exception:
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE script_generation_jobs SET state='FAILED',error_code='INTERNAL_ERROR',"
                         "error_message='Der Skriptauftrag ist unerwartet fehlgeschlagen. Bitte bewusst erneut versuchen.',updated_at=now() WHERE id=%s",
                         (job_id,))
