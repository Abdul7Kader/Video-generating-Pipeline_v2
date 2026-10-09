"""Real PostgreSQL/Redis/HTTP lifecycle with synthetic provider responses."""
import base64
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from app.main import app
from app.database import database
from app.migrate import migrate
from app.media_access import COOKIE, legacy_password_hash
from app.social_config import load_config
from app.social_crypto import unseal
from app.social_api import binding, lock
from app.social_providers import ACCOUNT, TOKEN, REVOKE, SCOPES
from app.storage_settings import private_write


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL'),'isolated PostgreSQL and Redis required')
class SocialIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_url=os.environ['DATABASE_URL']
        cls.schema='social_test_'+uuid4().hex
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        separator='&' if '?' in cls.original_url else '?'
        os.environ['DATABASE_URL']=cls.original_url+separator+'options=-csearch_path%3D'+cls.schema
        migrate()
        cls.password=secrets.token_urlsafe(32)

    @classmethod
    def tearDownClass(cls):
        os.environ['DATABASE_URL']=cls.original_url
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name)
        self.key=secrets.token_bytes(32)
        private_write(root/'key.json',{'key':base64.b64encode(self.key).decode()})
        self.config_path=root/'config.json'
        self.config_data=dict(origin='http://127.0.0.1:4177',video_mvp_accepted=True,providers={
            p:dict(client_id='synthetic-client-'+p,client_secret='synthetic-secret',enabled=True,
                   zero_cost_confirmed=True,checked_at=datetime.now(timezone.utc).isoformat(),
                   review_status='TEST_ONLY',account_reference='synthetic-test-account') for p in ('youtube','tiktok')})
        self.write_config()
        env=patch.dict(os.environ,{'SOCIAL_CONFIG_PATH':str(self.config_path),'SOCIAL_TOKEN_KEY_PATH':str(root/'key.json'),
            'MEDIA_RPC_NAMESPACE':'social-test:'+self.schema})
        env.start();self.addCleanup(env.stop)
        with database() as conn:
            conn.execute('DELETE FROM social_oauth_attempts');conn.execute('DELETE FROM social_connections')
        self.client=TestClient(app,base_url=self.config_data['origin'])
        self.addCleanup(self.client.close)
        self.login()
        self.calls=[];self.channel_id='synthetic-channel';self.partial=False;self.revoke_fails=False;self.token_fails=False;self.account_fails=False
        mock=patch('app.social_providers.http_client',side_effect=lambda:httpx.Client(transport=httpx.MockTransport(self.provider)))
        mock.start();self.addCleanup(mock.stop)

    def write_config(self): private_write(self.config_path,self.config_data)

    def login(self, password=None):
        response=self.client.post('/api/media-session',json={'password':password or self.password},headers={'Origin':self.config_data['origin']})
        self.assertEqual(response.status_code,200,response.text)

    def post(self,path): return self.client.post(path,headers={'Origin':self.config_data['origin']})
    def delete(self,path): return self.client.delete(path,headers={'Origin':self.config_data['origin']})

    def provider(self, request):
        self.calls.append(request)
        provider='tiktok' if request.url.host=='open.tiktokapis.com' else 'youtube'
        if str(request.url)==TOKEN[provider]:
            if self.token_fails: return httpx.Response(400,json={'error':'invalid_grant','error_description':'synthetic-private-token'})
            form=parse_qs(request.content.decode())
            value=dict(access_token='synthetic-private-access',expires_in=3600,token_type='Bearer',
                scope=(',' if provider=='tiktok' else ' ').join(SCOPES[provider][:-1] if self.partial else SCOPES[provider]))
            if provider=='tiktok': value.update(open_id='synthetic-tiktok',refresh_expires_in=86400)
            if form['grant_type']==['authorization_code']: value['refresh_token']='synthetic-private-refresh'
            elif provider=='tiktok': value['refresh_token']='synthetic-private-rotated-refresh'
            return httpx.Response(200,json=value)
        if str(request.url).startswith(ACCOUNT[provider]):
            if self.account_fails: return httpx.Response(403,json={'error':'synthetic-permission-error'})
            data={'items':[{'id':self.channel_id,'snippet':{'title':'Synthetic channel'}}]} if provider=='youtube' else {
                'data':{'user':{'open_id':'synthetic-tiktok','display_name':'Synthetic TikTok'}},'error':{'code':'ok'}}
            return httpx.Response(200,json=data)
        if str(request.url)==REVOKE[provider]: return httpx.Response(503 if self.revoke_fails else 200,json={})
        self.fail('Unexpected external endpoint')

    def begin(self,provider='youtube'):
        response=self.post(f'/api/connections/{provider}/authorize')
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=lax',response.headers['set-cookie'])
        return parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]

    def callback(self,provider,state,**params):
        return self.client.get(f'/api/connections/{provider}/callback?'+urlencode(dict(state=state,code='synthetic-code',**params)),follow_redirects=False)

    def connected(self,provider='youtube'):
        response=self.callback(provider,self.begin(provider))
        self.assertEqual(response.status_code,303,response.text)
        self.assertIn('connection_result=CONNECTED',response.headers['location'])
        self.assertEqual(response.headers['referrer-policy'],'no-referrer')
        self.assertNotIn('synthetic-code',response.headers['location'])

    def row(self,provider='youtube'):
        with database() as conn:
            return conn.execute('SELECT * FROM social_connections WHERE provider=%s',(provider,)).fetchone()

    def tokens(self,provider='youtube'):
        row=self.row(provider)
        return unseal(self.key,binding(provider,row['id'],row['config_fingerprint']),row['tokens_encrypted'])

    def test_youtube_complete_persistent_encrypted_lifecycle_and_idempotent_disconnect(self):
        state=self.begin();response=self.callback('youtube',state)
        self.assertEqual(response.status_code,303)
        replay=self.callback('youtube',state);self.assertEqual(replay.status_code,400)
        row=self.row();self.assertEqual(row['state'],'CONNECTED')
        self.assertNotIn(b'synthetic-private',bytes(row['tokens_encrypted']))
        listing=self.client.get('/api/connections')
        self.assertEqual(listing.status_code,200,listing.text)
        self.assertNotIn('synthetic-private',listing.text);self.assertNotIn('synthetic-secret',listing.text)
        self.assertEqual(listing.headers['cache-control'],'no-store')
        self.assertEqual(self.post('/api/connections/youtube/refresh').status_code,200)
        self.assertEqual(self.tokens()['refresh_token'],'synthetic-private-refresh')
        self.assertEqual(self.delete('/api/connections/youtube').status_code,200)
        row=self.row();self.assertIsNone(row['tokens_encrypted']);self.assertIsNone(row['account_title'])
        count=len(self.calls)
        self.assertEqual(self.delete('/api/connections/youtube').status_code,200)
        self.assertEqual(len(self.calls),count)

    def test_tiktok_cross_site_callback_refresh_rotation_and_partial_permissions(self):
        state=self.begin('tiktok');self.partial=True
        self.client.cookies.delete(COOKIE)
        result=self.callback('tiktok',state)
        self.assertEqual(result.status_code,303,result.text)
        self.assertEqual(self.row('tiktok')['state'],'LIMITED')
        self.login()
        status=self.client.get('/api/connections').json()['connections'][1]
        self.assertTrue(any('video.publish' in problem for problem in status['problems']))
        self.partial=False
        self.assertEqual(self.post('/api/connections/tiktok/refresh').status_code,200)
        self.assertEqual(self.tokens('tiktok')['refresh_token'],'synthetic-private-rotated-refresh')
        self.assertEqual(self.row('tiktok')['state'],'CONNECTED')

    def test_access_origin_mvp_cost_and_unimplemented_platforms_block_before_network(self):
        with TestClient(app,base_url=self.config_data['origin']) as outsider:
            self.assertEqual(outsider.get('/api/connections').status_code,401)
            self.assertEqual(outsider.post('/api/connections/youtube/authorize').status_code,401)
        self.assertEqual(self.client.post('/api/connections/youtube/authorize',headers={'Origin':'https://attacker.invalid'}).status_code,403)
        for platform in ('x','facebook','instagram'):
            self.assertEqual(self.post(f'/api/connections/{platform}/authorize').status_code,409)
        self.config_data['video_mvp_accepted']=False;self.write_config()
        self.assertEqual(self.post('/api/connections/youtube/authorize').status_code,409)
        self.config_data['video_mvp_accepted']=True
        self.config_data['providers']['youtube']['zero_cost_confirmed']=False;self.write_config()
        self.assertEqual(self.post('/api/connections/youtube/authorize').status_code,409)
        self.assertFalse(self.calls)

    def test_wrong_cookie_wrong_provider_duplicate_parameters_expiry_and_logout(self):
        state=self.begin()
        with TestClient(app,base_url=self.config_data['origin']) as outsider:
            self.assertEqual(outsider.get('/api/connections/youtube/callback?state='+state+'&code=synthetic-code').status_code,400)
        self.assertEqual(self.callback('tiktok',state).status_code,400)
        duplicate=self.client.get('/api/connections/youtube/callback?state='+state+'&state=other&code=synthetic-code',follow_redirects=False)
        self.assertEqual(duplicate.status_code,400)
        with database() as conn: conn.execute("UPDATE social_oauth_attempts SET expires_at=now()-interval '1 second'")
        self.assertEqual(self.callback('youtube',state).status_code,400)
        state=self.begin()
        self.assertEqual(self.delete('/api/media-session').status_code,200)
        self.assertEqual(self.callback('youtube',state).status_code,400)
        self.assertFalse(self.calls)

    def test_failed_exchange_consumes_state_and_does_not_expose_provider_error(self):
        state=self.begin();self.token_fails=True
        response=self.callback('youtube',state)
        self.assertEqual(response.status_code,303,response.text)
        self.assertNotIn('synthetic-private',response.text+response.headers['location'])
        self.assertEqual(self.callback('youtube',state).status_code,400)
        self.assertIsNone(self.row())
        self.assertEqual(len(self.calls),1)

    def test_revocation_failure_preserves_encrypted_tokens_then_retry_works_despite_cost_gate(self):
        self.connected();self.revoke_fails=True
        self.assertEqual(self.delete('/api/connections/youtube').status_code,503)
        self.assertEqual(self.row()['state'],'REVOKE_FAILED')
        self.assertTrue(self.row()['tokens_encrypted'])
        self.assertEqual(self.post('/api/connections/youtube/refresh').status_code,409)
        self.assertEqual(self.post('/api/connections/youtube/authorize').status_code,409)
        self.config_data['providers']['youtube']['enabled']=False;self.write_config()
        self.revoke_fails=False
        self.assertEqual(self.delete('/api/connections/youtube').status_code,200)
        self.assertIsNone(self.row()['tokens_encrypted'])

    def test_identity_switch_requires_disconnect_and_database_lock_blocks_overlapping_work(self):
        self.connected();original=self.row()
        self.assertEqual(self.post('/api/connections/youtube/authorize').status_code,409)
        self.assertEqual(self.row()['account_id'],original['account_id'])
        self.channel_id='other-channel'
        changed=self.post('/api/connections/youtube/refresh')
        self.assertEqual(changed.status_code,409)
        self.assertEqual(self.row()['state'],'REAUTH_REQUIRED')
        self.assertEqual(self.row()['account_id'],original['account_id'])
        count=len(self.calls)
        with database() as conn:
            lock(conn,'youtube')
            self.assertEqual(self.post('/api/connections/youtube/refresh').status_code,409)
        self.assertEqual(len(self.calls),count)

    def test_failed_account_lookup_retains_unverified_grant_for_explicit_revocation(self):
        state=self.begin();self.account_fails=True
        response=self.callback('youtube',state)
        self.assertEqual(response.status_code,303)
        row=self.row();self.assertEqual(row['state'],'REAUTH_REQUIRED')
        self.assertIsNone(row['account_id']);self.assertTrue(row['tokens_encrypted'])
        self.assertEqual(self.callback('youtube',state).status_code,400)
        self.assertEqual(self.delete('/api/connections/youtube').status_code,200)
        self.assertIsNone(self.row()['tokens_encrypted'])

    def test_logout_during_account_lookup_revokes_durable_candidate_and_state_is_consumed(self):
        for revoke_fails in (False,True):
            with self.subTest(revoke_fails=revoke_fails):
                self.login();self.revoke_fails=revoke_fails
                state=self.begin()
                original=self.provider
                def during_lookup(request):
                    if str(request.url).startswith(ACCOUNT['youtube']):
                        # Separate connections can see both committed checkpoints.
                        with database() as conn:
                            self.assertTrue(conn.execute('SELECT consumed FROM social_oauth_attempts').fetchone()['consumed'])
                        self.assertEqual(self.row()['state'],'REAUTH_REQUIRED')
                        self.assertTrue(self.row()['tokens_encrypted'])
                        self.assertEqual(self.delete('/api/media-session').status_code,200)
                    return original(request)
                with patch('app.social_providers.http_client',side_effect=lambda:httpx.Client(transport=httpx.MockTransport(during_lookup))):
                    result=self.callback('youtube',state)
                self.assertIn('SOCIAL_STATE_INVALID',result.headers['location'])
                self.assertEqual(self.callback('youtube',state).status_code,400)
                self.assertEqual(self.row()['state'],'REVOKE_FAILED' if revoke_fails else 'DISCONNECTED')
                self.assertEqual(bool(self.row()['tokens_encrypted']),revoke_fails)
                if revoke_fails:
                    self.login();self.revoke_fails=False
                    self.assertEqual(self.delete('/api/connections/youtube').status_code,200)

    def test_rotated_refresh_survives_failed_account_lookup_and_remains_revocable(self):
        self.connected('tiktok');self.account_fails=True
        response=self.post('/api/connections/tiktok/refresh')
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.row('tiktok')['state'],'REAUTH_REQUIRED')
        self.assertEqual(self.tokens('tiktok')['refresh_token'],'synthetic-private-rotated-refresh')
        self.assertEqual(self.delete('/api/connections/tiktok').status_code,200)
        self.assertIsNone(self.row('tiktok')['tokens_encrypted'])

    def test_legacy_password_upgrades_after_success_and_relogin_cancels_pending_oauth(self):
        salt=secrets.token_hex(16)
        encoded=legacy_password_hash(self.password,salt)
        with database() as conn:
            conn.execute('UPDATE media_access SET password_hash=%s,password_salt=%s',(encoded,salt))
        wrong=self.client.post('/api/media-session',json={'password':secrets.token_urlsafe(32)},headers={'Origin':self.config_data['origin']})
        self.assertEqual(wrong.status_code,401)
        with database() as conn:
            self.assertEqual(conn.execute('SELECT password_hash FROM media_access').fetchone()['password_hash'],encoded)
        self.login()
        with database() as conn:
            value=conn.execute('SELECT * FROM media_access').fetchone()
            self.assertTrue(value['password_hash'].startswith('$argon2id$'));self.assertEqual(value['password_salt'],'')
        state=self.begin();self.login()
        self.assertEqual(self.callback('youtube',state).status_code,400)

    def test_migration_rollback_preserves_active_credentials_and_empty_roundtrip_works(self):
        self.connected()
        with self.assertRaises(psycopg.Error): migrate('down')
        self.assertTrue(self.row()['tokens_encrypted'])
        with database() as conn:
            self.assertEqual([r['version'] for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version')],list(range(1,10)))
        self.assertEqual(self.delete('/api/connections/youtube').status_code,200)
        # Migration 6 also refuses to discard the isolated operator login.
        with database() as conn: conn.execute('DELETE FROM media_access')
        migrate('down');migrate('up')
        with database() as conn:
            self.assertEqual([r['version'] for r in conn.execute('SELECT version FROM schema_migrations ORDER BY version')],list(range(1,10)))

    def test_key_loss_recovery_requires_explicit_provider_removal_and_makes_no_remote_claim(self):
        self.connected()
        with patch.dict(os.environ,{'SOCIAL_TOKEN_KEY_PATH':'missing-test-key'}):
            listing=self.client.get('/api/connections').json()['connections'][0]
            self.assertFalse(listing['can_disconnect']);self.assertTrue(listing['can_forget'])
            path='/api/connections/youtube/forget'
            self.assertEqual(self.post(path).status_code,422)
            invalid=self.client.post(path,json={'provider_access_removed':False},headers={'Origin':self.config_data['origin']})
            self.assertEqual(invalid.status_code,422)
            coerced=self.client.post(path,json={'provider_access_removed':1},headers={'Origin':self.config_data['origin']})
            self.assertEqual(coerced.status_code,422)
            count=len(self.calls)
            result=self.client.post(path,json={'provider_access_removed':True},headers={'Origin':self.config_data['origin']})
            self.assertEqual(result.status_code,200,result.text)
            self.assertFalse(result.json()['provider_revoke_verified'])
            self.assertIsNone(self.row()['tokens_encrypted']);self.assertEqual(len(self.calls),count)

    def test_rejected_consent_and_config_change_consume_attempt_without_replacing_connection(self):
        state=self.begin()
        denied=self.callback('youtube',state,error='access_denied',error_description='synthetic-private-detail')
        self.assertIn('SOCIAL_CONSENT_DENIED',denied.headers['location'])
        self.assertNotIn('synthetic-private-detail',denied.headers['location'])
        self.assertEqual(self.callback('youtube',state).status_code,400)
        state=self.begin()
        self.config_data['providers']['youtube']['client_id']='synthetic-other-client';self.write_config()
        response=self.callback('youtube',state)
        self.assertIn('SOCIAL_CONFIG_CHANGED',response.headers['location'])
        self.assertIsNone(self.row());self.assertFalse(self.calls)


if __name__ == '__main__': unittest.main()
