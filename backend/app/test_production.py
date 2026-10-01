"""Actual PostgreSQL/Redis/RQ and process-death acceptance for step 13."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue

from app.api import database
from app.main import app
from app.migrate import migrate
from app.production_dispatch import recover_productions
from app.production_jobs import run_production
from app.production_stages import StageResult
from app import test_api
from app.test_script_generation import ControlledWorker


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL'), 'PostgreSQL and Redis required')
class ProductionIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = os.environ['DATABASE_URL']
        cls.schema = 'production_test_' + uuid4().hex
        with psycopg.connect(cls.base) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        os.environ['DATABASE_URL'] = cls.base + ('&' if '?' in cls.base else '?') + 'options=-csearch_path%3D' + cls.schema
        migrate()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        os.environ['DATABASE_URL'] = cls.base
        with psycopg.connect(cls.base) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        # Recovery scans the entire schema. An earlier failed case must not
        # enqueue its unfinished run into the next case's private queue.
        with database() as conn:
            conn.execute('TRUNCATE projects CASCADE')
        self.redis = Redis.from_url(os.environ['REDIS_URL'])
        self.queue = Queue('production-test-' + uuid4().hex, connection=self.redis)
        self.queue_patch = patch('app.api.Queue', return_value=self.queue)
        self.queue_patch.start()
        self.addCleanup(self.queue_patch.stop)
        self.files = tempfile.TemporaryDirectory(prefix='step13-fixture-')
        self.addCleanup(self.files.cleanup)
        self.env_patch = patch.dict(os.environ, {'TEST_ARTIFACT_ROOT': self.files.name})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.jobs = set()
        self.addCleanup(self.cleanup_queue)

    def cleanup_queue(self):
        self.queue.empty()
        for job_id in self.jobs:
            job = self.queue.fetch_job(job_id)
            if job:
                job.delete()

    def project(self, scenario='success', mode='LOKAL', approve=True, payload=None):
        project = self.client.post('/api/projects', json={'idea': 'Controlled step 13', 'mode': mode}).json()
        body = payload or test_api.ApiContractTest.script_payload(mode)
        body['title'] = scenario
        self.assertEqual(self.client.post(f"/api/projects/{project['id']}/scripts", json=body).status_code, 201)
        if not approve:
            return project['id'], body
        approved = self.client.post(f"/api/projects/{project['id']}/scripts/1/approval")
        self.assertEqual(approved.status_code, 201, approved.text)
        run = approved.json()['production_run_id']
        self.jobs.add(run)
        return project['id'], run

    def output(self, project, run):
        response = self.client.get(f'/api/projects/{project}/production-runs/{run}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def work(self):
        with patch('app.production_jobs.stage_command', return_value=[sys.executable, '-m', 'app.test_production_fixture', 'stage']):
            ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def recover_due(self, run):
        with database() as conn:
            conn.execute('UPDATE production_runs SET available_at = now() WHERE id = %s', (run,))
        recover_productions(self.queue)
        self.jobs.update(self.queue.job_ids)

    def test_both_modes_complete_and_duplicate_delivery_has_no_effect(self):
        for mode in ('LOKAL', 'CLOUD'):
            project, run = self.project(mode=mode)
            with ThreadPoolExecutor(2) as pool, patch('app.production_jobs.stage_command', return_value=[sys.executable, '-m', 'app.test_production_fixture', 'stage']):
                list(pool.map(run_production, [run, run]))
            output = self.output(project, run)
            self.assertEqual(output['state'], 'COMPLETED')
            self.assertEqual([s['name'] for s in output['steps']], ['SCENES', 'SPEECH', 'GRAPHICS', 'ENCODING', 'STORAGE'])
            self.assertEqual([s['attempts'] for s in output['steps']], [1]*5)
            self.work()  # previously queued duplicate
            with database() as conn:
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s', (run,)).fetchone()['n'], 5)
            self.assertEqual(len(list(Path(self.files.name).rglob('*.fixture'))), 5 if mode == 'LOKAL' else 10)

    def test_retry_keeps_completed_step_and_stops_after_three_attempts(self):
        for scenario in ('transient', 'persistent'):
            project, run = self.project(scenario)
            self.work()
            first = self.output(project, run)
            self.assertEqual(first['state'], 'QUEUED')
            self.assertEqual(first['steps'][0]['attempts'], 1)
            self.assertGreater(datetime.fromisoformat(first['available_at']), datetime.now(timezone.utc))
            self.recover_due(run); self.work()
            if scenario == 'persistent':
                second = self.output(project, run)
                self.assertGreater((datetime.fromisoformat(second['available_at'])-datetime.now(timezone.utc)).total_seconds(), 20)
                self.recover_due(run); self.work()
                final = self.output(project, run)
                self.assertEqual(final['state'], 'FAILED')
                self.assertFalse(final['can_resume'])
                self.assertEqual(final['steps'][1]['attempts'], 3)
                self.assertEqual(self.client.post(f'/api/projects/{project}/production-runs/{run}/resume').status_code, 409)
            else:
                self.assertEqual(self.output(project, run)['state'], 'COMPLETED')
            self.assertEqual(self.output(project, run)['steps'][0]['attempts'], 1)

    def test_timeout_is_recorded_and_resume_keeps_artifacts(self):
        project, run = self.project('timeout')
        with database() as conn:
            conn.execute("UPDATE production_steps SET timeout_seconds = 4 WHERE production_run_id = %s AND name = 'SPEECH'", (run,))
        self.work()
        output = self.output(project, run)
        self.assertEqual(output['steps'][1]['error_code'], 'STEP_TIMEOUT')
        self.recover_due(run); self.work()
        self.assertEqual(self.output(project, run)['state'], 'COMPLETED')
        self.assertEqual(len(list(Path(self.files.name).rglob('*.fixture'))), 5)

    def test_outbox_lost_response_resume_and_cancel_are_idempotent(self):
        project, body = self.project(approve=False)
        with patch.object(self.queue, 'enqueue', side_effect=RedisConnectionError('controlled')):
            self.assertEqual(self.client.post(f'/api/projects/{project}/scripts/1/approval').status_code, 503)
        status = self.client.get(f'/api/projects/{project}/status').json()
        run = status['production_run_id']; self.jobs.add(run)
        recover_productions(self.queue); recover_productions(self.queue)
        self.assertEqual(self.queue.count, 1)
        url = f'/api/projects/{project}/production-runs/{run}'
        self.assertEqual(self.client.post(url+'/cancel').json()['error_code'], 'CANCELLED')
        self.assertEqual(self.client.post(url+'/cancel').status_code, 200)
        self.assertEqual(self.client.post(url+'/resume').status_code, 409)
        self.work()
        self.assertEqual(self.output(project, run)['state'], 'FAILED')
        self.assertEqual(list(Path(self.files.name).rglob('*.fixture')), [])
        # Explicit resume preserves the run, completed steps and bounded budget.
        project, run = self.project()
        with database() as conn:
            conn.execute("UPDATE production_runs SET state = 'FAILED', error_code = 'TEST' WHERE id = %s", (run,))
        url = f'/api/projects/{project}/production-runs/{run}'
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: self.client.post(url+'/resume'), range(2)))
        self.assertTrue(all(r.status_code == 200 for r in responses))
        self.jobs.update(self.queue.job_ids)
        self.work()
        self.assertEqual(self.output(project, run)['state'], 'COMPLETED')

    def test_old_version_deadline_mixed_source_and_unknown_run_are_blocked(self):
        project, run = self.project()
        body = test_api.ApiContractTest.script_payload(expected_version=1)
        self.assertEqual(self.client.post(f'/api/projects/{project}/scripts', json=body).status_code, 201)
        self.work()
        self.assertEqual(self.output(project, run)['error_code'], 'VERSION_SUPERSEDED')
        self.assertFalse(self.output(project, run)['can_resume'])
        project, run = self.project()
        with database() as conn:
            conn.execute("UPDATE production_runs SET deadline_at = now() - interval '1 second' WHERE id = %s", (run,))
        self.work()
        self.assertEqual(self.output(project, run)['error_code'], 'RUN_TIMEOUT')
        project, run = self.project('mixed')
        self.work()
        self.assertEqual(self.output(project, run)['state'], 'FAILED')
        self.assertEqual(self.output(project, run)['error_code'], 'MODE_MISMATCH')
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s', (run,)).fetchone()['n'], 0)
        self.assertEqual(self.client.get(f'/api/projects/{project}/production-runs/{uuid4()}').status_code, 404)
        self.assertEqual(self.client.get(f'/api/projects/{uuid4()}/production-runs/{run}').status_code, 404)

    def test_cancel_running_stage_terminates_child_and_preserves_checkpoint(self):
        project, run = self.project('interrupt')
        command = [sys.executable, '-m', 'app.test_production_fixture', 'worker', self.queue.name, 'burst']
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        worker = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.output(project, run)['steps'][1]['state'] == 'RUNNING':
                    break
                time.sleep(.1)
            else:
                self.fail('Worker did not reach the cancellable stage')
            response = self.client.post(f'/api/projects/{project}/production-runs/{run}/cancel')
            self.assertEqual(response.status_code, 200, response.text)
            worker.wait(timeout=15)
            final = self.output(project, run)
            self.assertEqual(final['state'], 'FAILED')
            self.assertEqual(final['error_code'], 'CANCELLED')
            self.assertEqual([s['state'] for s in final['steps'][:2]], ['COMPLETED', 'FAILED'])
            self.assertFalse(final['can_resume'])
            self.assertEqual(len(list(Path(self.files.name).rglob('*.fixture'))), 1)
        finally:
            if worker.poll() is None:
                worker.kill(); worker.wait(timeout=10)

    def test_killed_worker_restart_continues_without_duplicate_artifacts(self):
        project, run = self.project('interrupt')
        with database() as conn:
            conn.execute("UPDATE production_steps SET timeout_seconds = 8 WHERE production_run_id = %s AND name = 'SPEECH'", (run,))
        command = [sys.executable, '-m', 'app.test_production_fixture', 'worker', self.queue.name]
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        worker = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.output(project, run)['steps'][1]['state'] == 'RUNNING':
                    break
                time.sleep(.1)
            else:
                self.fail('Worker did not reach speech checkpoint')
            worker.kill(); worker.wait(timeout=10)  # actual parent death, not a mocked exception
            self.assertEqual(self.output(project, run)['steps'][0]['state'], 'COMPLETED')
            restarted = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
            try:
                restarted.wait(timeout=100)
                self.assertEqual(restarted.returncode, 0)
            finally:
                if restarted.poll() is None:
                    restarted.kill(); restarted.wait(timeout=10)
            final = self.output(project, run)
            self.assertEqual(final['state'], 'COMPLETED', json.dumps(final))
            self.assertEqual([s['attempts'] for s in final['steps']], [1,2,1,1,1])
            with database() as conn:
                history = conn.execute('SELECT state, error_code FROM production_attempts WHERE step_id = %s ORDER BY number',
                                       (final['steps'][1]['id'],)).fetchall()
                self.assertEqual([(x['state'], x['error_code']) for x in history], [('FAILED','WORKER_INTERRUPTED'), ('COMPLETED',None)])
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s', (run,)).fetchone()['n'], 5)
            self.assertEqual(len(list(Path(self.files.name).rglob('*.fixture'))), 5)
            self.assertFalse(list(Path(self.files.name).rglob('*.partial')))
        finally:
            if worker.poll() is None:
                worker.kill(); worker.wait(timeout=10)
            with database() as conn:
                self.jobs.update(str(r['id']) + (f"-{r['dispatch_number']}" if r['dispatch_number'] else '')
                                 for r in conn.execute('SELECT id, dispatch_number FROM production_runs WHERE id = %s', (run,)))


class StageContractTest(unittest.TestCase):
    def test_paths_and_extra_fields_are_rejected(self):
        for value in ('../secret', '/secret', 'C:/secret', 'x\\y'):
            with self.assertRaises(ValueError):
                StageResult.model_validate({'artifacts': [dict(key='x', kind='SOURCE', media_type='STOCK_VIDEO', storage_path=value, checksum_sha256='a'*64)]})
        with self.assertRaises(ValueError):
            StageResult.model_validate({'artifacts': [], 'token': 'must-not-be-accepted'})
