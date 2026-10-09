"""Synthetic Meta protocol fixtures; no real identities or platform calls."""
from datetime import datetime,timezone
import logging,time,unittest
from urllib.parse import parse_qs,urlsplit
import httpx
from app import meta_providers as meta
from app import social_providers as providers
from app.social_config import ProviderConfig,SocialConfig,SocialError,blockers


def configuration():
    entry=ProviderConfig(client_id='123',client_secret='synthetic-secret',meta_page_id='100',enabled=True,
        zero_cost_confirmed=True,checked_at=datetime.now(timezone.utc),review_status='TEST_ONLY',account_reference='synthetic')
    return SocialConfig(video_mvp_accepted=True,providers={'facebook':entry,'instagram':entry})


class MetaFunctionsTest(unittest.TestCase):
    def setUp(self):
        self.config=configuration();self.calls=[];self.debug_changes={};self.pages_changes=None
        self.permission_missing=False;self.revoke_success=True;self.long_fails=False
        self.expiry=int(time.time())+86400

    def handler(self,request):
        self.calls.append(request)
        url=str(request.url).split('?',1)[0]
        if url==meta.TOKEN:
            is_long=request.url.params.get('grant_type')=='fb_exchange_token'
            if is_long and self.long_fails: return httpx.Response(503,json={})
            return httpx.Response(200,json=dict(access_token='synthetic-long' if is_long else 'synthetic-short',
                expires_in=86400 if is_long else 3600,token_type='bearer'))
        if url==meta.DEBUG:
            return httpx.Response(200,json={'data':dict(app_id='123',type='USER',is_valid=True,user_id='200',
                expires_at=self.expiry,data_access_expires_at=self.expiry,scopes=sorted(set(providers.SCOPES['facebook']+providers.SCOPES['instagram'])))|self.debug_changes})
        if url==meta.PERMISSIONS:
            if request.method=='DELETE': return httpx.Response(200,json={'success':self.revoke_success})
            return httpx.Response(200,json={'data':[dict(permission=p,status='declined' if self.permission_missing and p=='instagram_content_publish' else 'granted')
                for p in sorted(set(providers.SCOPES['facebook']+providers.SCOPES['instagram']))]})
        if url==meta.PAGES:
            return httpx.Response(200,json=self.pages_changes if self.pages_changes is not None else {'data':[
                dict(id='999',name='Other Page',tasks=['MANAGE']),dict(id='100',name='Synthetic Page',tasks=['CREATE_CONTENT'],
                    instagram_business_account={'id':'300','username':'synthetic_ig'})]})
        self.fail('Unexpected endpoint')

    def token(self,client,provider='instagram'):
        first=providers.exchange(provider,self.config,'synthetic-code','unused-pkce',client)
        self.assertIsNone(first.refresh_token)
        return meta.long_lived(provider,self.config,first,client)

    def test_authorization_uses_exact_callback_scopes_state_and_no_secret_or_fake_pkce(self):
        for provider in ('instagram','facebook'):
            self.assertFalse(blockers(provider,self.config))
            url=providers.authorization_url(provider,self.config,'synthetic-state','unused')
            parts=urlsplit(url);query=parse_qs(parts.query)
            self.assertEqual(parts.hostname,'www.facebook.com')
            self.assertEqual(parts.path,'/'+meta.VERSION+'/dialog/oauth')
            self.assertEqual(query['redirect_uri'],[self.config.callback(provider)])
            self.assertEqual(query['state'],['synthetic-state'])
            self.assertEqual(set(query['scope'][0].split(',')),set(providers.SCOPES[provider]))
            self.assertNotIn('code_challenge',query);self.assertNotIn('synthetic-secret',url)
        for value in ('../../foo','https://evil.example','１２３'):
            with self.assertRaises(ValueError): ProviderConfig(client_id='1',client_secret='synthetic',meta_page_id=value)

    def test_exchange_long_lived_permissions_account_and_revoke(self):
        for provider,expected in [('facebook',('100','Synthetic Page')),('instagram',('300','synthetic_ig'))]:
            with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
                token=self.token(client,provider)
                self.assertEqual(providers.account(provider,token,client,self.config),expected)
                self.assertEqual(token.scopes(provider),sorted(providers.SCOPES[provider]))
                providers.revoke(provider,self.config,token,client)
                self.assertEqual(token.meta_user_id,'200')
        for request in self.calls:
            self.assertEqual(request.url.host,'graph.facebook.com');self.assertEqual(request.url.scheme,'https')
            if str(request.url).split('?',1)[0] in (meta.PAGES,meta.PERMISSIONS):
                self.assertIn('appsecret_proof',request.url.params)
                self.assertNotIn('synthetic-long',str(request.url));self.assertNotIn('synthetic-secret',str(request.url))

    def test_wrong_app_user_type_expiration_or_data_access_fail_closed(self):
        for changes in ({'app_id':'other'},{'type':'PAGE'},{'is_valid':False},{'expires_at':True},
                        {'expires_at':0},{'expires_at':int(time.time())-1},{'data_access_expires_at':int(time.time())-1},
                        {'user_id':'bad'},{'scopes':None}):
            self.debug_changes=changes
            with self.subTest(changes=changes),httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
                with self.assertRaises(SocialError): providers.account('instagram',self.token(client),client,self.config)

    def test_target_is_never_first_page_personal_account_or_page_without_content_rights(self):
        for pages in ({'data':[]},{'data':[{'id':'999'}]},
                      {'data':[{'id':'100','name':'Page','tasks':['ANALYZE']}]},
                      {'data':[{'id':'100','name':'Page','tasks':['MANAGE']}]},
                      {'data':[{'id':'100'},{'id':'100'}]}):
            self.pages_changes=pages
            with self.subTest(pages=pages),httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
                with self.assertRaises(SocialError): providers.account('instagram',self.token(client),client,self.config)

    def test_partial_permission_is_recorded_without_inventing_grant(self):
        self.permission_missing=True
        with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
            token=self.token(client);providers.account('instagram',token,client,self.config)
        self.assertNotIn('instagram_content_publish',token.scopes('instagram'))

    def test_token_check_does_not_exchange_or_extend_and_detects_user_change(self):
        with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
            token=self.token(client);providers.account('instagram',token,client,self.config)
            original=token.meta_expires_at;count=len(self.calls)
            checked=providers.refresh('instagram',self.config,token,client)
            self.assertEqual(len(self.calls),count)
            self.expiry+=86400;providers.account('instagram',checked,client,self.config)
            self.assertEqual(checked.meta_expires_at,original)
            self.debug_changes={'user_id':'201'}
            with self.assertRaises(SocialError): providers.account('instagram',checked,client,self.config)

    def test_pagination_uses_only_fixed_url_cursor_and_rejects_cycles(self):
        self.pages_changes={'data':[],'paging':{'next':'http://127.0.0.1/private?access_token=synthetic', 'cursors':{'after':'cursor'}}}
        with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
            with self.assertRaises(SocialError): providers.account('instagram',self.token(client),client,self.config)
        page_requests=[r for r in self.calls if str(r.url).startswith(meta.PAGES)]
        self.assertEqual(len(page_requests),2)
        self.assertEqual(page_requests[-1].url.params['after'],'cursor')

    def test_revoke_requires_boolean_success_and_provider_errors_stay_safe(self):
        self.revoke_success=False
        with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
            with self.assertRaises(SocialError): providers.revoke('instagram',self.config,self.token(client),client)
        self.long_fails=True
        with httpx.Client(transport=httpx.MockTransport(self.handler)) as client:
            with self.assertRaises(SocialError) as caught: self.token(client)
        self.assertNotIn('synthetic',str(caught.exception))

    def test_httpx_log_filter_removes_credential_queries(self):
        record=logging.LogRecord('httpx',logging.INFO,'',0,'HTTP Request: %s %s "%s %d %s"',
            ('GET',meta.TOKEN+'?client_secret=synthetic-secret&fb_exchange_token=synthetic-long','HTTP/1.1',200,'OK'),None)
        meta.GraphLogFilter().filter(record)
        self.assertNotIn('synthetic',record.getMessage());self.assertIn(meta.TOKEN,record.getMessage())


if __name__=='__main__': unittest.main()
