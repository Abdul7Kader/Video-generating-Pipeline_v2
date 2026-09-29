"""Account-backed Antigravity invocation; never use a Gemini API key."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

from app.script_contract import make_prompt, output_schema, validate_script


class GenerationFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _safe_settings() -> None:
    path = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GenerationFailure(
            "CREDIT_GUARD_UNVERIFIED",
            "Die Antigravity-Kostensperre ist nicht bestätigt. Auf diesem Rechner muss useG1Credits ausdrücklich false sein.",
        ) from exc
    if not isinstance(settings, dict) or settings.get("useG1Credits") is not False:
        raise GenerationFailure(
            "CREDIT_GUARD_UNVERIFIED",
            "Antigravity darf keine zusätzlichen AI-Credits verwenden. useG1Credits muss false sein.",
        )
    if settings.get("modelProvider") is not None:
        raise GenerationFailure(
            "API_PROVIDER_FORBIDDEN",
            "Der Worker muss mit dem Google-AI-Pro-Konto angemeldet sein; ein API-Provider ist gesperrt.",
        )


def _failure_from_output(output: str) -> GenerationFailure:
    lower = output.lower()
    if any(word in lower for word in ("authentication required", "not authenticated", "sign in", "login required")):
        return GenerationFailure("AUTH_REQUIRED", "Antigravity ist auf diesem Rechner nicht angemeldet.")
    if any(word in lower for word in ("quota", "rate limit", "resource exhausted", "credits exhausted")):
        return GenerationFailure("QUOTA_EXHAUSTED", "Das Pro-Kontingent ist erschöpft. Bitte später bewusst erneut versuchen.")
    return GenerationFailure("AGY_FAILED", "Antigravity konnte das Skript nicht erstellen. Bitte später erneut versuchen.")


def generate(idea: str, mode: str) -> dict:
    _safe_settings()
    env = os.environ.copy()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GEMINI_BASE_URL"):
        env.pop(name, None)
    try:
        with tempfile.TemporaryDirectory(prefix="video-script-") as scratch:
            result = subprocess.run(
                ["agy", "-p", make_prompt(idea, mode), "--model", "gemini-3.1-pro-high",
                 "--output-format", "json", "--json-schema", json.dumps(output_schema(mode)),
                 "--print-timeout", "180s", "--sandbox"],
                cwd=scratch, env=env, capture_output=True, text=True,
                encoding="utf-8", timeout=210, check=False,
            )
    except FileNotFoundError as exc:
        raise GenerationFailure("AGY_UNAVAILABLE", "Antigravity CLI ist auf diesem Rechner nicht installiert.") from exc
    except OSError as exc:
        raise GenerationFailure("AGY_UNAVAILABLE", "Antigravity CLI konnte auf diesem Rechner nicht gestartet werden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GenerationFailure("AGY_TIMEOUT", "Antigravity hat nicht rechtzeitig geantwortet. Bitte erneut versuchen.") from exc
    if result.returncode != 0:
        raise _failure_from_output(result.stderr + "\n" + result.stdout)
    try:
        envelope = json.loads(result.stdout)
        if not isinstance(envelope, dict) or envelope.get("status") != "SUCCESS":
            raise _failure_from_output(result.stdout)
        response = envelope.get("response")
        if not isinstance(response, str):
            raise ValueError("Missing response")
        return validate_script(response, mode)
    except (ValueError, KeyError, TypeError) as exc:
        raise GenerationFailure(
            "INVALID_SCRIPT", "Antigravity lieferte kein vollständiges gültiges Skript. Bitte erneut versuchen.",
        ) from exc
