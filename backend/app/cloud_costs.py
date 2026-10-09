"""Offline planning allowance, never an account verification or billing guarantee.

Rates checked against https://modal.com/pricing on 2026-10-09. No SDK,
credentials, network, deployments or runtime switches in this module.
"""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_UP

from pydantic import BaseModel, ConfigDict, Field
from cloud.validate import load, validate_bundle
from app.cloud_limits import check_clip_count, check_live_budget
from app.production_stages import StageFailure


class ComputeRates(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    checked_on: date = date(2026, 10, 9)
    gpu_second: Decimal = Field(default=Decimal('0.000694'), gt=0)
    core_second: Decimal = Field(default=Decimal('0.0000131'), gt=0)
    gib_second: Decimal = Field(default=Decimal('0.00000222'), gt=0)


class CostEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)
    clip_count: int
    container_seconds: int
    compute_usd: Decimal
    extra_usd: Decimal
    total_usd: Decimal


def estimate_cost(planned, limits, *, rates, extra_cost_usd, now=None):
    """Plan every remote call without treating the host deadline as cancellation.

    Assumes no remote retries/restarts, one cold start per clip, full execution
    timeout, container tail and 30 seconds timing allowance per call. Extra must
    explicitly cover image build, model provisioning, storage and transfer for
    the actual account. Even explicit zero requires separate verification by
    the live adapter. Provider preemption/restarts and soft CPU throttling mean
    this is a planning allowance, not a hard spend limit. Account limits must
    protect billing independently.
    """
    check_clip_count(planned, limits)
    try:
        rates = ComputeRates.model_validate(rates.model_dump())
        now = now or datetime.now(timezone.utc)
        age = (now.date()-rates.checked_on).days
        extra = Decimal(str(extra_cost_usd))
        if not 0 <= age <= 1 or not extra.is_finite() or extra < 0:
            raise ValueError('unknown costs or stale prices')
        validate_bundle()
        spec = load('deployment.json')
        count = sum(len(clips) for _, _, clips in planned)
        seconds = count*(spec['startup_timeout_seconds']+spec['timeout_seconds']
                         +spec['scaledown_window_seconds']+30)
        rate = (rates.gpu_second + Decimal(str(spec['cpu_limit']))*rates.core_second
                +Decimal(spec['memory_limit_mib'])/1024*rates.gib_second)
        compute = rate*seconds
        return CostEstimate(clip_count=count, container_seconds=seconds,
            compute_usd=compute, extra_usd=extra,
            total_usd=(compute+extra).quantize(Decimal('0.000001'), rounding=ROUND_UP))
    except (OSError, ValueError, TypeError, AttributeError, KeyError, ArithmeticError) as exc:
        raise StageFailure('WAN_COST_COMPONENTS_UNVERIFIED',
            'Cloud-Kostenplanung gesperrt: aktuelle Preise und Kosten für Aufbau, Modelle, Speicher und Transfer fehlen oder sind ungültig.') from exc


def check_planned_budget(planned, limits, evidence, *, workspace, rates, extra_cost_usd, now=None):
    """Pure preparation for the future live adapter; never enables inference."""
    estimate = estimate_cost(planned, limits, rates=rates, extra_cost_usd=extra_cost_usd, now=now)
    if estimate.total_usd > Decimal('10'):
        raise StageFailure('WAN_VIDEO_COST_LIMIT',
            f'Cloud-Kostenplanung {estimate.total_usd} USD überschreitet das 10-USD-Bruttolimit pro Testvideo.')
    check_live_budget(planned, limits, evidence, workspace=workspace,
                      estimated_total_usd=estimate.total_usd, now=now)
    return estimate
