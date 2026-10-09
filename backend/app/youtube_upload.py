"""Bounded YouTube resumable protocol; never follow provider redirects."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import re
from urllib.parse import urlsplit, parse_qs
import httpx

INSERT = 'https://www.googleapis.com/upload/youtube/v3/videos'
VIDEOS = 'https://www.googleapis.com/youtube/v3/videos'
CHUNK = 4 * 1024 * 1024
MAX_SIZE = 256 * 1024**3


class UploadLogFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args,tuple) and len(record.args)==5 and '/upload/youtube/v3/videos' in str(record.args[1]):
            args=list(record.args);args[1]=INSERT;record.args=tuple(args)
        return True


logging.getLogger('httpx').addFilter(UploadLogFilter())


class UploadError(Exception):
    def __init__(self, code, message, retryable=False, delay=30):
        self.code, self.retryable, self.delay = code, retryable, delay
        super().__init__(message)


def session_url(value):
    try:
        uri = urlsplit(value)
        query = parse_qs(uri.query, strict_parsing=True)
        if (not isinstance(value, str) or len(value)>4096 or any(ord(c)<=32 for c in value)
                or uri.scheme!='https' or uri.netloc!='www.googleapis.com'
                or uri.path!='/upload/youtube/v3/videos' or uri.fragment
                or query.get('uploadType')!=['resumable'] or len(query.get('upload_id', []))!=1
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,2000}', query['upload_id'][0])):
            raise ValueError('invalid session')
    except (ValueError, TypeError, AttributeError):
        raise UploadError('YOUTUBE_SESSION_INVALID', 'Die Upload-Sitzung ist ungültig. Kein neuer Upload wurde gestartet.') from None
    return value


def http_client():
    return httpx.Client(timeout=httpx.Timeout(30, connect=10), verify=True,
                        follow_redirects=False, trust_env=False)


def retry_delay(value):
    try:
        seconds=int(value) if str(value).isdigit() else int((parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
        return max(1, min(86400, seconds))
    except (TypeError, ValueError, OverflowError):
        return 30


def request(client, method, url, token, **kwargs):
    if url not in (INSERT, VIDEOS): session_url(url)
    headers={'Authorization': 'Bearer '+token, **kwargs.pop('headers', {})}
    try:
        with client.stream(method, url, headers=headers, **kwargs) as response:
            data=bytearray()
            for block in response.iter_bytes():
                data.extend(block)
                if len(data)>262144: raise UploadError('YOUTUBE_RESPONSE_INVALID', 'YouTube lieferte eine ungültige Antwort.')
            code=response.status_code
            if code==429 or code>=500:
                raise UploadError('YOUTUBE_TEMPORARY', 'YouTube ist vorübergehend nicht verfügbar. Der bestehende Auftrag wird abgeglichen.', True, retry_delay(response.headers.get('Retry-After')))
            if code in (401,403):
                raise UploadError('YOUTUBE_ACCESS_REQUIRED', 'YouTube-Zugang, Kontingent oder Berechtigungen prüfen.')
            if code in (404,410) and url not in (INSERT, VIDEOS):
                raise UploadError('YOUTUBE_SESSION_LOST', 'Upload-Sitzung nicht mehr verfügbar. Ergebnis zuerst im Zielkonto klären; kein automatischer Neu-Upload.')
            if code not in (200,201,308):
                raise UploadError('YOUTUBE_REJECTED', 'YouTube hat den Auftrag abgewiesen. Angaben und Rechte prüfen.')
            try: value=json.loads(data) if data else {}
            except ValueError: raise UploadError('YOUTUBE_RESPONSE_INVALID', 'YouTube lieferte eine ungültige Antwort.') from None
            if not isinstance(value,dict): raise UploadError('YOUTUBE_RESPONSE_INVALID', 'YouTube lieferte eine ungültige Antwort.')
            return code, dict(response.headers), value
    except httpx.HTTPError:
        # Do not retain provider bodies, URLs, tokens, or chained HTTP exceptions.
        raise UploadError('YOUTUBE_NETWORK', 'YouTube antwortet nicht eindeutig. Der bestehende Upload wird zuerst abgefragt.', True) from None


def initiate(client, token, profile, size):
    code, headers, _=request(client, 'POST', INSERT, token,
        params={'uploadType':'resumable', 'part':','.join(profile), 'notifySubscribers':'false'},
        headers={'X-Upload-Content-Length':str(size), 'X-Upload-Content-Type':'video/mp4'}, json=profile)
    if code not in (200,201): raise UploadError('YOUTUBE_RESPONSE_INVALID', 'YouTube hat keine Upload-Sitzung bestätigt.')
    return session_url(headers.get('location'))


def progress(code, headers, value, size):
    if code in (200,201):
        identity=value.get('id')
        if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity):
            raise UploadError('YOUTUBE_RESPONSE_INVALID', 'YouTube hat keine gültige Video-ID bestätigt.')
        return size, identity
    match=re.fullmatch(r'bytes=0-([0-9]{1,12})', headers.get('range',''))
    if 'range' in headers and not match:
        raise UploadError('YOUTUBE_RANGE_INVALID', 'YouTube hat keinen gültigen Upload-Fortschritt bestätigt.')
    offset=int(match[1])+1 if match else 0
    if offset>=size: raise UploadError('YOUTUBE_RANGE_INVALID', 'Upload vollständig übertragen, aber noch nicht bestätigt. Ergebnis prüfen.')
    return offset, None


def probe(client, token, url, size):
    return request(client, 'PUT', session_url(url), token,
                   headers={'Content-Length':'0', 'Content-Range':f'bytes */{size}'}, content=b'')


def send(client, token, url, size, offset, data):
    return request(client, 'PUT', session_url(url), token,
        headers={'Content-Length':str(len(data)), 'Content-Type':'video/mp4',
                 'Content-Range':f'bytes {offset}-{offset+len(data)-1}/{size}'}, content=data)


def status(client, token, identity, account_id):
    _, _, value=request(client, 'GET', VIDEOS, token,
        params={'part':'snippet,status,processingDetails', 'id':identity})
    try:
        items=value['items']
        if len(items)!=1 or items[0]['id']!=identity or items[0]['snippet']['channelId']!=account_id:
            raise ValueError('wrong account or missing video')
        item=items[0]
        visibility=item['status']['privacyStatus']
        uploaded=item['status']['uploadStatus']
        processed=item.get('processingDetails',{}).get('processingStatus')
        if visibility not in ('private','unlisted','public') or uploaded not in ('uploaded','processed','failed','rejected','deleted'):
            raise ValueError('invalid status')
        if uploaded in ('failed','rejected','deleted') or processed in ('failed','terminated'):
            raise UploadError('YOUTUBE_PROCESSING_FAILED', 'YouTube hat das Video nicht erfolgreich verarbeitet. Bestehendes Video im Zielkonto prüfen.')
        if processed not in (None,'processing','succeeded'): raise ValueError('invalid processing')
        return dict(visibility=visibility, complete=uploaded=='processed' or processed=='succeeded')
    except (ValueError, KeyError, TypeError):
        raise UploadError('YOUTUBE_STATUS_INVALID', 'YouTube-Video und Zielkonto konnten nicht eindeutig bestätigt werden.') from None
