"""Cost planning stays offline, including negative admission cases."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.cloud_costs import ComputeRates, estimate_cost, check_planned_budget
from app.cloud_limits import CloudLimits, CostEvidence
from app.production_stages import StageFailure
from app.test_wan import context
from app.wan import plan_requests


class CloudCostsTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
        self.rates = ComputeRates(checked_on=date(2026, 10, 9))
        self.limits = CloudLimits(max_cost_usd=Decimal('10'))
        self.planned = plan_requests(context(6))
        self.evidence = CostEvidence(workspace='fixture', checked_at=self.now,
            credits_remaining_usd=Decimal('30'), workspace_budget_remaining_usd=Decimal('30'),
            net_spend_limit_usd=Decimal('0'), net_spend_limit_enforced=True,
            max_containers=1, function_timeout_seconds=1800, source_reference='test-only')

    def estimate(self, **kwargs):
        return estimate_cost(self.planned, self.limits, rates=self.rates,
                             extra_cost_usd=Decimal('0.50'), now=self.now, **kwargs)

    def test_every_clip_includes_startup_execution_tail_and_uncertainty(self):
        result = self.estimate()
        self.assertEqual(result.clip_count, 12)
        self.assertEqual(result.container_seconds, 12*(300+1800+2+30))
        self.assertEqual(result.compute_usd, Decimal('22.73087232'))
        self.assertEqual(result.total_usd, Decimal('23.230873'))  # rounded up
        # A local one-second deadline cannot cancel or bound remote billing.
        short = CloudLimits(max_run_seconds=1, max_cost_usd=Decimal('10'))
        self.assertEqual(estimate_cost(self.planned, short, rates=self.rates,
            extra_cost_usd=Decimal('0.50'), now=self.now).total_usd, result.total_usd)

    def test_unknown_extra_costs_and_invalid_or_stale_rates_block(self):
        for extra in (None, '-1', 'NaN', 'Infinity'):
            with self.subTest(extra=extra), self.assertRaises(StageFailure):
                estimate_cost(self.planned, self.limits, rates=self.rates,
                              extra_cost_usd=extra, now=self.now)
        for checked in (self.now.date()-timedelta(days=2), self.now.date()+timedelta(days=1)):
            with self.subTest(checked=checked), self.assertRaises(StageFailure):
                estimate_cost(self.planned, self.limits,
                    rates=self.rates.model_copy(update={'checked_on': checked}),
                    extra_cost_usd=Decimal('0'), now=self.now)

    def test_product_ten_dollar_limit_cannot_be_bypassed_by_worker_configuration(self):
        with self.assertRaises(StageFailure) as caught:
            check_planned_budget(self.planned, CloudLimits(max_cost_usd=Decimal('100')),
                self.evidence, workspace='fixture', rates=self.rates,
                extra_cost_usd=Decimal('0'), now=self.now)
        self.assertEqual(caught.exception.code, 'WAN_VIDEO_COST_LIMIT')

    def test_affordable_plan_still_requires_fresh_account_evidence(self):
        planned = plan_requests(context())
        result = check_planned_budget(planned, self.limits, self.evidence,
            workspace='fixture', rates=self.rates, extra_cost_usd=Decimal('0.50'), now=self.now)
        self.assertLess(result.total_usd, Decimal('10'))
        with self.assertRaises(StageFailure) as caught:
            check_planned_budget(planned, self.limits, None, workspace='fixture',
                rates=self.rates, extra_cost_usd=Decimal('0.50'), now=self.now)
        self.assertEqual(caught.exception.code, 'WAN_COST_UNVERIFIED')


if __name__ == '__main__': unittest.main()
