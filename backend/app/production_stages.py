"""Isolated media-stage boundary. Actual adapters arrive in tasks 14-18/21."""

import json
import os
from pathlib import PurePosixPath
import signal
import subprocess
import sys
import threading

from pydantic import BaseModel, ConfigDict, Field, field_validator


STAGES = (("SCENES", 3600), ("SPEECH", 300), ("GRAPHICS", 900),
          ("ENCODING", 1800), ("STORAGE", 120))
RUN_TIMEOUT = 10800


class StageFailure(Exception):
    def __init__(self, code, message, retryable=False):
        super().__init__(message)
        self.code, self.retryable = code, retryable


class StageArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    kind: str = Field(pattern=r"^(SOURCE|INTERMEDIATE|FINAL)$")
    media_type: str = Field(pattern=r"^(STOCK_VIDEO|AI_GENERATED_VIDEO|FINAL_VIDEO)$")
    storage_path: str = Field(min_length=1, max_length=1000)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("storage_path")
    @classmethod
    def relative_path(cls, value):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value or str(path) == ".":
            raise ValueError("artifact path must be relative to the configured media root")
        return value


class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifacts: list[StageArtifact] = Field(max_length=100)


def execute_stage(name, context):
    # No fixture switch, external calls, source fallback or simulated media in production.
    labels = {"SCENES": "Szenenbeschaffung", "SPEECH": "Sprachsynthese", "GRAPHICS": "Grafikerstellung",
              "ENCODING": "Video-Encoding", "STORAGE": "Medienablage"}
    raise StageFailure("STAGE_UNAVAILABLE", f"{labels[name]} ist noch nicht verfügbar. Deine Skriptfreigabe bleibt gespeichert.")


def kill_process_tree(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def main():
    from app.api import database
    payload = json.loads(sys.stdin.readline())
    context = payload["context"]
    # An orphaned child is bounded even if its RQ parent is killed.
    watchdog = threading.Timer(payload["timeout_seconds"], kill_process_tree, (os.getpid(),))
    watchdog.daemon = True
    watchdog.start()
    try:
        with database() as conn:
            conn.autocommit = True
            conn.execute("SELECT pg_advisory_lock(hashtextextended(%s, 13))", (context["step_id"],))
            row = conn.execute("SELECT state, attempts FROM production_steps WHERE id = %s",
                               (context["step_id"],)).fetchone()
            if not row or row["state"] != "RUNNING" or row["attempts"] != context["attempt"]:
                raise StageFailure("WORKER_INTERRUPTED", "Der Produktionsschritt wurde unterbrochen.", True)
            result = execute_stage(payload["name"], context)
            print(StageResult.model_validate(result).model_dump_json(), flush=True)
    except StageFailure as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc), "retryable": exc.retryable}}), flush=True)
    except Exception:
        print(json.dumps({"error": {"code": "STAGE_ERROR", "message": "Der Produktionsschritt ist fehlgeschlagen.",
                                   "retryable": False}}), flush=True)
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
