"""Real PostgreSQL/Redis API sessions; all Meta responses are synthetic."""
from datetime import datetime,timezone,timedelta
import os,time,unittest
from unittest.mock import patch
import httpx,psycopg
from app import test_social_integration as social_tests
from app import test_meta as meta_tests
from app import meta_providers as meta
from app.database import database
from app.migrate import MIGRATIONS
from app.social_api import lock
from app.publication_api import readiness,eligible
from fastapi import HTTPException


@unittest.skipUnless(os.getenv('DATABASE_URL') and os.getenv('REDIS_URL'),'isolated PostgreSQL and Redis required')
class MetaIntegrationTest(unittest.TestCase):
    setUpClass=classmethod(social_tests.SocialIntegrationTest.setUpClass.__func__)
    tearDownClass=classmethod(social_tests.SocialIntegrationTest.tearDownClass.__func__)
    write_config=social_tests.SocialIntegrationTest.write_config
    login=social_tests.SocialIntegrationTest.login
    post=social_tests.SocialIntegrationTest.post
    delete=social_tests.SocialIntegrationTest.delete
    begin=social_tests.SocialIntegrationTest.begin
    callback=social_tests.SocialIntegrationTest.callback
    connected=social_tests.SocialIntegrationTest.connected
    row=social_tests.SocialIntegrationTest.row
    tokens=social_tests.SocialIntegrationTest.tokens

    def setUp(self):
        social_tests.SocialIntegrationTest.setUp(self)
        meta_tests.MetaFunctionsTest.setUp(self)
        for provider,entry in meta_tests.configuration().providers.items():
            value=entry.model_dump(mode='json');value['client_secret']=entry.client_secret.get_secret_value()
            self.config_data['providers'][provider]=value
        self.write_config()

    def provider(self,request):
        if request.url.host=='graph.facebook.com': return meta_tests.MetaFunctionsTest.handler(self,request)
        return social_tests.SocialIntegrationTest.provider(self,request)

    def status(self,provider):
        return next(c for c in self.client.get('/api/connections').json()['connections'] if c['provider']==provider)

    def test_both_lifecycles_persist_encrypted_identity_without_refresh_token(self):
        for provider,account_id in [('facebook','100'),('instagram','300')]:
            self.connected(provider)
            row=self.row(provider);self.assertEqual(row['state'],'CONNECTED');self.assertEqual(row['account_id'],account_id)
            self.assertNotIn(b'synthetic-',bytes(row['tokens_encrypted']))
            token=self.tokens(provider);self.assertIsNone(token['refresh_token']);self.assertEqual(token['meta_user_id'],'200')
            listed=self.status(provider);self.assertTrue(listed['can_refresh']);self.assertEqual(listed['refresh_label'],'Zugang prüfen')
            self.assertNotIn('synthetic-long',str(listed));self.assertNotIn('synthetic-secret',str(listed))
        self.assertFalse(self.calls[0].url.params.get('code_verifier'))

    def test_shared_revoke_clears_both_grants_and_pending_attempts_once(self):
        self.connected('instagram');self.connected('facebook')
        response=self.delete('/api/connections/instagram');self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(set(response.json()['removed_connections']),{'facebook','instagram'})
        for provider in ('facebook','instagram'): self.assertIsNone(self.row(provider)['tokens_encrypted'])
        count=len(self.calls);self.assertEqual(self.delete('/api/connections/facebook').status_code,200)
        self.assertEqual(len(self.calls),count)

    def test_failed_shared_revoke_blocks_both_until_successful_retry(self):
        self.connected('instagram');self.connected('facebook');self.revoke_success=False
        self.assertEqual(self.delete('/api/connections/instagram').status_code,503)
        for provider in ('instagram','facebook'):
            self.assertEqual(self.row(provider)['state'],'REVOKE_FAILED')
            self.assertFalse(self.status(provider)['can_refresh'])
            self.assertEqual(self.post('/api/connections/'+provider+'/refresh').status_code,409)
        self.revoke_success=True
        self.assertEqual(self.delete('/api/connections/facebook').status_code,200)
        self.assertIsNone(self.row('instagram')['tokens_encrypted'])

    def test_failed_long_exchange_retains_short_grant_for_revocation_and_consumes_state(self):
        state=self.begin('instagram');self.long_fails=True
        result=self.callback('instagram',state)
        self.assertIn('SOCIAL_PROVIDER_UNAVAILABLE',result.headers['location'])
        self.assertEqual(self.row('instagram')['state'],'REAUTH_REQUIRED')
        self.assertEqual(self.tokens('instagram')['access_token'],'synthetic-short')
        self.assertEqual(self.callback('instagram',state).status_code,400)
        self.assertEqual(self.delete('/api/connections/instagram').status_code,200)

    def test_wrong_target_retains_long_grant_without_accepting_first_page(self):
        self.pages_changes={'data':[dict(id='999',name='Wrong Page',tasks=['MANAGE'])]}
        result=self.callback('facebook',self.begin('facebook'))
        self.assertIn('SOCIAL_ACCOUNT_INELIGIBLE',result.headers['location'])
        self.assertIsNone(self.row('facebook')['account_id'])
        self.assertEqual(self.tokens('facebook')['access_token'],'synthetic-long')
        self.assertFalse(self.status('facebook')['can_refresh'])
        self.assertEqual(self.delete('/api/connections/facebook').status_code,200)

    def test_partial_rights_stay_limited_and_review_can_restore_current_rights(self):
        self.permission_missing=True;self.connected('instagram')
        self.assertEqual(self.row('instagram')['state'],'LIMITED')
        self.assertTrue(any('instagram_content_publish' in p for p in self.status('instagram')['problems']))
        expiry=self.row('instagram')['expires_at'];self.permission_missing=False
        response=self.post('/api/connections/instagram/refresh')
        self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['expiration_extended'])
        self.assertEqual(self.row('instagram')['state'],'CONNECTED')
        self.assertEqual(self.row('instagram')['expires_at'],expiry)

    def test_expired_grant_requires_consent_and_never_makes_fake_refresh_call(self):
        self.connected('instagram')
        with database() as conn:
            conn.execute("UPDATE social_connections SET expires_at=now()-interval '1 second' WHERE provider='instagram'")
        count=len(self.calls)
        self.assertEqual(self.post('/api/connections/instagram/refresh').status_code,409)
        self.assertEqual(len(self.calls),count)
        self.assertEqual(self.row('instagram')['state'],'REAUTH_REQUIRED')

    def test_changed_page_or_app_config_blocks_existing_grant_and_old_attempt(self):
        state=self.begin('instagram')
        self.config_data['providers']['instagram']['meta_page_id']='101';self.write_config()
        self.assertIn('SOCIAL_CONFIG_CHANGED',self.callback('instagram',state).headers['location'])
        self.assertFalse(self.calls)
        self.config_data['providers']['instagram']['meta_page_id']='100';self.write_config();self.connected('instagram')
        self.config_data['providers']['instagram']['meta_page_id']='101';self.write_config()
        self.assertFalse(self.status('instagram')['can_disconnect'])
        self.assertEqual(self.post('/api/connections/instagram/refresh').status_code,409)

    def test_meta_changes_share_a_real_database_lock(self):
        with database() as conn:
            lock(conn,'facebook')
            self.assertEqual(self.post('/api/connections/instagram/authorize').status_code,409)
        self.assertEqual(self.post('/api/connections/instagram/authorize').status_code,200)

    def test_shared_revoke_cancels_unfinished_sibling_consent_even_when_revoke_fails(self):
        for success in (True,False):
            with self.subTest(success=success):
                self.revoke_success=True
                if self.row('facebook') and self.row('facebook')['tokens_encrypted']:
                    self.delete('/api/connections/facebook')
                self.connected('facebook');state=self.begin('instagram');self.revoke_success=success
                self.assertEqual(self.delete('/api/connections/facebook').status_code,200 if success else 503)
                self.assertEqual(self.callback('instagram',state).status_code,400)
                if not success:
                    self.assertFalse(self.status('instagram')['can_connect'])
                    self.assertEqual(self.post('/api/connections/instagram/authorize').status_code,409)

    def test_other_meta_user_is_not_cleared_and_changed_account_check_stays_blocked(self):
        self.connected('instagram');self.debug_changes={'user_id':'201'};self.connected('facebook')
        self.assertEqual(self.delete('/api/connections/instagram').status_code,200)
        self.assertEqual(self.row('facebook')['state'],'CONNECTED')
        self.debug_changes={'user_id':'202'}
        self.assertEqual(self.post('/api/connections/facebook/refresh').status_code,409)
        self.assertEqual(self.row('facebook')['state'],'REAUTH_REQUIRED')
        self.assertEqual(self.tokens('facebook')['meta_user_id'],'201')

    def test_logout_during_verification_revokes_both_shared_grants(self):
        self.connected('facebook');state=self.begin('instagram')
        original=self.provider
        def canceled(request):
            if str(request.url).split('?',1)[0]==meta.PAGES:
                self.assertEqual(self.row('instagram')['state'],'REAUTH_REQUIRED')
                self.assertEqual(self.delete('/api/media-session').status_code,200)
            return original(request)
        with patch('app.social_providers.http_client',side_effect=lambda:httpx.Client(transport=httpx.MockTransport(canceled))):
            result=self.callback('instagram',state)
        self.assertIn('SOCIAL_STATE_INVALID',result.headers['location'])
        for provider in ('facebook','instagram'): self.assertIsNone(self.row(provider)['tokens_encrypted'])

    def test_access_origin_cost_and_page_gates_block_before_external_requests(self):
        self.assertEqual(self.client.post('/api/connections/instagram/authorize').status_code,403)
        self.config_data['providers']['instagram']['meta_page_id']='';self.write_config()
        self.assertEqual(self.post('/api/connections/instagram/authorize').status_code,409)
        self.config_data['providers']['instagram']['meta_page_id']='100'
        self.config_data['providers']['instagram']['zero_cost_confirmed']=False;self.write_config()
        self.assertEqual(self.post('/api/connections/instagram/authorize').status_code,409)
        self.assertFalse(self.calls)
        self.assertEqual(self.delete('/api/media-session').status_code,200)
        self.assertEqual(self.post('/api/connections/facebook/authorize').status_code,401)

    def test_connected_meta_is_not_publication_ready_and_cannot_create_upload_options(self):
        self.connected('instagram');self.connected('facebook')
        with database() as conn:
            platforms=readiness(conn)
            for provider in ('facebook','instagram'):
                item=next(p for p in platforms if p['provider']==provider);self.assertFalse(item['ready'])
                self.assertTrue(any('Veröffentlichungsadapter' in p for p in item['problems']))
                with self.assertRaises(HTTPException) as caught: eligible(conn,provider,None)
                self.assertEqual(caught.exception.detail['code'],'PUBLICATION_ADAPTER_UNAVAILABLE')

    def test_migration_preserves_active_and_disconnected_meta_then_empty_roundtrip(self):
        self.connected('instagram')
        for connected in (True,False):
            if not connected: self.delete('/api/connections/instagram')
            with self.assertRaises(psycopg.Error),database() as conn:
                conn.execute((MIGRATIONS/'0010_meta_connections.down.sql').read_text())
        with database() as conn:
            conn.execute("DELETE FROM social_connections WHERE provider IN ('instagram','facebook')")
            conn.execute((MIGRATIONS/'0010_meta_connections.down.sql').read_text())
            self.assertEqual(conn.execute('SELECT max(version) AS n FROM schema_migrations').fetchone()['n'],9)
            conn.execute((MIGRATIONS/'0010_meta_connections.sql').read_text())
            self.assertEqual(conn.execute('SELECT max(version) AS n FROM schema_migrations').fetchone()['n'],10)


if __name__=='__main__': unittest.main()
