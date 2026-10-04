"""Wan transport v1: strict provenance, immutable intent and bounded raw clips."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

WORKFLOW = 'wan2.2-t2v-a14b-v1'
COMFY_COMMIT = '6b747c0428c343e1417219641db93a4fb7cb69ae'
RAW_FRAMES, RAW_FPS = 81, 16
MAX_CLIP_BYTES = 150 * 1024 * 1024


class WanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    job_id: UUID
    scene_position: int = Field(ge=1, le=20, strict=True)
    clip_index: int = Field(ge=1, le=12, strict=True)
    provider: Literal['WAN'] = 'WAN'
    media_type: Literal['AI_GENERATED_VIDEO'] = 'AI_GENERATED_VIDEO'
    workflow_version: Literal['wan2.2-t2v-a14b-v1'] = WORKFLOW
    comfy_commit: Literal['6b747c0428c343e1417219641db93a4fb7cb69ae'] = COMFY_COMMIT
    models_lock_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    prompt: str = Field(min_length=1, max_length=2000)
    seed: int = Field(ge=0, le=2**64-1, strict=True)
    width: Literal[720] = 720
    height: Literal[1280] = 1280
    frames: Literal[81] = RAW_FRAMES
    fps: Literal[16] = RAW_FPS


class WanResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    request: WanRequest
    execution: Literal['CONTROLLED_TEST', 'WAN_INFERENCE']
    result_path: str = Field(min_length=1, max_length=100)
    checksum_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    size_bytes: int = Field(gt=0, le=MAX_CLIP_BYTES, strict=True)
    duration_seconds: float = Field(gt=0, le=6)


class WanSceneSource(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    scene_position: int = Field(ge=1, le=20)
    artifact_key: str = Field(pattern=r'^scene_[0-9]+$')
    media_type: Literal['AI_GENERATED_VIDEO'] = 'AI_GENERATED_VIDEO'
    scene_duration_seconds: float = Field(gt=0, le=60)
    duration_seconds: float = Field(gt=0, le=61)
    clips: list[WanResponse] = Field(min_length=1, max_length=12)
