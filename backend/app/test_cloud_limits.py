"""Cloud admission functions only; never contact Modal or allocate a GPU."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.production_stages import StageFailure
from app.test_wan import context
from app.test_wan_fixture import FixtureProvider
from app.wan import collect_scenes, plan_requests
from app.cloud_limits import CloudLimits, CostEvidence, check_live_budget, load_limits, cloud_slot


class CloudLimitsTest(unittest.TestCase):
    def test_cloud_subprocess_uses_configured_deadline_and_local_mode_is_unchanged(self):
        from app.production_jobs import run_stage
        from app.test_encoding import encoding_context
        for mode, expected in [('CLOUD', 2), ('LOKAL', 30)]:
            body = encoding_context(mode)
            body['run_id'] = 'controlled-fixture'
            process = Mock()
            process.returncode = 0
            process.communicate.return_value = (json.dumps({'artifacts': []}), '')
            with patch.dict(os.environ, {'WAN_MAX_RUN_SECONDS': '2', 'WORKER_CONFIG_PATH': ''}), \
                 patch('app.production_jobs.subprocess.Popen', return_value=process), \
                 patch('app.production_jobs.check_run'), \
                 patch('app.production_jobs.StageResult.model_validate', side_effect=ValueError('test stop')):
                with self.assertRaises(StageFailure):
                    run_stage(None, {'name': 'SCENES'}, body, 30)
            payload = json.loads(process.stdin.write.call_args.args[0])
            self.assertEqual(payload['timeout_seconds'], expected)

    def test_invalid_configuration_fails_closed_and_private_config_is_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'worker.json'
            config.write_text(json.dumps({'WAN_LIMITS': {'max_clips': 4}}), encoding='utf-8')
            with patch.dict(os.environ, {'WORKER_CONFIG_PATH': str(config)}, clear=True):
                self.assertEqual(load_limits().max_clips, 4)
                for value in ('0', '-1', 'nan', '1.5', ''):
                    with self.subTest(value=value), patch.dict(os.environ, {'WAN_MAX_CLIPS': value}):
                        with self.assertRaises(StageFailure) as caught: load_limits()
                        self.assertEqual(caught.exception.code, 'WAN_LIMITS_INVALID')
                for name, value in [('WAN_MAX_RUN_SECONDS', '3601'), ('WAN_MAX_CLIP_SECONDS', '1801'),
                                    ('WAN_MAX_PARALLEL', '0'), ('WAN_MAX_COST_USD', 'NaN'),
                                    ('WAN_MAX_COST_USD', '-0.01')]:
                    with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}):
                        with self.assertRaises(StageFailure): load_limits()
            config.write_text('{broken', encoding='utf-8')
            with patch.dict(os.environ, {'WORKER_CONFIG_PATH': str(config)}, clear=True):
                with self.assertRaises(StageFailure): load_limits()

    def test_clip_limit_rejects_before_provider_or_media_work(self):
        provider = FixtureProvider('/never-read')
        with patch.dict(os.environ, {'WAN_MAX_CLIPS': '1', 'WORKER_CONFIG_PATH': ''}), \
             patch('app.wan.media_root') as storage:
            with self.assertRaises(StageFailure) as caught: collect_scenes(context(), provider)
        self.assertEqual(caught.exception.code, 'WAN_CLIP_LIMIT')
        self.assertFalse(provider.calls)
        storage.assert_not_called()

    def test_parallel_slots_are_shared_across_processes_and_released_after_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = ('from pathlib import Path; from app.cloud_limits import cloud_slot; '
                    'from app.production_stages import StageFailure; import sys\n'
                    'try:\n with cloud_slot(Path(sys.argv[1]), 1): pass\n'
                    'except StageFailure as exc:\n print(exc.code); sys.exit(7)\n')
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                with cloud_slot(root, 1):
                    result = subprocess.run([sys.executable, '-c', code, str(root)],
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 7, result.stderr)
                    self.assertEqual(result.stdout.strip(), 'WAN_PARALLEL_LIMIT')
                    with cloud_slot(root, 2): pass  # second configured slot
                    raise RuntimeError('fixture failure')
            with cloud_slot(root, 1): pass


class LiveBudgetTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.limits = CloudLimits(max_cost_usd=Decimal('5'))
        self.plan = plan_requests(context())
        self.evidence = CostEvidence(workspace='fixture-workspace', checked_at=self.now,
            credits_remaining_usd=Decimal('10'), workspace_budget_remaining_usd=Decimal('8'),
            net_spend_limit_usd=Decimal('0'), net_spend_limit_enforced=True,
            max_containers=1, function_timeout_seconds=1800,
            source_reference='controlled-test-only')

    def check(self, evidence=None, **kwargs):
        return check_live_budget(self.plan, self.limits, evidence or self.evidence,
            workspace='fixture-workspace', estimated_total_usd=Decimal('2'), now=self.now, **kwargs)

    def test_valid_snapshot_passes_pure_preflight_but_does_not_enable_live_provider(self):
        self.check()
        provider = FixtureProvider('/never-read'); provider.execution = 'WAN_INFERENCE'
        with self.assertRaises(StageFailure) as caught: collect_scenes(context(), provider)
        self.assertEqual(caught.exception.code, 'WAN_LIVE_DISABLED')
        self.assertFalse(provider.calls)

    def test_zero_default_missing_stale_future_or_wrong_workspace_block_admission(self):
        with self.assertRaises(StageFailure):
            check_live_budget(self.plan, CloudLimits(), self.evidence,
                workspace='fixture-workspace', estimated_total_usd=Decimal('2'), now=self.now)
        with self.assertRaises(StageFailure):
            check_live_budget(self.plan, self.limits, None,
                workspace='fixture-workspace', estimated_total_usd=Decimal('2'), now=self.now)
        for updates in ({'checked_at': self.now-timedelta(minutes=6)},
                        {'checked_at': self.now+timedelta(seconds=1)}, {'workspace': 'other'}):
            with self.subTest(updates=updates), self.assertRaises(StageFailure):
                self.check(self.evidence.model_copy(update=updates))

    def test_cost_credit_budget_spend_and_deployment_bounds_are_independent(self):
        for updates in ({'credits_remaining_usd': Decimal('1')},
                        {'workspace_budget_remaining_usd': Decimal('1')},
                        {'net_spend_limit_usd': Decimal('1')}, {'net_spend_limit_enforced': False},
                        {'max_containers': 2}, {'function_timeout_seconds': 1801}):
            with self.subTest(updates=updates), self.assertRaises(StageFailure):
                self.check(self.evidence.model_copy(update=updates))
        for estimate in ('0', '-1', 'NaN', 'Infinity', '5.01'):
            with self.subTest(estimate=estimate), self.assertRaises(StageFailure):
                check_live_budget(self.plan, self.limits, self.evidence,
                    workspace='fixture-workspace', estimated_total_usd=Decimal(estimate), now=self.now)
        check_live_budget(self.plan, self.limits, self.evidence, workspace='fixture-workspace',
                          estimated_total_usd=Decimal('5'), now=self.now)


if __name__ == '__main__': unittest.main()
