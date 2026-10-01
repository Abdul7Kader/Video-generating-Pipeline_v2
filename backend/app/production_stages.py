"""Isolated media-stage boundary with Pexels/Piper; remaining adapters in 16-18/21."""

import json
import os
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import urlparse
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
    media_type: str = Field(pattern=r"^(STOCK_VIDEO|AI_GENERATED_VIDEO|FINAL_VIDEO|SPEECH_AUDIO)$")
    storage_path: str = Field(min_length=1, max_length=1000)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("storage_path")
    @classmethod
    def relative_path(cls, value):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value or str(path) == ".":
            raise ValueError("artifact path must be relative to the configured media root")
        return value


class PexelsSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_position: int = Field(ge=1, le=20)
    artifact_key: str = Field(pattern=r"^scene_[0-9]+$")
    media_type: Literal["STOCK_VIDEO"] = "STOCK_VIDEO"
    video_id: int = Field(gt=0)
    file_id: int = Field(gt=0)
    query: str = Field(min_length=1, max_length=1000)
    video_page: str
    creator: str = Field(min_length=1, max_length=300)
    creator_page: str
    license_url: Literal["https://www.pexels.com/license/"] = "https://www.pexels.com/license/"
    scene_duration_seconds: float = Field(gt=0, le=60)
    duration_seconds: float = Field(gt=0, le=86400)
    width: int = Field(ge=720)
    height: int = Field(ge=1280)
    fps: float = Field(gt=0, le=240)

    @field_validator("video_page", "creator_page")
    @classmethod
    def pexels_page(cls, value):
        url = urlparse(value)
        if url.scheme != "https" or url.hostname not in ("pexels.com", "www.pexels.com") or url.port not in (None, 443) or url.username or url.password:
            raise ValueError("Pexels HTTPS page required")
        return value


class SpeechSegment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scene_position: int = Field(ge=1, le=20)
    artifact_key: str = Field(pattern=r'^speech_[0-9]+$')
    media_type: Literal['SPEECH_AUDIO'] = 'SPEECH_AUDIO'
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9_-]+$')
    model_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    config_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    engine_version: str = Field(min_length=1, max_length=50)
    length_scale: float = Field(gt=0, le=2)
    duration_seconds: float = Field(gt=0, le=120)
    frames: int = Field(gt=0)
    sample_rate: int = Field(ge=8000, le=48000)
    channels: Literal[1] = 1


class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifacts: list[StageArtifact] = Field(max_length=100)
    sources: list[PexelsSource] = Field(default_factory=list, max_length=20)
    speech: list[SpeechSegment] = Field(default_factory=list, max_length=20)


def execute_stage(name, context):
    if name == "SCENES" and context["mode"] == "LOKAL":
        from app.pexels import collect_scenes
        return collect_scenes(context)
    if name == 'SPEECH':
        from app.speech import synthesize_scenes
        return synthesize_scenes(context)
    # No source fallback or simulated media in production.
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
    # Parent and child must agree even on Windows with a legacy code page.
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    from app.database import database
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
    # Keep adapter exceptions identical when invoked directly via python -m.
    from app.production_stages import main as canonical_main
    canonical_main()
