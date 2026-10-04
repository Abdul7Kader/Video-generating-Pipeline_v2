"""Real service/CPU-media integration; explicitly controlled scene source."""

import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

from app.api import database
from app.encoding import encode_video, inspect_master
from app.media import checksum
from app import test_production
from app.test_script_generation import ControlledWorker
from app.test_speech_production import MODEL


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and MODEL.is_file()
                    and shutil.which('ffmpeg') and shutil.which('node'), 'Encoding runtime/services required')
class EncodingProductionTest(unittest.TestCase):
    setUpClass = classmethod(test_production.ProductionIntegrationTest.setUpClass.__func__)
    tearDownClass = classmethod(test_production.ProductionIntegrationTest.tearDownClass.__func__)
    setUp = test_production.ProductionIntegrationTest.setUp
    cleanup_queue = test_production.ProductionIntegrationTest.cleanup_queue
    project = test_production.ProductionIntegrationTest.project
    output = test_production.ProductionIntegrationTest.output

    def work(self):
        with patch.dict(os.environ, {'MEDIA_ROOT':self.files.name, 'PIPER_MODEL_PATH':str(MODEL)}), \
             patch('app.production_jobs.stage_command', return_value=[sys.executable,'-m','app.test_encoding_fixture']):
            ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def test_both_modes_encode_and_resume_keeps_completed_file_and_artifact(self):
        for mode in ('LOKAL','CLOUD'):
            body = test_production.test_api.ApiContractTest.script_payload(mode)
            for scene in body['scenes']:
                scene.update(duration_seconds=5, narration='Über Blüten fliegen Bienen.')
            body['narration'] = ' '.join(s['narration'] for s in body['scenes'])
            project, run = self.project('Grüße aus der Straße', mode=mode, payload=body)
            self.work()
            result = self.output(project,run)
            self.assertEqual(result['error_code'],'STAGE_UNAVAILABLE')  # Storage remains step 18.
            self.assertEqual([s['state'] for s in result['steps']],['COMPLETED']*4+['FAILED'])
            self.assertEqual(result['encoding']['duration_frames'],720)
            self.assertEqual(self.client.get(f'/api/projects/{project}/status').json()['production_encoding'],result['encoding'])
            with database() as conn:
                records = conn.execute("SELECT * FROM artifacts WHERE production_run_id=%s AND media_type='FINAL_VIDEO'",(run,)).fetchall()
                previous = {s['name']:s['result'] for s in conn.execute("SELECT name,result FROM production_steps WHERE production_run_id=%s AND state='COMPLETED'",(run,))}
                script = conn.execute('SELECT * FROM script_versions WHERE project_id=%s',(project,)).fetchone()
                scenes = conn.execute('SELECT * FROM scenes WHERE script_version_id=%s ORDER BY position',(script['id'],)).fetchall()
            self.assertEqual(len(records),1)
            artifact = records[0]; path = Path(self.files.name)/artifact['storage_path']
            self.assertEqual(artifact['kind'],'INTERMEDIATE')
            self.assertEqual(checksum(path),artifact['checksum_sha256'])
            inspect_master(path,720,shutil.which('ffprobe'),shutil.which('ffmpeg'))
            self.assertFalse(self.client.get(f"/api/artifacts/{artifact['id']}").json()['content_available'])
            before = path.stat().st_mtime_ns
            with patch.dict(os.environ, {'MEDIA_ROOT':self.files.name}), patch('app.encoding.run_ffmpeg') as render:
                encode_video(dict(project_id=project,run_id=run,mode=mode,media_type='STOCK_VIDEO' if mode=='LOKAL' else 'AI_GENERATED_VIDEO',
                                  script=script,scenes=scenes,previous_results=previous))
                render.assert_not_called()
            self.assertEqual(self.client.post(f'/api/projects/{project}/production-runs/{run}/resume').status_code,200)
            self.work()
            resumed = self.output(project,run)
            self.assertEqual([s['attempts'] for s in resumed['steps']],[1,1,1,1,2])
            self.assertEqual(resumed['encoding'],result['encoding'])
            self.assertEqual(path.stat().st_mtime_ns,before)
            with database() as conn:
                self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s AND media_type='FINAL_VIDEO'",(run,)).fetchone()['n'],1)

    def test_short_source_blocks_encoding_without_output_or_storage_attempt(self):
        project,run = self.project('short-source')
        self.work()
        result = self.output(project,run)
        self.assertEqual(result['error_code'],'ENCODING_SOURCE_INVALID')
        self.assertEqual([s['attempts'] for s in result['steps']],[1,1,1,1,0])
        self.assertIsNone(result['encoding'])
        with database() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s AND media_type='FINAL_VIDEO'",(run,)).fetchone()['n'],0)
