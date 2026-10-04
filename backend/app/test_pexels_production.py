"""Actual PostgreSQL, Redis/RQ and isolated production-stage processes.

HTTP is controlled during prefetch; the real child verifies persisted MP4s/cache.
"""

import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue

from app.api import database
from app.main import app
from app.migrate import migrate
from app.pexels import collect_scenes
from app.production_stages import StageFailure
from app import test_pexels
from app.test_script_generation import sample_script, ControlledWorker


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and shutil.which('ffmpeg') and shutil.which('ffprobe'),
                     'PostgreSQL, Redis, FFmpeg and ffprobe required')
class PexelsProductionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_pexels.PexelsTest.setUpClass.__func__(cls)
        cls.base = os.environ['DATABASE_URL']
        cls.schema = 'pexels_test_' + uuid4().hex
        with psycopg.connect(cls.base) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        os.environ['DATABASE_URL'] = cls.base + ('&' if '?' in cls.base else '?') + 'options=-csearch_path%3D' + cls.schema
        migrate()
        cls.api = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.api.close()
        os.environ['DATABASE_URL'] = cls.base
        with psycopg.connect(cls.base) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))
        test_pexels.PexelsTest.tearDownClass.__func__(cls)

    http = test_pexels.PexelsTest.http

    def setUp(self):
        test_pexels.PexelsTest.setUp(self)
        # This suite isolates stock sourcing from an installed speech model.
        model = patch.dict(os.environ, {'PIPER_MODEL_PATH': str(self.root / 'missing.onnx')})
        model.start()
        self.addCleanup(model.stop)
        self.redis = Redis.from_url(os.environ['REDIS_URL'])
        self.queue = Queue('pexels-test-' + uuid4().hex, connection=self.redis)
        override = patch('app.api.Queue', return_value=self.queue)
        override.start()
        self.addCleanup(override.stop)
        self.jobs = []
        self.addCleanup(self.cleanup_queue)

    def cleanup_queue(self):
        self.queue.empty()
        for identity in self.jobs:
            job = self.queue.fetch_job(identity)
            if job:
                job.delete()

    def project(self, mode='LOKAL'):
        project = self.api.post('/api/projects', json={'idea': 'Controlled Pexels production acceptance', 'mode': mode}).json()
        script = sample_script(mode)
        body = {'expected_version': 0, 'title': script['title'], 'language': script['language'],
                'target_duration_seconds': script['target_duration_seconds'],
                'narration': ' '.join(s['narration'] for s in script['scenes']),
                'scenes': [{k: v for k, v in s.items() if k not in ('index', 'media_type')} for s in script['scenes']]}
        if mode == 'LOKAL':
            for scene in body['scenes']:
                scene['pexels_queries'] = ['bee on lavender', 'lavender flower']
        response = self.api.post(f"/api/projects/{project['id']}/scripts", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        approval = self.api.post(f"/api/projects/{project['id']}/scripts/1/approval")
        self.assertEqual(approval.status_code, 201, approval.text)
        run = approval.json()['production_run_id']
        self.jobs.append(run)
        with database() as conn:
            scenes = conn.execute('SELECT s.* FROM scenes s JOIN script_versions v ON v.id = s.script_version_id '
                                  'WHERE v.project_id = %s ORDER BY position', (project['id'],)).fetchall()
        return project['id'], run, {'project_id':project['id'], 'script':{'version':1}, 'mode': mode, 'media_type': project['media_type'], 'run_id': run, 'scenes': scenes}

    def work(self):
        ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def output(self, project, run):
        response = self.api.get(f'/api/projects/{project}/production-runs/{run}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_real_checkpoint_sources_and_resume_skip_scenes(self):
        project, run, body = self.project()
        prepared = collect_scenes(body, self.client)
        self.work()  # actual app.production_stages subprocess verifies all scene files
        output = self.output(project, run)
        self.assertEqual(output['state'], 'FAILED')
        self.assertEqual(output['error_code'], 'PIPER_MODEL_REQUIRED')  # next stage, not SCENES
        self.assertEqual([s['state'] for s in output['steps']], ['COMPLETED', 'FAILED', 'PENDING', 'PENDING', 'PENDING'])
        self.assertEqual(output['sources'], prepared['sources'])
        status = self.api.get(f'/api/projects/{project}/status').json()
        self.assertEqual(status['production_sources'], prepared['sources'])
        self.assertIsNone(status['final_artifact_id'])
        with database() as conn:
            rows = conn.execute('SELECT media_type, checksum_sha256 FROM artifacts WHERE production_run_id = %s', (run,)).fetchall()
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r['media_type'] == 'STOCK_VIDEO' for r in rows))
        # Even absent search cache cannot restart a completed SCENES checkpoint.
        shutil.rmtree(self.root / 'pexels-search')
        self.assertEqual(self.api.post(f'/api/projects/{project}/production-runs/{run}/resume').status_code, 200)
        self.work()
        output = self.output(project, run)
        self.assertEqual([s['attempts'] for s in output['steps']], [1, 2, 0, 0, 0])
        self.assertEqual(output['sources'], prepared['sources'])
        self.assertFalse((self.root / 'pexels-search').exists())

    def test_no_match_visible_with_no_artifact_or_fallback(self):
        project, run, body = self.project()
        self.videos = []
        with self.assertRaises(StageFailure):
            collect_scenes(body, self.client)  # stores controlled empty search results
        self.work()
        output = self.output(project, run)
        self.assertEqual(output['error_code'], 'PEXELS_NO_MATCH')
        self.assertIn('Szene 1', output['error_message'])
        self.assertIn('neu freigeben', output['error_message'])
        self.assertEqual([s['attempts'] for s in output['steps']], [1, 0, 0, 0, 0])
        self.assertFalse(output['sources'])
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s', (run,)).fetchone()['n'], 0)

    def test_cloud_never_enters_pexels_adapter(self):
        project, run, _ = self.project('CLOUD')
        self.work()
        output = self.output(project, run)
        self.assertEqual(output['error_code'], 'STAGE_UNAVAILABLE')
        self.assertFalse(output['sources'])
        self.assertFalse(list(self.root.iterdir()))


if __name__ == '__main__':
    unittest.main()
