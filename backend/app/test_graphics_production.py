"""Actual PostgreSQL/Redis/RQ/Piper/Remotion, with explicit visual test fixtures."""

import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

import psycopg

from app.api import database
from app.graphics import inspect_overlay, render_graphics
from app.media import checksum
from app.migrate import migrate
from app import test_production
from app.test_script_generation import ControlledWorker
from app.test_speech_production import MODEL


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and MODEL.is_file()
                     and shutil.which('ffprobe') and shutil.which('node'), 'Local graphics runtime and services required')
class GraphicsProductionTest(unittest.TestCase):
    setUpClass = classmethod(test_production.ProductionIntegrationTest.setUpClass.__func__)
    tearDownClass = classmethod(test_production.ProductionIntegrationTest.tearDownClass.__func__)
    setUp = test_production.ProductionIntegrationTest.setUp
    cleanup_queue = test_production.ProductionIntegrationTest.cleanup_queue
    project = test_production.ProductionIntegrationTest.project
    output = test_production.ProductionIntegrationTest.output

    def work(self):
        with patch.dict(os.environ, {'MEDIA_ROOT': self.files.name, 'PIPER_MODEL_PATH': str(MODEL)}), \
                patch('app.production_jobs.stage_command', return_value=[sys.executable, '-m', 'app.test_graphics_fixture']):
            ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def test_both_modes_render_exact_text_timing_and_resume_without_duplicates(self):
        for mode in ('LOKAL', 'CLOUD'):
            payload = test_production.test_api.ApiContractTest.script_payload(mode)
            for scene in payload['scenes']:
                scene['narration'] = 'Über Blüten fliegen Bienen. Grüße aus der Straße!'
                scene['duration_seconds'] = 7
            payload['narration'] = ' '.join(s['narration'] for s in payload['scenes'])
            project, run = self.project('Bienen, Blüten & Grüße', mode=mode, payload=payload)
            self.work()
            result = self.output(project, run)
            self.assertEqual(result['error_code'], 'STAGE_UNAVAILABLE')  # Isolated graphics suite disables ENCODING.
            self.assertEqual([s['state'] for s in result['steps']], ['COMPLETED']*3 + ['FAILED', 'PENDING'])
            graphics = result['graphics']
            self.assertEqual((graphics['width'], graphics['height'], graphics['fps'], graphics['duration_frames']), (720, 1280, 24, 1008))
            self.assertEqual(graphics['title'], 'Bienen, Blüten & Grüße')
            self.assertEqual([s['text'] for s in graphics['scenes']], [s['narration'] for s in payload['scenes']])
            self.assertEqual(self.client.get(f'/api/projects/{project}/status').json()['production_graphics'], graphics)
            with database() as conn:
                artifacts = conn.execute("SELECT * FROM artifacts WHERE production_run_id = %s AND media_type = 'GRAPHICS_OVERLAY'", (run,)).fetchall()
                previous = {s['name']: s['result'] for s in conn.execute("SELECT name,result FROM production_steps WHERE production_run_id = %s AND state = 'COMPLETED'", (run,))}
                script = conn.execute('SELECT * FROM script_versions WHERE project_id = %s', (project,)).fetchone()
                scenes = conn.execute('SELECT * FROM scenes WHERE script_version_id = %s ORDER BY position', (script['id'],)).fetchall()
            self.assertEqual(len(artifacts), 7)
            before = {}
            for a in artifacts:
                self.assertEqual(a['kind'], 'INTERMEDIATE')
                path = Path(self.files.name)/a['storage_path']
                inspect_overlay(path, shutil.which('ffprobe'))
                self.assertEqual(checksum(path), a['checksum_sha256'])
                before[path] = path.stat().st_mtime_ns
                response = self.client.get(f"/api/artifacts/{a['id']}")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()['content_available'])
            # The filesystem checkpoint must work independently of the DB checkpoint.
            with patch.dict(os.environ, {'MEDIA_ROOT': self.files.name}), patch('app.graphics.subprocess.run', wraps=__import__('subprocess').run) as launch:
                cached = render_graphics(dict(project_id=project,run_id=run, script=script, scenes=scenes, previous_results=previous))
                self.assertEqual(cached['graphics'], graphics)
                self.assertFalse(any(str(call.args[0][0]).endswith(('node', 'node.exe')) for call in launch.call_args_list))
            self.assertEqual(self.client.post(f'/api/projects/{project}/production-runs/{run}/resume').status_code, 200)
            self.work()
            resumed = self.output(project, run)
            self.assertEqual([s['attempts'] for s in resumed['steps']], [1, 1, 1, 2, 0])
            self.assertEqual(resumed['graphics'], graphics)
            self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})
            with database() as conn:
                self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s AND media_type = 'GRAPHICS_OVERLAY'", (run,)).fetchone()['n'], 7)

    def test_changed_speech_blocks_graphics_and_encoding(self):
        project, run = self.project('changed-audio')
        self.work()
        result = self.output(project, run)
        self.assertEqual(result['error_code'], 'GRAPHICS_SPEECH_REQUIRED')
        self.assertEqual([s['attempts'] for s in result['steps']], [1, 1, 1, 0, 0])
        self.assertIsNone(result['graphics'])
        with database() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s AND media_type = 'GRAPHICS_OVERLAY'", (run,)).fetchone()['n'], 0)

    def test_migration_roundtrip_mode_guards_and_nonlossy_rollback(self):
        migrate('down'); migrate('up')
        with database() as conn:
            self.assertEqual([r['version'] for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version')], [1, 2, 3, 4, 5, 6])
            for mode in ('LOKAL', 'CLOUD'):
                project, run = self.project(mode=mode)
                insert = "INSERT INTO artifacts (project_id,production_run_id,kind,media_type,storage_path,checksum_sha256) VALUES (%s,%s,%s,%s,'graphic.png',%s)"
                conn.execute(insert, (project, run, 'INTERMEDIATE', 'GRAPHICS_OVERLAY', 'a'*64))
                for kind, media in [('SOURCE', 'GRAPHICS_OVERLAY'), ('FINAL', 'GRAPHICS_OVERLAY'),
                                    ('SOURCE', 'AI_GENERATED_VIDEO' if mode == 'LOKAL' else 'STOCK_VIDEO')]:
                    with self.assertRaises(psycopg.Error), conn.transaction():
                        conn.execute(insert, (project, run, kind, media, 'b'*64))
        with self.assertRaises(psycopg.Error):
            migrate('down')
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n'], 6)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE media_type = 'GRAPHICS_OVERLAY'").fetchone()['n'], 2)
