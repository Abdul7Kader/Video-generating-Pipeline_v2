"""Local CLOUD limits and offline live-admission contract. No Modal SDK here."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import errno
import json
import os
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from app.production_stages import StageFailure


class CloudLimits(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    max_clips: int = Field(default=20, ge=1, le=100, strict=True)
    max_run_seconds: int = Field(default=3600, ge=1, le=3600, strict=True)
    max_clip_seconds: int = Field(default=1800, ge=1, le=1800, strict=True)
    max_parallel: int = Field(default=1, ge=1, le=8, strict=True)
    max_cost_usd: Decimal = Field(default=Decimal('0'), ge=0, le=100)


def load_limits():
    """Private worker WAN_LIMITS, then explicit environment overrides; no UI input."""
    try:
        values = {}
        if filename := os.environ.get('WORKER_CONFIG_PATH'):
            config = json.loads(Path(filename).read_text(encoding='utf-8'))
            values = config.get('WAN_LIMITS', {})
            if not isinstance(values, dict): raise ValueError('WAN_LIMITS must be an object')
            values = dict(values)
        for field in CloudLimits.model_fields:
            name = 'WAN_'+field.upper()
            if name in os.environ:
                value = os.environ[name]
                values[field] = Decimal(value) if field == 'max_cost_usd' else int(value)
        return CloudLimits.model_validate(values)
    except (OSError, ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        raise StageFailure('WAN_LIMITS_INVALID', 'Cloud-Grenzen sind ungültig. Private Worker-Konfiguration prüfen.') from exc


def check_clip_count(planned, limits):
    count = sum(len(clips) for _, _, clips in planned)
    if not 0 < count <= limits.max_clips:
        raise StageFailure('WAN_CLIP_LIMIT', f'Cloud-Auftrag benötigt {count} Clips; erlaubt sind höchstens {limits.max_clips}.')


class CostEvidence(BaseModel):
    """Snapshot supplied by a trusted future account adapter, never by script/UI."""
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    workspace: str = Field(min_length=1, max_length=200)
    checked_at: AwareDatetime
    credits_remaining_usd: Decimal = Field(ge=0)
    workspace_budget_remaining_usd: Decimal = Field(ge=0)
    net_spend_limit_usd: Decimal = Field(ge=0)
    net_spend_limit_enforced: bool = Field(strict=True)
    max_containers: int = Field(ge=1, strict=True)
    function_timeout_seconds: int = Field(ge=1, strict=True)
    source_reference: str = Field(min_length=1, max_length=500)


def check_live_budget(planned, limits, evidence, *, workspace, estimated_total_usd, now=None):
    """Pure preflight; passing does NOT enable a provider or verify an account.

    Estimate must cover compute, startup, builds, storage and transfer. The live
    adapter in step 24 must obtain fresh evidence and reserve spend atomically.
    """
    check_clip_count(planned, limits)
    try:
        limits = CloudLimits.model_validate(limits.model_dump())
        evidence = CostEvidence.model_validate(evidence.model_dump() if isinstance(evidence, CostEvidence) else evidence)
        now = now or datetime.now(timezone.utc)
        age = (now-evidence.checked_at).total_seconds()
        estimate = Decimal(str(estimated_total_usd))
        if (not estimate.is_finite() or estimate <= 0 or not 0 <= age <= 300
                or evidence.workspace != workspace or not evidence.net_spend_limit_enforced
                or evidence.net_spend_limit_usd != 0):
            raise ValueError('unverified evidence')
        if (evidence.max_containers > limits.max_parallel
                or evidence.function_timeout_seconds > min(limits.max_clip_seconds, limits.max_run_seconds)):
            raise ValueError('deployment exceeds limits')
        if estimate > min(limits.max_cost_usd, evidence.credits_remaining_usd,
                          evidence.workspace_budget_remaining_usd):
            raise ValueError('insufficient budget')
    except (ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        raise StageFailure('WAN_COST_UNVERIFIED', 'Cloud-Auftrag gesperrt: aktuelle Credits, Budget, 0-USD-Nettokostenlimit und Auftragskosten müssen nachgewiesen sein.') from exc


@contextmanager
def cloud_slot(root, maximum):
    """Nonblocking OS locks shared by host processes using the same media root.

    Keep lock files: unlinking a locked inode would allow another process in.
    OS releases the lock when the process exits, including after a crash.
    Remote/global workspace concurrency must additionally be bounded in step 24.
    """
    from app.media import safe_path
    folder = safe_path(root, '.cloud-slots')
    folder.mkdir(exist_ok=True)
    stream = None
    for index in range(maximum):
        candidate = safe_path(root, f'.cloud-slots/{index}.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                candidate.seek(0)
                msvcrt.locking(candidate.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(candidate.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            stream = candidate
            break
        except OSError as exc:
            candidate.close()
            if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise StageFailure('WAN_LOCK_UNAVAILABLE', 'Cloud-Parallelitätsgrenze konnte nicht sicher geprüft werden.') from exc
    if stream is None:
        raise StageFailure('WAN_PARALLEL_LIMIT', 'Cloud-Parallelitätsgrenze erreicht. Nach Ende des laufenden Auftrags erneut versuchen.', True)
    try:
        yield
    finally:
        stream.close()
