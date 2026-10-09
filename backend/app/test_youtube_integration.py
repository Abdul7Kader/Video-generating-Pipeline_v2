"""Real PostgreSQL, Redis/RQ and media gateway; only YouTube is synthetic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch
from uuid import uuid4
import httpx
import psycopg
from redis import Redis
from rq import Queue
from psycopg.types.json import Jsonb
from app import test_publication_integration as fixture
from app import youtube_jobs as jobs, youtube_upload as yt
from app.database import database
from app.media import checksum
from app.migrate import MIGRATIONS, migrate
from app.worker import WindowsWorker

SESSION=yt.INSERT+'?uploadType=resumable&upload_id=controlled-session'
VIDEO='testVideo01'


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL'),'isolated services required')
class YouTubeIntegrationTest(unittest.TestCase):
    setUpClass=classmethod(fixture.PublicationIntegrationTest.setUpClass.__func__)
    tearDownClass=classmethod(fixture.PublicationIntegrationTest.tearDownClass.__func__)
    write_config=fixture.PublicationIntegrationTest.write_config
    login=fixture.PublicationIntegrationTest.login
    post=fixture.PublicationIntegrationTest.post
    delete=fixture.PublicationIntegrationTest.delete
    begin=fixture.PublicationIntegrationTest.begin
    callback=fixture.PublicationIntegrationTest.callback
    connected=fixture.PublicationIntegrationTest.connected
    save=fixture.PublicationIntegrationTest.save
    release=fixture.PublicationIntegrationTest.release

    def provider(self, request):
        return fixture.PublicationIntegrationTest.provider(self,request)

    def setUp(self):
        def fixture_checksum(path):
            if path.name=='master.mp4':
                padding=yt.CHUNK+700000-path.stat().st_size
                with path.open('ab') as handle: handle.write(padding.to_bytes(4,'big')+b'free'+b'\0'*(padding-8))
            return checksum(path)
        if self._testMethodName=='test_large_valid_mp4_uploads_in_bounded_chunks_with_verified_progress':
            # Prepare the large fixture before its original checksum/consent.
            # The real gateway later hashes all bytes independently.
            with patch('app.test_publication_integration.checksum',side_effect=fixture_checksum):
                fixture.PublicationIntegrationTest.setUp(self)
        else: fixture.PublicationIntegrationTest.setUp(self)
        self.config_data['providers']['youtube']['upload_enabled']=True;self.write_config()
        self.connected();self.assertEqual(self.save().status_code,200)
        released=self.release();self.assertEqual(released.status_code,201,released.text)
        self.identity=released.json()['jobs'][0]['id']
        self.start_path=self.path+'/jobs/'+self.identity+'/youtube'
        self.remote=[];self.offset=0;self.failure=None;self.processed=True;self.visibility='private';self.remote_channel=self.channel_id
        mock=patch('app.youtube_upload.http_client',side_effect=lambda:httpx.Client(transport=httpx.MockTransport(self.youtube)))
        mock.start();self.addCleanup(mock.stop)
        self.redis=Redis.from_url(os.environ['REDIS_URL']);self.addCleanup(self.redis.close)
        self.queue=Queue('default',connection=self.redis);self.queue.empty()

    def youtube(self, request):
        if request.url.path=='/youtube/v3/channels': return self.provider(request)
        self.remote.append(request)
        if request.method=='POST':
            if self.failure=='init-timeout': raise httpx.ReadTimeout('controlled-private',request=request)
            self.assertEqual(request.url.path,'/upload/youtube/v3/videos')
            self.assertEqual(json.loads(request.content),self.job()['snapshot']['profile'])
            return httpx.Response(200,headers={'Location':SESSION})
        if request.method=='GET':
            self.assertEqual(request.url.path,'/youtube/v3/videos')
            return httpx.Response(200,json={'items':[dict(id=VIDEO,snippet={'channelId':self.remote_channel},
                status={'uploadStatus':'processed' if self.processed else 'uploaded','privacyStatus':self.visibility},
                processingDetails={'processingStatus':'succeeded' if self.processed else 'processing'})]})
        self.assertEqual(str(request.url),SESSION)
        if self.failure=='session-lost': return httpx.Response(410)
        content_range=request.headers['Content-Range']
        if content_range.startswith('bytes */'):
            if self.offset==self.file.stat().st_size: return httpx.Response(201,json={'id':VIDEO})
            return httpx.Response(308,headers={'Range':f'bytes=0-{self.offset-1}'} if self.offset else {})
        self.assertTrue(content_range.startswith(f'bytes {self.offset}-'),content_range)
        self.assertEqual(request.content,self.file.read_bytes()[self.offset:self.offset+len(request.content)])
        if self.failure=='partial-timeout':
            self.offset+=256;self.failure=None
            raise httpx.ReadTimeout('controlled-private',request=request)
        self.offset+=len(request.content)
        if self.failure=='final-timeout':
            self.failure=None;raise httpx.ReadTimeout('controlled-private',request=request)
        if self.failure=='rate-limit':
            self.offset-=len(request.content);self.failure=None
            return httpx.Response(429,headers={'Retry-After':'120'},text='controlled-private')
        return httpx.Response(201,json={'id':VIDEO}) if self.offset==self.file.stat().st_size else httpx.Response(308,headers={'Range':f'bytes=0-{self.offset-1}'})

    def job(self):
        with database() as conn: return conn.execute('SELECT * FROM platform_publications WHERE id=%s',(self.identity,)).fetchone()

    def upload(self):
        with database() as conn: return conn.execute('SELECT * FROM youtube_uploads WHERE publication_id=%s',(self.identity,)).fetchone()

    def due(self):
        with database() as conn: conn.execute("UPDATE youtube_uploads SET available_at=now()-interval '1 second' WHERE publication_id=%s",(self.identity,))

    def run_step(self): jobs.run_upload(self.identity)

    def test_real_rq_worker_persists_exact_upload_then_confirms_private_visibility(self):
        self.assertEqual(self.post(self.start_path).status_code,202)
        worker=WindowsWorker([self.queue],connection=self.redis,name='youtube-controlled-'+uuid4().hex)
        worker.work(burst=True,with_scheduler=False,logging_level='ERROR')
        self.assertEqual(self.upload()['phase'],'PROCESSING')
        self.assertEqual(self.job()['external_id'],VIDEO)
        jobs.recover_uploads(self.queue)
        worker.work(burst=True,with_scheduler=False,logging_level='ERROR')
        self.assertEqual(self.job()['state'],'PUBLISHED')
        self.assertEqual(self.upload()['actual_visibility'],'private')
        body=self.client.get(self.path)
        self.assertEqual(body.status_code,200,body.text)
        self.assertNotIn('controlled-session',body.text);self.assertNotIn('synthetic-private',body.text)
        encrypted=bytes(self.upload()['session_encrypted'])
        self.assertNotIn(b'controlled-session',encrypted)
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)
        self.assertEqual(self.post(self.start_path).json()['state'],'PUBLISHED')
        self.run_step();self.assertEqual(sum(r.method=='POST' for r in self.remote),1)

    def test_partial_timeout_probes_remote_offset_and_resumes_same_session(self):
        self.post(self.start_path);self.failure='partial-timeout';self.run_step()
        self.assertEqual(self.upload()['confirmed_bytes'],0)
        self.assertEqual(self.upload()['phase'],'ACTIVE')
        self.assertEqual(self.upload()['error_code'],'YOUTUBE_NETWORK')
        self.due();self.run_step();self.run_step()
        self.assertEqual(self.job()['state'],'PUBLISHED')
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)
        sends=[r for r in self.remote if r.method=='PUT' and not r.headers['Content-Range'].startswith('bytes */')]
        self.assertTrue(sends[1].headers['Content-Range'].startswith('bytes 256-'))

    def test_lost_final_response_is_reconciled_without_resending_or_new_session(self):
        self.post(self.start_path);self.failure='final-timeout';self.run_step();self.due();self.run_step();self.run_step()
        self.assertEqual(self.job()['state'],'PUBLISHED')
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)
        self.assertEqual(sum(r.method=='PUT' and len(r.content)>0 for r in self.remote),1)

    def test_uncertain_initialization_and_worker_crash_never_initiate_twice(self):
        self.post(self.start_path);self.failure='init-timeout';self.run_step()
        self.assertEqual(self.upload()['phase'],'UNKNOWN');self.assertEqual(self.job()['state'],'FAILED')
        self.assertEqual(self.post(self.start_path).json()['error']['code'],'YOUTUBE_RESULT_UNKNOWN')
        self.run_step();self.assertEqual(len(self.remote),1)
        with database() as conn:
            conn.execute("UPDATE youtube_uploads SET phase='INITIATING' WHERE publication_id=%s",(self.identity,))
            conn.execute("UPDATE platform_publications SET state='QUEUED' WHERE id=%s",(self.identity,))
            conn.execute("UPDATE platform_publications SET state='UPLOADING' WHERE id=%s",(self.identity,))
        self.due();self.run_step();self.assertEqual(self.upload()['phase'],'UNKNOWN');self.assertEqual(len(self.remote),1)

    def test_lost_session_blocks_new_upload_and_manual_retry_preserves_checkpoint(self):
        self.post(self.start_path);self.failure='partial-timeout';self.run_step();self.due();self.failure='session-lost';self.run_step()
        self.assertEqual(self.job()['state'],'FAILED');self.assertEqual(self.upload()['error_code'],'YOUTUBE_SESSION_LOST')
        self.assertEqual(self.post(self.start_path).status_code,202);self.run_step()
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)

    def test_rate_limit_processing_poll_and_backoff_are_durable(self):
        self.post(self.start_path);self.failure='rate-limit';self.run_step()
        self.assertGreater((self.upload()['available_at']-datetime.now(timezone.utc)).total_seconds(),110)
        calls=len(self.remote);self.run_step();self.assertEqual(len(self.remote),calls)
        self.due();self.run_step();self.processed=False;self.run_step()
        self.assertEqual(self.job()['state'],'UPLOADING');self.assertEqual(self.upload()['phase'],'PROCESSING')
        self.assertEqual(self.upload()['actual_visibility'],'private')
        self.due();self.processed=True;self.run_step();self.assertEqual(self.job()['state'],'PUBLISHED')

    def test_duplicate_starts_redelivery_and_connection_change_are_serialized(self):
        with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(lambda _:self.post(self.start_path),range(2)))
        self.assertTrue(all(r.status_code in (202,409) for r in responses))
        self.assertEqual(self.queue.count,1)
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _:self.run_step(),range(2)))
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)
        with database() as conn: conn.execute("UPDATE social_connections SET id=%s WHERE provider='youtube'",(uuid4(),))
        self.run_step();self.assertEqual(self.job()['state'],'FAILED')
        self.assertNotEqual(self.job()['state'],'PUBLISHED')

    def test_disabled_upload_mvp_cost_origin_and_auth_block_before_network(self):
        for name in ['upload_enabled','zero_cost_confirmed']:
            self.config_data['providers']['youtube'][name]=False;self.write_config()
            self.assertEqual(self.post(self.start_path).status_code,409)
            self.config_data['providers']['youtube'][name]=True;self.write_config()
        self.config_data['video_mvp_accepted']=False;self.write_config();self.assertEqual(self.post(self.start_path).status_code,409)
        self.config_data['video_mvp_accepted']=True;self.write_config()
        self.assertEqual(self.client.post(self.start_path,headers={'Origin':'https://other.invalid'}).status_code,403)
        self.delete('/api/media-session');self.assertEqual(self.post(self.start_path).status_code,401)
        self.assertIsNone(self.upload());self.assertFalse(self.remote)

    def test_wrong_project_corrupt_file_changed_provenance_and_revoked_access_block(self):
        wrong=self.start_path.replace(str(self.project),str(uuid4()))
        self.assertEqual(self.post(wrong).status_code,404)
        data=self.file.read_bytes();self.file.write_bytes(b'corrupt')
        self.assertEqual(self.post(self.start_path).json()['error']['code'],'MEDIA_CORRUPT');self.file.write_bytes(data)
        self.post(self.start_path)
        with database() as conn:
            stage=conn.execute("SELECT result FROM production_steps WHERE production_run_id=%s AND name='SCENES'",(self.run,)).fetchone()['result']
            stage['sources'][0]['creator']='Changed';conn.execute("UPDATE production_steps SET result=%s WHERE production_run_id=%s AND name='SCENES'",(Jsonb(stage),self.run))
        self.run_step();self.assertEqual(self.job()['state'],'FAILED');self.assertFalse(self.remote)

    def test_mismatched_remote_account_or_visibility_never_reports_publication_success(self):
        self.post(self.start_path);self.run_step();self.remote_channel='foreign-channel';self.run_step()
        self.assertEqual(self.job()['state'],'FAILED');self.assertEqual(self.upload()['error_code'],'YOUTUBE_STATUS_INVALID')
        self.remote_channel=self.channel_id;self.visibility='public';self.post(self.start_path);self.due();self.run_step()
        self.assertEqual(self.job()['state'],'FAILED');self.assertEqual(self.upload()['error_code'],'YOUTUBE_VISIBILITY_CHANGED')
        self.assertEqual(self.upload()['actual_visibility'],'public')
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)

    def test_stale_queue_delivery_and_database_guards_preserve_consent(self):
        self.post(self.start_path)
        with database() as conn:
            with self.assertRaises(psycopg.Error),conn.transaction(): conn.execute("UPDATE youtube_uploads SET size_bytes=size_bytes+1 WHERE publication_id=%s",(self.identity,))
            with self.assertRaises(psycopg.Error),conn.transaction(): conn.execute("UPDATE platform_publications SET state='QUEUED' WHERE id=%s",(self.identity,))
            with self.assertRaises(psycopg.Error),conn.transaction(): conn.execute((MIGRATIONS/'0009_youtube_upload.down.sql').read_text())
            conn.execute('UPDATE publication_releases SET invalidated_at=now() WHERE id=%s',(self.job()['release_id'],))
        self.run_step();self.assertEqual(self.job()['state'],'FAILED');self.assertFalse(self.remote)

    def test_repeated_network_failures_exhaust_retries_and_preserve_session(self):
        self.post(self.start_path);self.failure='partial-timeout';self.run_step()
        def unavailable(request):
            raise httpx.ReadTimeout('controlled-private',request=request)
        with patch('app.youtube_upload.http_client',side_effect=lambda:httpx.Client(transport=httpx.MockTransport(unavailable))):
            for _ in range(5): self.due();self.run_step()
        self.assertEqual(self.job()['state'],'FAILED');self.assertEqual(self.upload()['retries'],5)
        self.assertEqual(self.upload()['phase'],'ACTIVE')

    def test_disconnect_prevents_redelivery_before_any_more_remote_requests(self):
        self.post(self.start_path);self.failure='partial-timeout';self.run_step();self.due()
        calls=len(self.remote);self.delete('/api/connections/youtube');self.run_step()
        self.assertEqual(self.job()['state'],'FAILED');self.assertEqual(len(self.remote),calls)

    def test_old_profile_requires_resave_and_fresh_consent_after_adapter_upgrade(self):
        from app.publication_contract import profile
        def old_profile(*args):
            value=profile(*args);value['snippet'].pop('categoryId',None);return value
        with database() as conn:
            conn.execute('DELETE FROM platform_publications');conn.execute('DELETE FROM publication_releases');conn.execute('DELETE FROM publication_drafts')
        with patch('app.publication_api.profile',side_effect=old_profile):
            self.save();self.assertEqual(self.release().status_code,201)
        state=self.client.get(self.path).json();self.assertIsNone(state['release_id'])
        self.assertEqual(self.save(1).json()['revision'],2)
        self.assertEqual(self.release(2).status_code,201)

    def test_active_checkpoint_survives_process_interruption_before_final_db_commit(self):
        self.post(self.start_path)
        original=jobs.checkpoint
        def interrupted(conn,identity,reply,size):
            if reply[0]==201: raise SystemExit('Controlled worker interruption after YouTube accepted bytes')
            return original(conn,identity,reply,size)
        with patch('app.youtube_jobs.checkpoint',side_effect=interrupted):
            with self.assertRaises(SystemExit): self.run_step()
        self.assertEqual(self.upload()['phase'],'ACTIVE');self.assertEqual(self.job()['state'],'UPLOADING')
        self.run_step();self.run_step()
        self.assertEqual(self.job()['state'],'PUBLISHED')
        self.assertEqual(sum(r.method=='POST' for r in self.remote),1)
        self.assertEqual(sum(r.method=='PUT' and bool(r.content) for r in self.remote),1)

    def test_migration_roundtrip_without_uploads_preserves_version_contract(self):
        with database() as conn: conn.execute((MIGRATIONS/'0009_youtube_upload.down.sql').read_text())
        migrate()
        with database() as conn:
            self.assertEqual([r['version'] for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version')],list(range(1,10)))

    def test_large_valid_mp4_uploads_in_bounded_chunks_with_verified_progress(self):
        import subprocess,shutil
        subprocess.run([shutil.which('ffprobe'),'-v','error',str(self.file)],check=True)
        self.post(self.start_path);self.run_step();self.assertEqual(self.upload()['confirmed_bytes'],yt.CHUNK)
        self.assertEqual(self.upload()['phase'],'ACTIVE')
        self.run_step();self.run_step();self.assertEqual(self.job()['state'],'PUBLISHED')
        sends=[r for r in self.remote if r.method=='PUT' and r.content]
        self.assertEqual([len(r.content) for r in sends],[yt.CHUNK,700000])
