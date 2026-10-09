"""Synthetic OAuth fixtures only; no real account calls or credential data."""
import base64
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from app.social_config import SocialConfig, ProviderConfig, load_config, blockers
from app.social_crypto import seal, unseal
from app.social_providers import authorization_url, exchange, refresh, revoke, account, SocialError
from app.social_providers import Tokens, SCOPES, TOKEN, REVOKE, ACCOUNT, remote


class SocialFunctionsTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.entry = ProviderConfig(client_id='synthetic-client', client_secret='synthetic-secret',
            enabled=True, zero_cost_confirmed=True, checked_at=self.now, review_status='TEST_ONLY',
            account_reference='synthetic-test-account')
        self.config = SocialConfig(origin='http://127.0.0.1:4177', video_mvp_accepted=True,
                                  providers={'youtube':self.entry,'tiktok':self.entry})
        self.key = secrets.token_bytes(32)

    def test_encryption_binds_record_provider_and_client_and_detects_tampering(self):
        value = {'access_token':'synthetic-token'}
        ciphertext = seal(self.key, 'youtube:record:client', value)
        self.assertNotIn(b'synthetic-token', ciphertext)
        self.assertNotEqual(ciphertext, seal(self.key, 'youtube:record:client', value))
        self.assertEqual(unseal(self.key, 'youtube:record:client', ciphertext), value)
        for aad, encrypted in [('tiktok:record:client',ciphertext),
                               ('youtube:other:client',ciphertext),
                               ('youtube:record:client',ciphertext[:-1]+bytes([ciphertext[-1]^1]))]:
            with self.subTest(aad=aad), self.assertRaises(SocialError): unseal(self.key,aad,encrypted)

    def test_cost_review_mvp_and_config_are_independent_gates(self):
        self.assertFalse(blockers('youtube',self.config,self.now))
        for changes in ({'zero_cost_confirmed':False}, {'enabled':False},
                        {'checked_at':self.now-timedelta(days=2)}, {'checked_at':self.now+timedelta(seconds=2)},
                        {'review_status':'UNVERIFIED'}, {'account_reference':''}):
            config=self.config.model_copy(update={'providers':{'youtube':self.entry.model_copy(update=changes)}})
            self.assertTrue(blockers('youtube',config,self.now))
        self.assertTrue(blockers('youtube',self.config.model_copy(update={'video_mvp_accepted':False}),self.now))
        for platform in ('facebook','instagram','x'):
            self.assertTrue(blockers(platform,self.config,self.now))
        with patch.dict(os.environ, {'SOCIAL_CONFIG_PATH':''}): self.assertIsNone(load_config())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json';path.write_text('{broken')
            with patch.dict(os.environ, {'SOCIAL_CONFIG_PATH':str(path)}), self.assertRaises(SocialError): load_config()

    def test_local_redirect_validation_and_provider_specific_pkce(self):
        for origin in ('http://example.com:4177','http://localhost:4177/path',
                       'http://user@localhost:4177','http://localhost:4177?x=1'):
            with self.subTest(origin=origin), self.assertRaises(ValueError): SocialConfig(origin=origin)
        verifier=secrets.token_urlsafe(48)
        google=parse_qs(urlsplit(authorization_url('youtube',self.config,'state',verifier)).query)
        tiktok=parse_qs(urlsplit(authorization_url('tiktok',self.config,'state',verifier)).query)
        import hashlib
        digest=hashlib.sha256(verifier.encode()).digest()
        self.assertEqual(google['code_challenge'],[base64.urlsafe_b64encode(digest).rstrip(b'=').decode()])
        self.assertEqual(tiktok['code_challenge'],[digest.hex()])
        self.assertEqual(tiktok['code_challenge_method'],['S256'])
        self.assertNotIn('synthetic-secret',authorization_url('youtube',self.config,'state',verifier))

    def test_exchange_refresh_rotation_account_and_revocation_use_only_official_endpoints(self):
        for provider in ('youtube','tiktok'):
            calls=[]
            def handle(request):
                calls.append(request)
                if str(request.url).startswith(ACCOUNT[provider]):
                    data={'items':[{'id':'channel','snippet':{'title':'Synthetic channel'}}]} if provider=='youtube' else {
                        'data':{'user':{'open_id':'account','display_name':'Synthetic TikTok'}},'error':{'code':'ok'}}
                    return httpx.Response(200,json=data)
                if str(request.url)==REVOKE[provider]: return httpx.Response(200,json={})
                form=parse_qs(request.content.decode())
                token={'access_token':'synthetic-access','expires_in':3600,'scope':(',' if provider=='tiktok' else ' ').join(SCOPES[provider])}
                token['open_id']='account'
                if form['grant_type']==['authorization_code']: token['refresh_token']='synthetic-first-refresh'
                elif provider=='tiktok': token['refresh_token']='synthetic-rotated-refresh'
                return httpx.Response(200,json=token)
            with httpx.Client(transport=httpx.MockTransport(handle)) as client:
                first=exchange(provider,self.config,'synthetic-code','synthetic-verifier',client)
                renewed=refresh(provider,self.config,first,client)
                self.assertEqual(renewed.refresh_token,'synthetic-rotated-refresh' if provider=='tiktok' else first.refresh_token)
                identity,title=account(provider,renewed,client)
                self.assertEqual(identity,'channel' if provider=='youtube' else 'account')
                revoke(provider,self.config,renewed,client)
            self.assertEqual(len(calls),4)
            for request in calls:
                self.assertEqual(request.url.scheme,'https')
                self.assertNotIn('synthetic-access',str(request.url))
                self.assertNotIn('synthetic-secret',str(request.url))
            code_form=parse_qs(calls[0].content.decode())
            self.assertEqual(code_form['code_verifier'],['synthetic-verifier'])

    def test_remote_rejects_redirects_oversized_bodies_errors_and_arbitrary_urls(self):
        for status, body in [(302,b''),(200,b'x'*262145),(200,b'{bad'),(400,b'{"error_description":"synthetic-token"}')]:
            with self.subTest(status=status), httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(status,content=body))) as client:
                with self.assertRaises(SocialError) as caught: remote(client,'POST',TOKEN['youtube'])
                self.assertNotIn('synthetic-token',str(caught.exception))
        with httpx.Client(transport=httpx.MockTransport(lambda _:self.fail('unexpected network'))) as client:
            with self.assertRaises(SocialError): remote(client,'GET','http://127.0.0.1/private')

    def test_wrong_identity_missing_channel_and_bad_tokens_fail(self):
        token=Tokens(access_token='synthetic-access',refresh_token='synthetic-refresh',expires_in=3600,open_id='expected')
        replies=[('youtube',{'items':[]}),('youtube',{'items':[{},{}]}),
                 ('tiktok',{'data':{'user':{'open_id':'other','display_name':'Unexpected'}}})]
        for provider,data in replies:
            with self.subTest(provider=provider), httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=data))) as client:
                with self.assertRaises(SocialError): account(provider,token,client)
        for value in ({'access_token':'synthetic-access','expires_in':-1},
                      {'access_token':'synthetic-access','expires_in':True}, {'expires_in':3600}):
            with self.subTest(value=value), httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=value))) as client:
                with self.assertRaises(SocialError): exchange('youtube',self.config,'synthetic-code','verifier',client)

    def test_argon2id_salts_password_errors_and_legacy_upgrade_decision(self):
        from app.media_access import password_hash, verify_password, legacy_password_hash, PASSWORDS
        password=secrets.token_urlsafe(32)
        first,second=password_hash(password),password_hash(password)
        self.assertTrue(first.startswith('$argon2id$'))
        self.assertNotEqual(first,second)
        self.assertIn('m=65536,t=3,p=4',first)
        row={'password_hash':first,'password_salt':''}
        self.assertEqual(verify_password(password,row),(True,False))
        self.assertEqual(verify_password(secrets.token_urlsafe(32),row),(False,False))
        salt=secrets.token_hex(16)
        row={'password_hash':legacy_password_hash(password,salt),'password_salt':salt}
        self.assertEqual(verify_password(password,row),(True,True))
        self.assertEqual(verify_password(secrets.token_urlsafe(32),row),(False,False))

    def test_callback_logging_redacts_authorization_code_and_state(self):
        import logging
        from app.social_api import CallbackLogFilter
        record=logging.LogRecord('uvicorn.access',logging.INFO,'',0,'%s %s %s %s %s',
            ('client','GET','/api/connections/youtube/callback?code=synthetic-code&state=synthetic-state','1.1',303),None)
        CallbackLogFilter().filter(record)
        self.assertNotIn('synthetic-code',record.getMessage())
        self.assertNotIn('synthetic-state',record.getMessage())


if __name__ == '__main__': unittest.main()
