"""CLOUD approval to playable FINAL: fixture sourcing, real CPU media functions."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from app.database import database
from app.encoding import inspect_master
from app.media import checksum, media_root
from app.production_jobs import run_production
from app.test_api import ApiContractTest
from app.test_production import ProductionIntegrationTest
from app.test_script_generation import ControlledWorker
from app.test_speech_production import MODEL
from app.test_storage_integration import StorageIntegrationTest


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and MODEL.is_file(),
                     'Isolated PostgreSQL/Redis and installed Piper model required')
class CloudProductionTest(unittest.TestCase):
    setUpClass = classmethod(ProductionIntegrationTest.setUpClass.__func__)
    tearDownClass = classmethod(ProductionIntegrationTest.tearDownClass.__func__)
    cleanup_queue = ProductionIntegrationTest.cleanup_queue
    project = ProductionIntegrationTest.project
    output = ProductionIntegrationTest.output
    login = StorageIntegrationTest.login

    def setUp(self):
        StorageIntegrationTest.setUp(self)
        self.provider = Path(self.files.name)/'provider'
        self.provider.mkdir()
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-f', 'lavfi',
            '-i', 'color=c=blue:s=720x1280:r=16', '-frames:v', '81', '-c:v', 'libx264',
            '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', str(self.provider/'raw.mp4')],
            check=True, timeout=15)
        env = patch.dict(os.environ, {'WAN_FIXTURE_ROOT': str(self.provider)})
        env.start(); self.addCleanup(env.stop)

    def work(self):
        with patch('app.production_jobs.stage_command', return_value=[sys.executable, '-m', 'app.test_cloud_fixture']):
            ControlledWorker([self.queue], connection=self.redis).work(burst=True, logging_level='WARNING')

    def make_project(self):
        body = ApiContractTest.script_payload('CLOUD')
        body['target_duration_seconds'] = 36
        for scene in body['scenes']:
            scene.update(duration_seconds=6, narration='Dieses Testvideo prüft den CLOUD-Ablauf.')
        body['narration'] = ' '.join(s['narration'] for s in body['scenes'])
        return self.project('CONTROLLED_TEST – CLOUD-Funktionsprüfung', mode='CLOUD', payload=body)

    def test_approval_full_pipeline_manifest_stream_and_duplicate_delivery(self):
        project, run = self.make_project()
        repeated = self.client.post(f'/api/projects/{project}/scripts/1/approval')
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()['production_run_id'], run)
        self.work()
        output = self.output(project, run)
        self.assertEqual(output['state'], 'COMPLETED', output)
        self.assertEqual([s['state'] for s in output['steps']], ['COMPLETED']*5)
        self.assertEqual([s['attempts'] for s in output['steps']], [1]*5)
        self.assertFalse(output['sources'])
        self.assertEqual(len(output['wan_sources']), 6)
        self.assertTrue(all(c['execution'] == 'CONTROLLED_TEST'
                            for s in output['wan_sources'] for c in s['clips']))
        with database() as conn:
            final = conn.execute("SELECT * FROM artifacts WHERE production_run_id=%s AND kind='FINAL'", (run,)).fetchone()
            sources = conn.execute("SELECT * FROM artifacts WHERE production_run_id=%s AND kind='SOURCE'", (run,)).fetchall()
        self.assertEqual(len(sources), 6)
        self.assertTrue(all(s['media_type'] == 'AI_GENERATED_VIDEO' for s in sources))
        root = media_root()
        target = root/final['storage_path']
        manifest = json.loads(target.with_name('manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['wan_sources'], output['wan_sources'])
        self.assertEqual(manifest['media_type'], 'AI_GENERATED_VIDEO')
        self.assertFalse(manifest['sources'])
        self.assertEqual((manifest['encoding']['duration_seconds'], manifest['encoding']['duration_frames']), (36, 864))
        self.assertEqual(checksum(target), final['checksum_sha256'])
        inspect_master(target, 864, shutil.which('ffprobe'), shutil.which('ffmpeg'))
        status = self.client.get(f'/api/projects/{project}/status').json()
        self.assertEqual(status['production_wan_sources'], manifest['wan_sources'])
        self.assertEqual(status['final_artifact_id'], str(final['id']))
        self.assertFalse(status['video_approved'])
        url = f"/api/artifacts/{final['id']}/content"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.login()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(hashlib.sha256(response.content).hexdigest(), final['checksum_sha256'])
        self.assertEqual(self.client.head(url).headers['content-length'], str(target.stat().st_size))
        chunk = self.client.get(url, headers={'Range': 'bytes=0-127'})
        self.assertEqual(chunk.status_code, 206)
        self.assertEqual(chunk.content, target.read_bytes()[:128])
        self.assertEqual(len(list((self.provider/'jobs').glob('*.json'))), 12)
        timestamps = {p: p.stat().st_mtime_ns for p in root.rglob('*.mp4')}
        run_production(run)  # completed delivery cannot call a new provider
        self.assertEqual(timestamps, {p: p.stat().st_mtime_ns for p in root.rglob('*.mp4')})
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM production_runs WHERE project_id=%s', (project,)).fetchone()['n'], 1)
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s AND kind='FINAL'", (run,)).fetchone()['n'], 1)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM platform_publications').fetchone()['n'], 0)
        self.assertFalse(list(root.rglob('*.part')))
        if location := os.getenv('CLOUD_TEST_PREVIEW_DIR'):
            preview = Path(location).resolve()
            from app.media import ROOT
            if not preview.is_relative_to((ROOT/'.data').resolve()):
                raise ValueError('Test preview must stay in ignored project .data')
            preview.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, preview/'CONTROLLED_TEST-cloud.mp4')
            (preview/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    def test_clip_limit_and_expired_resume_make_no_provider_job(self):
        project, run = self.make_project()
        with patch.dict(os.environ, {'WAN_MAX_CLIPS': '1'}): self.work()
        first = self.output(project, run)
        self.assertEqual(first['error_code'], 'WAN_CLIP_LIMIT')
        self.assertFalse(first['wan_sources'])
        self.assertFalse(list(self.provider.rglob('*.json')))
        with database() as conn:
            conn.execute("UPDATE production_runs SET started_at=now()-interval '3601 seconds' WHERE id=%s", (run,))
        resumed = self.client.post(f'/api/projects/{project}/production-runs/{run}/resume')
        self.assertEqual(resumed.status_code, 200, resumed.text)
        self.jobs.update(self.queue.job_ids)
        self.work()
        self.assertEqual(self.output(project, run)['error_code'], 'WAN_RUNTIME_LIMIT')
        self.assertFalse(list(self.provider.rglob('*.json')))
        with database() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM artifacts WHERE production_run_id=%s', (run,)).fetchone()['n'], 0)


if __name__ == '__main__': unittest.main()
