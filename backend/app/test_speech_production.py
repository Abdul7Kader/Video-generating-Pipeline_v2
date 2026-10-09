"""Real PostgreSQL/Redis/RQ, isolated stages and installed CPU Piper model."""

import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

import psycopg

from app.api import database
from app.migrate import migrate
from app import test_production
from app.speech import ROOT, inspect_audio
from app.test_script_generation import ControlledWorker


MODEL = Path(os.environ.get('PIPER_MODEL_PATH') or ROOT / '.data/models/de_DE-thorsten-high.onnx')


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and MODEL.is_file() and shutil.which('ffprobe'),
                     'PostgreSQL, Redis, ffprobe and installed Piper model required')
class SpeechProductionTest(unittest.TestCase):
    setUpClass = classmethod(test_production.ProductionIntegrationTest.setUpClass.__func__)
    tearDownClass = classmethod(test_production.ProductionIntegrationTest.tearDownClass.__func__)
    setUp = test_production.ProductionIntegrationTest.setUp
    cleanup_queue = test_production.ProductionIntegrationTest.cleanup_queue
    project = test_production.ProductionIntegrationTest.project
    output = test_production.ProductionIntegrationTest.output

    def work(self):
        with patch.dict(os.environ, {'MEDIA_ROOT': self.files.name, 'PIPER_MODEL_PATH': str(MODEL), 'PYTHONIOENCODING': 'cp1252'}), \
                patch('app.production_jobs.stage_command', return_value=[sys.executable, '-m', 'app.test_speech_fixture']):
            ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def test_real_piper_both_modes_durations_and_completed_resume(self):
        for mode in ('LOKAL', 'CLOUD'):
            payload = test_production.test_api.ApiContractTest.script_payload(mode)
            for scene in payload['scenes']:
                scene['narration'] = 'Über blühende Wiesen fliegen Bienen. Sie bestäuben unsere Pflanzen.'
            payload['narration'] = ' '.join(s['narration'] for s in payload['scenes'])
            project, run = self.project(mode=mode, payload=payload)
            self.work()
            result = self.output(project, run)
            self.assertEqual(result['error_code'], 'STAGE_UNAVAILABLE')  # isolate speech from graphics
            self.assertEqual([s['state'] for s in result['steps']], ['COMPLETED', 'COMPLETED', 'FAILED', 'PENDING', 'PENDING'])
            self.assertEqual(len(result['speech']), 6)
            self.assertEqual(self.client.get(f'/api/projects/{project}/status').json()['production_speech'], result['speech'])
            with database() as conn:
                artifacts = conn.execute("SELECT storage_path, artifact_key, media_type FROM artifacts WHERE production_run_id = %s AND kind = 'INTERMEDIATE'", (run,)).fetchall()
            self.assertEqual(len(artifacts), 6)
            before = {}
            for artifact in artifacts:
                self.assertEqual(artifact['media_type'], 'SPEECH_AUDIO')
                segment = next(s for s in result['speech'] if s['artifact_key'] == artifact['artifact_key'])
                path = Path(self.files.name) / artifact['storage_path']
                measured = inspect_audio(path, 22050, shutil.which('ffprobe'))
                self.assertEqual(measured['duration_seconds'], segment['duration_seconds'])
                self.assertEqual(measured['frames'], segment['frames'])
                before[path] = path.stat().st_mtime_ns
            self.assertEqual(self.client.post(f'/api/projects/{project}/production-runs/{run}/resume').status_code, 200)
            self.work()
            resumed = self.output(project, run)
            self.assertEqual([s['attempts'] for s in resumed['steps']], [1, 1, 2, 0, 0])
            self.assertEqual(resumed['speech'], result['speech'])
            self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_empty_silent_and_failed_speech_block_graphics(self):
        for scenario, code in [('empty-speech', 'SPEECH_TEXT_REQUIRED'), ('silent-speech', 'SPEECH_OUTPUT_INVALID'),
                               ('failed-speech', 'SPEECH_SYNTHESIS_FAILED')]:
            project, run = self.project(scenario)
            self.work()
            result = self.output(project, run)
            self.assertEqual(result['error_code'], code)
            self.assertEqual([s['attempts'] for s in result['steps']], [1, 1, 0, 0, 0])
            self.assertFalse(result['speech'])
            self.assertIn('Szene 1' if scenario != 'silent-speech' else 'Rendering wurde blockiert', result['error_message'])
            with database() as conn:
                self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id = %s AND media_type = 'SPEECH_AUDIO'", (run,)).fetchone()['n'], 0)

    def test_migration_roundtrip_and_audio_kind_guards(self):
        migrate('down'); migrate('up')
        with database() as conn:
            self.assertEqual([r['version'] for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version')], [1, 2, 3, 4, 5, 6, 7, 8])
            for mode, media in [('LOKAL', 'STOCK_VIDEO'), ('CLOUD', 'AI_GENERATED_VIDEO')]:
                project, run = self.project(mode=mode)
                insert = "INSERT INTO artifacts (project_id,production_run_id,kind,media_type,storage_path,checksum_sha256) VALUES (%s,%s,%s,%s,'audio.wav',%s)"
                conn.execute(insert, (project, run, 'INTERMEDIATE', 'SPEECH_AUDIO', 'a'*64))
                for kind, bad in [('SOURCE', 'SPEECH_AUDIO'), ('FINAL', 'SPEECH_AUDIO'), ('SOURCE', 'AI_GENERATED_VIDEO' if mode == 'LOKAL' else 'STOCK_VIDEO')]:
                    with self.assertRaises(psycopg.Error), conn.transaction():
                        conn.execute(insert, (project, run, kind, bad, 'b'*64))
        # Rollback must preserve real audio and migration version rather than delete data.
        with self.assertRaises(psycopg.Error):
            migrate('down')
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n'], 8)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE media_type = 'SPEECH_AUDIO'").fetchone()['n'], 2)


if __name__ == '__main__':
    unittest.main()
