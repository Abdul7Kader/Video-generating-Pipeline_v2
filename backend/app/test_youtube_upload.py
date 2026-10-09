import unittest
import logging
import httpx
from app import youtube_upload as yt

SESSION=yt.INSERT+'?uploadType=resumable&upload_id=controlled-session'


class YouTubeProtocolTest(unittest.TestCase):
    def test_only_exact_https_session_origin_and_path_are_accepted(self):
        self.assertEqual(yt.session_url(SESSION),SESSION)
        for url in [None,SESSION.replace('https:','http:'),SESSION.replace('www.googleapis.com','localhost'),
                    SESSION.replace('www.googleapis.com','www.googleapis.com.evil.invalid'),
                    SESSION.replace('www.googleapis.com','user@www.googleapis.com'),SESSION+'#secret',
                    SESSION+'&upload_id=duplicate',SESSION.replace('videos?','videos/../tokens?'),SESSION.replace('controlled-session','a%0Ab')]:
            with self.subTest(url=url), self.assertRaises(yt.UploadError): yt.session_url(url)

    def test_init_and_chunks_use_the_frozen_profile_and_exact_byte_ranges(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200,headers={'Location':SESSION}) if request.method=='POST' else httpx.Response(308,headers={'Range':'bytes=0-262143'})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(yt.initiate(client,'controlled-token',{'status':{'privacyStatus':'private'}},300000),SESSION)
            reply=yt.send(client,'controlled-token',SESSION,300000,0,b'x'*262144)
            self.assertEqual(yt.progress(*reply,300000),(262144,None))
            yt.probe(client,'controlled-token',SESSION,300000)
        self.assertEqual(seen[1].headers['content-range'],'bytes 0-262143/300000')
        self.assertEqual(seen[2].headers['content-range'],'bytes */300000')
        self.assertEqual(seen[0].url.params['notifySubscribers'],'false')

    def test_invalid_ranges_and_missing_video_id_never_count_as_success(self):
        self.assertEqual(yt.progress(308,{}, {},100),(0,None))
        self.assertEqual(yt.progress(201,{}, {'id':'testVideo01'},100),(100,'testVideo01'))
        for code,headers,value in [(308,{'range':'bytes=1-5'},{}),(308,{'range':'bytes=0-100'},{}),(201,{},{}),(201,{}, {'id':'https://evil.invalid'})]:
            with self.assertRaises(yt.UploadError): yt.progress(code,headers,value,100)

    def test_network_rate_limit_and_session_loss_return_safe_errors(self):
        def network(request): raise httpx.ReadTimeout('controlled-private-'+SESSION,request=request)
        for response,code,retry in [(network,'YOUTUBE_NETWORK',True),
                (lambda r:httpx.Response(429,headers={'Retry-After':'60'},text='controlled-private'), 'YOUTUBE_TEMPORARY',True),
                (lambda r:httpx.Response(410,text='controlled-private'),'YOUTUBE_SESSION_LOST',False),
                (lambda r:httpx.Response(302,headers={'Location':'https://evil.invalid'}),'YOUTUBE_REJECTED',False)]:
            with httpx.Client(transport=httpx.MockTransport(response)) as client:
                with self.assertRaises(yt.UploadError) as caught: yt.probe(client,'controlled-private-token',SESSION,100)
            self.assertEqual(caught.exception.code,code);self.assertEqual(caught.exception.retryable,retry)
            self.assertNotIn('controlled-private',str(caught.exception))

    def test_status_requires_owned_video_and_distinguishes_processing_and_visibility(self):
        item={'id':'testVideo01','snippet':{'channelId':'channel'},'status':{'privacyStatus':'private','uploadStatus':'uploaded'},'processingDetails':{'processingStatus':'processing'}}
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'items':[item]}))) as client:
            self.assertFalse(yt.status(client,'token','testVideo01','channel')['complete'])
            item['processingDetails']['processingStatus']='succeeded'
            self.assertEqual(yt.status(client,'token','testVideo01','channel'),{'complete':True,'visibility':'private'})
            with self.assertRaises(yt.UploadError): yt.status(client,'token','testVideo01','other-channel')
            item['status']['uploadStatus']='rejected'
            with self.assertRaises(yt.UploadError): yt.status(client,'token','testVideo01','channel')

    def test_oversized_response_and_retry_after_are_bounded(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*262145))) as client:
            with self.assertRaises(yt.UploadError): yt.probe(client,'token',SESSION,100)
        self.assertEqual(yt.retry_delay('9999999'),86400)
        self.assertEqual(yt.retry_delay(None),30)

    def test_httpx_access_logs_redact_upload_session_query(self):
        record=logging.LogRecord('httpx',logging.INFO,'',1,'HTTP Request: %s %s "%s %d %s"',
            ('PUT',httpx.URL(SESSION),'HTTP/1.1',308,'Resume Incomplete'),None)
        yt.UploadLogFilter().filter(record)
        self.assertNotIn('controlled-session',record.getMessage())
        self.assertNotIn('upload_id',record.getMessage())
