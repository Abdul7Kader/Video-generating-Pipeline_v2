"""Real DB/Redis/file verification; synthetic consent and creator responses."""
from concurrent.futures import ThreadPoolExecutor
import json,os,shutil,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
import httpx,psycopg
from psycopg.types.json import Jsonb
from app import test_social_integration as social_tests
from app.database import database
from app.media import checksum
from app.media_gateway import MediaGateway
from app.storage_settings import private_write,initialize_store
from app.social_providers import CREATOR
from app.migrate import MIGRATIONS


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL'),'isolated services required')
class PublicationIntegrationTest(unittest.TestCase):
    setUpClass=classmethod(social_tests.SocialIntegrationTest.setUpClass.__func__)
    tearDownClass=classmethod(social_tests.SocialIntegrationTest.tearDownClass.__func__)
    write_config=social_tests.SocialIntegrationTest.write_config
    login=social_tests.SocialIntegrationTest.login
    post=social_tests.SocialIntegrationTest.post
    delete=social_tests.SocialIntegrationTest.delete
    begin=social_tests.SocialIntegrationTest.begin
    callback=social_tests.SocialIntegrationTest.callback
    connected=social_tests.SocialIntegrationTest.connected

    def provider(self,request):
        if str(request.url)==CREATOR:
            self.calls.append(request)
            return httpx.Response(200,json={'error':{'code':'ok'},'data':dict(privacy_level_options=self.privacy,creator_nickname='Controlled TikTok creator',
                max_video_post_duration_sec=self.duration_limit,comment_disabled=True,duet_disabled=True,stitch_disabled=True)})
        return social_tests.SocialIntegrationTest.provider(self,request)

    def setUp(self):
        social_tests.SocialIntegrationTest.setUp(self)
        self.config_data['providers']['tiktok']['public_creator_app_confirmed']=True
        self.write_config()
        self.privacy=['SELF_ONLY'];self.duration_limit=300
        with database() as conn: conn.execute('TRUNCATE projects CASCADE')
        root=Path(self.folder.name)/'media';root.mkdir()
        config=Path(self.folder.name)/'worker.json'
        private_write(config,dict(MEDIA_ROOT=str(root),DATABASE_URL=os.environ['DATABASE_URL'],REDIS_URL=os.environ['REDIS_URL']))
        env=patch.dict(os.environ,{'WORKER_CONFIG_PATH':str(config),'MEDIA_ROOT':str(root)})
        env.start();self.addCleanup(env.stop);initialize_store()
        self.gateway=MediaGateway().start();self.addCleanup(self.gateway.close)
        self.file=root/'master.mp4'
        subprocess.run([shutil.which('ffmpeg'),'-v','error','-nostdin','-y','-f','lavfi','-i','color=blue:s=720x1280:r=24:d=1',
            '-c:v','libx264','-preset','ultrafast',str(self.file)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.sha=checksum(self.file)
        with database() as conn:
            def insert(query,params=()): return conn.execute(query+' RETURNING id',params).fetchone()['id']
            self.project=insert("INSERT INTO projects(idea,mode,media_type) VALUES('Controlled release test','LOKAL','STOCK_VIDEO')")
            self.version=insert("INSERT INTO script_versions(project_id,version,title,narration) VALUES(%s,1,'Garten','Text')",(self.project,))
            sources=[]
            for n in range(1,7):
                conn.execute("INSERT INTO scenes(project_id,script_version_id,position,narration,visual_description,media_type,pexels_query) VALUES(%s,%s,%s,'Text','Bild','STOCK_VIDEO','flower')",(self.project,self.version,n))
                sources.append(dict(scene_position=n,artifact_key=f'scene_{n}',media_type='STOCK_VIDEO',video_id=n,file_id=n,query='flower',
                    video_page=f'https://www.pexels.com/video/{n}/',creator='Controlled fixture',creator_page='https://www.pexels.com/@fixture/',
                    license_url='https://www.pexels.com/license/',scene_duration_seconds=5,duration_seconds=5,width=720,height=1280,fps=24))
            approval=insert("INSERT INTO approvals(project_id,kind,script_version_id) VALUES(%s,'SCRIPT',%s)",(self.project,self.version))
            self.run=insert('INSERT INTO production_runs(project_id,script_version_id,script_approval_id) VALUES(%s,%s,%s)',(self.project,self.version,approval))
            conn.execute("UPDATE production_runs SET state='RUNNING' WHERE id=%s",(self.run,))
            self.artifact=insert("INSERT INTO artifacts(project_id,production_run_id,kind,media_type,storage_path,checksum_sha256) VALUES(%s,%s,'FINAL','FINAL_VIDEO','master.mp4',%s)",(self.project,self.run,self.sha))
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps(dict(project_id=str(self.project),run_id=str(self.run),script_version=1,
                final=dict(storage_path='master.mp4',checksum_sha256=self.sha),encoding=dict(size_bytes=self.file.stat().st_size))))
            for position,name,result in [(1,'SCENES',{'sources':sources}),(4,'ENCODING',{'encoding':{'duration_seconds':1}}),
                (5,'STORAGE',{'storage':dict(manifest_path='manifest.json',manifest_sha256=checksum(manifest))})]:
                conn.execute("INSERT INTO production_steps(production_run_id,position,name,state,timeout_seconds,result) VALUES(%s,%s,%s,'COMPLETED',60,%s)",(self.run,position,name,Jsonb(result)))
            conn.execute("UPDATE production_runs SET state='COMPLETED' WHERE id=%s",(self.run,))
            # This one negative fixture intentionally starts without content
            # approval; database protection remains enabled throughout.
            if self._testMethodName!='test_rollback_refuses_discarding_drafts_and_video_approval_is_required':
                conn.execute("INSERT INTO approvals(project_id,kind,artifact_id,checksum_sha256) VALUES(%s,'VIDEO',%s,%s)",(self.project,self.artifact,self.sha))
        self.path=f'/api/projects/{self.project}/videos/{self.artifact}/publication'
        self.metadata=dict(title='Garten',description='Ein ruhiger Tag',made_for_kids=False,synthetic_media=False,
            paid_partnership=False,own_brand=False,tiktok_music_confirmed=True,targets={'youtube':{'visibility':'private'}})

    def save(self,revision=0,metadata=None):
        return self.client.put(self.path,json=dict(expected_revision=revision,checksum_sha256=self.sha,metadata=metadata or self.metadata),headers={'Origin':self.config_data['origin']})

    def release(self,revision=1,**changes):
        body=dict(expected_revision=revision,checksum_sha256=self.sha,reviewed_metadata=True,reviewed_sources=True,consent_to_publish=True)
        body.update(changes)
        return self.client.post(self.path+'/approval',json=body,headers={'Origin':self.config_data['origin']})

    def test_two_targets_concurrent_repeats_create_one_job_each_with_exact_profiles(self):
        self.connected();self.connected('tiktok')
        self.metadata['targets']['tiktok']={'visibility':'SELF_ONLY'}
        saved=self.save();self.assertEqual(saved.status_code,200,saved.text)
        self.assertNotIn('synthetic-private',saved.text)
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:self.release(),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,201])
        self.assertEqual(results[0].json()['release_id'],results[1].json()['release_id'])
        with database() as conn:
            jobs=conn.execute('SELECT * FROM platform_publications').fetchall()
            self.assertEqual(len(jobs),2)
            self.assertTrue(all(j['state']=='QUEUED' and j['external_id'] is None for j in jobs))
            youtube=next(j for j in jobs if j['platform']=='YOUTUBE')
            self.assertIn('Pexels',youtube['snapshot']['profile']['snippet']['description'])
            self.assertEqual(youtube['snapshot']['account_id'],'synthetic-channel')
        self.assertFalse(results[0].json()['upload_available'])

    def test_draft_edit_invalidates_release_and_queued_jobs_then_new_revision_is_required(self):
        self.connected();self.save();self.assertEqual(self.release().status_code,201)
        same=self.save(1);self.assertEqual(same.json()['revision'],1)
        self.metadata['title']='Neuer Titel'
        changed=self.save(1);self.assertEqual(changed.json()['revision'],2)
        self.assertIsNone(changed.json()['release_id']);self.assertFalse(changed.json()['jobs'])
        self.assertEqual(self.release().status_code,409)
        self.assertEqual(self.release(2).status_code,201)
        self.assertEqual(self.save(1).status_code,409)

    def test_real_mp4_corruption_and_wrong_checksum_prevent_any_job(self):
        self.connected();self.save()
        self.assertEqual(self.release(checksum_sha256='b'*64).status_code,409)
        self.file.write_bytes(b'corrupt')
        self.assertEqual(self.release().json()['error']['code'],'MEDIA_CORRUPT')
        self.assertEqual(self.client.get(self.path).status_code,409)
        with database() as conn: self.assertEqual(conn.execute('SELECT count(*) AS n FROM platform_publications').fetchone()['n'],0)

    def test_auth_origin_missing_connection_scopes_mvp_and_cost_are_server_gates(self):
        self.save();self.assertEqual(self.release().status_code,409)
        self.connected()
        self.assertEqual(self.client.post(self.path+'/approval',json={},headers={'Origin':'https://other.invalid'}).status_code,422)
        body=dict(expected_revision=1,checksum_sha256=self.sha,reviewed_metadata=True,reviewed_sources=True,consent_to_publish=True)
        self.assertEqual(self.client.post(self.path+'/approval',json=body,headers={'Origin':'https://other.invalid'}).status_code,403)
        self.config_data['video_mvp_accepted']=False;self.write_config();self.assertEqual(self.release().status_code,409)
        self.config_data['video_mvp_accepted']=True;self.config_data['providers']['youtube']['zero_cost_confirmed']=False;self.write_config()
        self.assertEqual(self.release().status_code,409)
        self.config_data['providers']['youtube']['zero_cost_confirmed']=True;self.write_config()
        with database() as conn: conn.execute("UPDATE social_connections SET scopes='[]' WHERE provider='youtube'")
        self.assertEqual(self.release().status_code,409)
        self.delete('/api/media-session');self.assertEqual(self.client.get(self.path).status_code,401)
        self.assertEqual(self.release().status_code,401)

    def test_new_script_and_changed_provenance_require_new_review(self):
        self.connected();self.save()
        with database() as conn:
            stage=conn.execute("SELECT result FROM production_steps WHERE production_run_id=%s AND name='SCENES'",(self.run,)).fetchone()['result']
            stage['sources'][0]['creator']='Changed source'
            conn.execute("UPDATE production_steps SET result=%s WHERE production_run_id=%s AND name='SCENES'",(Jsonb(stage),self.run))
        self.assertEqual(self.release().status_code,409)
        self.assertEqual(self.save(1).json()['revision'],2)
        with database() as conn: conn.execute("INSERT INTO script_versions(project_id,version,title,narration) VALUES(%s,2,'Neu','Text')",(self.project,))
        self.assertEqual(self.release(2).json()['error']['code'],'VIDEO_VERSION_OUTDATED')

    def test_reconnected_different_account_requires_new_snapshot_even_with_same_metadata(self):
        self.connected();self.save();self.release()
        revision=1
        for channel in ('different-channel','different-channel'):
            # Both switching accounts and reconnecting the same account end
            # the previous publication consent; token refresh does not.
            self.delete('/api/connections/youtube');self.channel_id=channel;self.connected()
            self.assertIsNone(self.client.get(self.path).json()['release_id'])
            self.assertEqual(self.release(revision).status_code,409)
            self.assertEqual(self.save(revision).json()['revision'],revision+1)
            revision+=1
            self.assertEqual(self.release(revision).status_code,201)

    def test_started_job_metadata_is_frozen_and_database_blocks_snapshot_tampering(self):
        self.connected();self.save();self.release()
        with database() as conn:
            with self.assertRaises(psycopg.Error),conn.transaction(): conn.execute("UPDATE platform_publications SET snapshot='{}',state='UPLOADING'")
            conn.execute("UPDATE platform_publications SET state='UPLOADING'")
        self.metadata['title']='Change after start'
        self.assertEqual(self.save(1).json()['error']['code'],'PUBLICATION_STARTED')

    def test_private_only_and_live_creator_options_are_checked_before_release(self):
        self.connected('tiktok');self.metadata['targets']={'tiktok':{'visibility':'SELF_ONLY'}}
        options=self.post(self.path+'/options/tiktok');self.assertEqual(options.json()['choices'],['SELF_ONLY'])
        self.save();self.privacy=['MUTUAL_FOLLOW_FRIENDS']
        self.assertEqual(self.release().json()['error']['code'],'PUBLICATION_CREATOR_LIMIT')
        self.metadata['targets']={'tiktok':{'visibility':'PUBLIC_TO_EVERYONE'}}
        self.save(1);self.assertEqual(self.release(2).json()['error']['code'],'PUBLICATION_PRIVATE_ONLY')

    def test_tiktok_music_and_interaction_changes_require_explicit_valid_choices(self):
        self.connected('tiktok');self.metadata['targets']={'tiktok':{'visibility':'SELF_ONLY'}}
        self.metadata['tiktok_music_confirmed']=False;self.save()
        self.assertEqual(self.release().json()['error']['code'],'PUBLICATION_TIKTOK_CONSENT')
        self.metadata.update(tiktok_music_confirmed=True,allow_comments=True);self.save(1)
        self.assertEqual(self.release(2).json()['error']['code'],'PUBLICATION_CREATOR_LIMIT')

    def test_private_utility_tiktok_is_blocked_before_creator_request(self):
        self.connected('tiktok');self.metadata['targets']={'tiktok':{'visibility':'SELF_ONLY'}};self.save()
        self.config_data['providers']['tiktok']['public_creator_app_confirmed']=False;self.write_config()
        count=len(self.calls)
        self.assertEqual(self.post(self.path+'/options/tiktok').json()['error']['code'],'PUBLICATION_TIKTOK_USE_BLOCKED')
        self.assertEqual(self.release().json()['error']['code'],'PUBLICATION_TIKTOK_USE_BLOCKED')
        self.assertEqual(len(self.calls),count)

    def test_rollback_refuses_discarding_drafts_and_video_approval_is_required(self):
        self.connected();self.save()
        with database() as conn:
            with self.assertRaises(psycopg.Error),conn.transaction(): conn.execute((MIGRATIONS/'0008_publication_release.down.sql').read_text())
        self.assertEqual(self.release().json()['error']['code'],'VIDEO_APPROVAL_REQUIRED')


if __name__=='__main__': unittest.main()
