"""Short real PostgreSQL/RQ/subprocess test, exclusively local fixture clips."""
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

from app.api import database
from app.test_api import ApiContractTest
from app.test_production import ProductionIntegrationTest
from app.test_script_generation import ControlledWorker
from app.test_wan import WanTransferTest


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and shutil.which('ffmpeg')
                    and shutil.which('ffprobe'),'PostgreSQL, Redis and FFmpeg required')
class WanProductionTest(unittest.TestCase):
    project = ProductionIntegrationTest.project
    output = ProductionIntegrationTest.output
    cleanup_queue = ProductionIntegrationTest.cleanup_queue

    @classmethod
    def setUpClass(cls):
        ProductionIntegrationTest.setUpClass.__func__(cls)
        WanTransferTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        WanTransferTest.tearDownClass.__func__(cls)
        ProductionIntegrationTest.tearDownClass.__func__(cls)

    def setUp(self):
        ProductionIntegrationTest.setUp(self)
        root=Path(self.files.name)
        provider=root/'provider';provider.mkdir()
        shutil.copyfile(self.fixture_root/'raw.mp4',provider/'raw.mp4')
        env=patch.dict(os.environ,{'WAN_FIXTURE_ROOT':str(provider),'MEDIA_ROOT':str(root/'chosen-media'),
                                   'WORKER_CONFIG_PATH':''})
        env.start();self.addCleanup(env.stop)
        self.provider=provider

    def work(self):
        with patch('app.production_jobs.stage_command',return_value=[sys.executable,'-m','app.test_wan_fixture']):
            ControlledWorker([self.queue],connection=self.redis).work(burst=True,logging_level='WARNING')

    def make_project(self, scenario):
        body=ApiContractTest.script_payload('CLOUD')
        body['target_duration_seconds']=36
        for scene in body['scenes']: scene['duration_seconds']=6
        body['narration']=' '.join(scene['narration'] for scene in body['scenes'])
        return self.project(scenario=scenario,mode='CLOUD',payload=body)

    def test_scene_checkpoint_api_metadata_and_duplicate_delivery(self):
        project,run=self.make_project('success');self.work()
        output=self.output(project,run)
        self.assertEqual(output['error_code'],'TEST_STOP_AFTER_SCENES')
        self.assertEqual(output['steps'][0]['state'],'COMPLETED')
        self.assertEqual(len(output['wan_sources']),6)
        self.assertTrue(all(c['execution']=='CONTROLLED_TEST' for s in output['wan_sources'] for c in s['clips']))
        self.assertFalse(output['sources'])
        from app.production_jobs import run_production
        run_production(run)
        status=self.client.get(f'/api/projects/{project}/status').json()
        self.assertEqual(status['production_wan_sources'],output['wan_sources'])
        with database() as conn:
            rows=conn.execute('SELECT media_type FROM artifacts WHERE production_run_id=%s',(run,)).fetchall()
            self.assertEqual(len(rows),6)
            self.assertTrue(all(r['media_type']=='AI_GENERATED_VIDEO' for r in rows))
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM production_runs WHERE project_id=%s',(project,)).fetchone()['n'],1)
        self.assertEqual(len(list((self.provider/'jobs').glob('*.json'))),12)

    def test_interrupted_transfer_has_no_artifact_and_resume_reuses_intent(self):
        project,run=self.make_project('timeout');self.work()
        output=self.output(project,run)
        self.assertEqual(output['error_code'],'WAN_TRANSFER_TIMEOUT')
        self.assertFalse(output['wan_sources'])
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s',(run,)).fetchone()['n'],0)
            conn.execute('UPDATE production_runs SET available_at=now() WHERE id=%s',(run,))
        from app.production_dispatch import recover_productions
        with patch.dict(os.environ,{'WAN_FIXTURE_SCENARIO':'success'}):
            recover_productions(self.queue);self.jobs.update(self.queue.job_ids);self.work()
        output=self.output(project,run)
        self.assertEqual(output['steps'][0]['state'],'COMPLETED')
        self.assertEqual(output['steps'][0]['attempts'],2)
        self.assertEqual(len(list((self.provider/'jobs').glob('*.json'))),12)
        self.assertFalse(list(Path(self.files.name).rglob('*.part')))
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s',(run,)).fetchone()['n'],6)


if __name__=='__main__': unittest.main()
