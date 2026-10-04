"""Real PostgreSQL/Redis/RQ, media access, copy and publication acceptance."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
import psycopg
from app import test_production
from app.database import database
from app.media import checksum, media_root
from app.media_gateway import MediaGateway
from app.migrate import migrate
from app.storage_jobs import recover_storage_changes
from app.storage_settings import initialize_store, private_write
from app.test_script_generation import ControlledWorker
from app.test_speech_production import MODEL

@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL') and MODEL.is_file(),'Services/model required')
class StorageIntegrationTest(unittest.TestCase):
    setUpClass=classmethod(test_production.ProductionIntegrationTest.setUpClass.__func__)
    tearDownClass=classmethod(test_production.ProductionIntegrationTest.tearDownClass.__func__)
    cleanup_queue=test_production.ProductionIntegrationTest.cleanup_queue
    project=test_production.ProductionIntegrationTest.project
    output=test_production.ProductionIntegrationTest.output

    def setUp(self):
        test_production.ProductionIntegrationTest.setUp(self)
        with database() as conn: conn.execute('TRUNCATE media_access, storage_changes')
        self.client.cookies.clear()
        root=Path(self.files.name)/'media'; root.mkdir()
        config=Path(self.files.name)/'worker.json'
        private_write(config,dict(MEDIA_ROOT=str(root),DATABASE_URL=os.environ['DATABASE_URL'],REDIS_URL=os.environ['REDIS_URL']))
        env=patch.dict(os.environ,dict(WORKER_CONFIG_PATH=str(config),MEDIA_ROOT=str(root),MEDIA_RPC_NAMESPACE='storage-test:'+uuid4().hex,PIPER_MODEL_PATH=str(MODEL)))
        env.start(); self.addCleanup(env.stop)
        initialize_store()
        self.gateway=MediaGateway().start(); self.addCleanup(self.gateway.close)
        self.origin={'Origin':'http://testserver'}

    def login(self):
        response=self.client.post('/api/media-session',json={'password':'controlled-test-password'},headers=self.origin)
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=strict',response.headers['set-cookie'])

    def work(self):
        with patch('app.production_jobs.stage_command',return_value=[sys.executable,'-m','app.test_storage_fixture']):
            ControlledWorker([self.queue],connection=self.redis).work(burst=True,logging_level='WARNING')

    def test_access_origin_password_logout_and_migration_guard(self):
        self.assertEqual(self.client.get('/api/storage').status_code,401)
        self.assertEqual(self.client.get(f'/api/artifacts/{uuid4()}/content').status_code,401)
        self.assertEqual(self.client.post('/api/media-session',json={'password':'controlled-test-password'},headers={'Origin':'https://other.invalid'}).status_code,403)
        self.login()
        wrong=self.client.post('/api/media-session',json={'password':'controlled-wrong-password'},headers=self.origin)
        self.assertEqual(wrong.status_code,401)
        self.assertEqual(self.client.post('/api/storage/changes',json={'path':'abc','expected_path':'abc'},headers={'Origin':'https://other.invalid'}).status_code,403)
        with self.assertRaises(psycopg.errors.RaiseException): migrate('down')
        self.assertEqual(self.client.delete('/api/media-session',headers=self.origin).status_code,200)
        self.assertEqual(self.client.get('/api/storage').status_code,401)
        self.client.cookies.set('video_media_session','9999999999.'+'a'*32+'.'+'b'*64,path='/api')
        self.assertFalse(self.client.get('/api/media-session').json()['authorized'])

    def test_copy_outbox_recovery_checksums_and_conflict_keeps_current_root(self):
        self.login()
        old=media_root(); (old/'projects').mkdir(); (old/'projects'/'fixture.bin').write_bytes(b'media'*100000)
        target=Path(self.files.name)/'neuer Speicher Grüße'
        with patch('app.storage_api.Queue',return_value=self.queue),patch.object(self.queue,'enqueue',side_effect=__import__('redis').exceptions.ConnectionError('controlled')):
            response=self.client.post('/api/storage/changes',json={'path':str(target),'expected_path':str(old)},headers=self.origin)
        self.assertEqual(response.status_code,202,response.text)
        recover_storage_changes(self.queue); self.jobs.update(self.queue.job_ids)
        # An interrupted copy may have already verified a complete target file.
        from app.storage_settings import copy_store
        config=json.loads(Path(os.environ['WORKER_CONFIG_PATH']).read_text())
        copy_store(old,target,config['MEDIA_STORE_ID'],lambda *_:None)
        ControlledWorker([self.queue],connection=self.redis).work(burst=True,logging_level='WARNING')
        change=self.client.get('/api/storage/changes/'+response.json()['id']).json()
        self.assertEqual(change['state'],'COMPLETED',change)
        self.assertEqual(change['total_bytes'],change['verified_bytes'])
        self.assertEqual(media_root(),target)
        self.assertEqual(checksum(old/'projects'/'fixture.bin'),checksum(target/'projects'/'fixture.bin'))
        self.gateway.close(); self.gateway=MediaGateway().start(); self.addCleanup(self.gateway.close)
        self.assertEqual(self.client.get('/api/storage').json()['path'],str(target))
        foreign=Path(self.files.name)/'foreign'; foreign.mkdir(); (foreign/'keep.txt').write_text('keep')
        with patch('app.storage_api.Queue',return_value=self.queue):
            response=self.client.post('/api/storage/changes',json={'path':str(foreign),'expected_path':str(target)},headers=self.origin)
        self.jobs.update(self.queue.job_ids)
        ControlledWorker([self.queue],connection=self.redis).work(burst=True,logging_level='WARNING')
        self.assertEqual(self.client.get('/api/storage/changes/'+response.json()['id']).json()['state'],'FAILED')
        self.assertEqual(media_root(),target); self.assertEqual((foreign/'keep.txt').read_text(),'keep')

    def test_recovery_after_activation_before_database_checkpoint(self):
        from app.storage_jobs import change_storage
        from app.storage_settings import activate_store
        self.login()
        old=media_root(); (old/'projects').mkdir(); (old/'projects'/'file.bin').write_bytes(b'unchanged media')
        target=Path(self.files.name)/'after interruption'
        with patch('app.storage_api.Queue',return_value=self.queue):
            response=self.client.post('/api/storage/changes',json={'path':str(target),'expected_path':str(old)},headers=self.origin)
        identity=response.json()['id']; self.jobs.update(self.queue.job_ids)
        def activated_then_interrupted(path,store_id):
            activate_store(path,store_id)
            raise SystemExit('controlled interruption')
        with patch('app.storage_jobs.activate_store',side_effect=activated_then_interrupted),self.assertRaises(SystemExit):
            change_storage(identity)
        self.assertEqual(media_root(),target)
        self.assertEqual(self.client.get('/api/storage/changes/'+identity).json()['state'],'RUNNING')
        recover_storage_changes(self.queue); self.jobs.update(self.queue.job_ids)
        ControlledWorker([self.queue],connection=self.redis).work(burst=True,logging_level='WARNING')
        result=self.client.get('/api/storage/changes/'+identity).json()
        self.assertEqual((result['state'],result['attempts']),('COMPLETED',2))
        self.assertEqual(result['total_bytes'],result['verified_bytes'])
        self.assertEqual((old/'projects'/'file.bin').read_bytes(),(target/'projects'/'file.bin').read_bytes())

    def test_both_modes_publish_real_mp4_ranges_corruption_and_path_protection(self):
        self.login()
        for mode in ('LOKAL','CLOUD'):
            body=test_production.test_api.ApiContractTest.script_payload(mode)
            for scene in body['scenes']: scene.update(duration_seconds=5,narration='Über Blüten fliegen Bienen.')
            body['narration']=' '.join(s['narration'] for s in body['scenes'])
            project,run=self.project('Grüße aus der Straße',mode=mode,payload=body)
            self.work()
            output=self.output(project,run)
            self.assertEqual(output['state'],'COMPLETED',output)
            self.assertEqual([s['attempts'] for s in output['steps']],[1]*5)
            with database() as conn:
                row=conn.execute("SELECT * FROM artifacts WHERE production_run_id=%s AND kind='FINAL'",(run,)).fetchone()
            identity=str(row['id']); url=f'/api/artifacts/{identity}/content'
            path=media_root()/row['storage_path']; raw=path.read_bytes()
            self.assertTrue(row['storage_path'].startswith(f'projects/{project}/versions/1/runs/'))
            self.assertTrue(self.client.get(f'/api/artifacts/{identity}').json()['content_available'])
            response=self.client.get(url)
            self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
            self.assertEqual(hashlib.sha256(response.content).hexdigest(),row['checksum_sha256'])
            self.assertEqual(self.client.head(url).headers['content-length'],str(len(raw)))
            for value,expected in [('bytes=0-99',raw[:100]),('bytes=-100',raw[-100:]),('bytes=100-',raw[100:])]:
                response=self.client.get(url,headers={'Range':value})
                self.assertEqual(response.status_code,206); self.assertEqual(response.content,expected)
            for value in ('bytes=999999999999-','bytes=0-1,5-6','bytes=-0','bytes=9-2'):
                self.assertEqual(self.client.get(url,headers={'Range':value}).status_code,416)
            self.assertEqual(self.client.get(url,headers={'Range':'bytes=0-1','If-Range':'"different"'}).status_code,200)
            path.write_bytes(b'broken')
            self.assertEqual(self.client.get(url).status_code,409)
            path.write_bytes(raw)
            with database() as conn: conn.execute('UPDATE artifacts SET storage_path=%s WHERE id=%s',('../private.txt',identity))
            self.assertNotEqual(self.client.get(url).status_code,200)
