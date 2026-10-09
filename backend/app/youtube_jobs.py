"""Durable, explicitly started YouTube uploads; one bounded step per RQ job."""
import base64
from datetime import datetime, timedelta, timezone
import os
from uuid import UUID
from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from app.database import database
from app.media_access import denied
from app.media_gateway import rpc, CHUNK as MEDIA_CHUNK
from app.production_stages import StageFailure
from app.publication_contract import Metadata, digest, profile
from app.social_config import SocialError
from app.social_api import configuration, connection, stored_tokens, lock
from app.social_crypto import seal, unseal
from app import social_providers as providers
from app import youtube_upload as yt


def try_lock(conn, identity):
    return conn.execute("SELECT pg_try_advisory_lock(hashtextextended(current_schema() || ':youtube:' || %s,27)) AS ok",
                        (str(identity),)).fetchone()['ok']


def validate(conn, identity, project_id=None, artifact_id=None):
    from app.publication_api import video, provenance
    job=conn.execute("SELECT * FROM platform_publications WHERE id=%s AND platform='YOUTUBE'",(identity,)).fetchone()
    if not job or (project_id is not None and job['project_id']!=project_id) or (artifact_id is not None and job['artifact_id']!=artifact_id):
        raise denied(404,'PUBLICATION_NOT_FOUND','YouTube-Auftrag nicht gefunden.')
    row=video(conn, job['project_id'], job['artifact_id'])
    job=conn.execute('SELECT * FROM platform_publications WHERE id=%s FOR UPDATE',(identity,)).fetchone()
    release=conn.execute('SELECT * FROM publication_releases WHERE id=%s',(job['release_id'],)).fetchone()
    draft=conn.execute('SELECT * FROM publication_drafts WHERE artifact_id=%s',(row['id'],)).fetchone()
    source=provenance(conn,row)
    if (not release or release['invalidated_at'] or not draft or draft['revision']!=release['revision']
            or release['checksum_sha256']!=row['checksum_sha256'] or draft['checksum_sha256']!=row['checksum_sha256']
            or draft['provenance_hash']!=digest(source) or release['snapshot']['provenance']!=source
            or release['snapshot']['metadata']!=draft['metadata'] or source['controlled_test']):
        raise denied(409,'PUBLICATION_RELEASE_OUTDATED','Video, Herkunft oder Veröffentlichungsfreigabe geändert. Upload gesperrt.')
    approval=conn.execute("SELECT id FROM approvals WHERE id=%s AND project_id=%s AND artifact_id=%s AND kind='VIDEO' AND checksum_sha256=%s",
        (job['video_approval_id'],job['project_id'],row['id'],row['checksum_sha256'])).fetchone()
    target=release['snapshot']['targets'].get('youtube')
    metadata=Metadata.model_validate(draft['metadata'])
    if not approval or not target or target!=job['snapshot'] or profile('youtube',metadata,source['credits'],row['mode'])!=target['profile']:
        raise denied(409,'PUBLICATION_RELEASE_OUTDATED','Die Datei- oder Plattformfreigabe stimmt nicht überein.')
    config,key=configuration('youtube');lock(conn,'youtube')
    entry=config.providers['youtube']
    if not entry.upload_enabled: raise denied(409,'YOUTUBE_UPLOAD_DISABLED','YouTube-Uploads sind in der privaten Konfiguration deaktiviert.')
    account=connection(conn,'youtube',config)
    if (account['state']!='CONNECTED' or not account['expires_at'] or account['expires_at']<=datetime.now(timezone.utc)
            or not set(providers.SCOPES['youtube'])<=set(account['scopes'])
            or str(account['id'])!=target['connection_id'] or account['account_id']!=target['account_id']
            or account['config_fingerprint']!=target['config_fingerprint']):
        raise denied(409,'PUBLICATION_CONNECTION_CHANGED','Freigegebenes YouTube-Konto erneuern oder Freigabe prüfen.')
    if target['profile']['status']['privacyStatus']!='private' and (not entry.public_upload_approved or entry.review_status!='APPROVED'):
        raise denied(409,'PUBLICATION_PRIVATE_ONLY','Die App ist nur für private Testveröffentlichungen freigegeben.')
    return job,row,key,stored_tokens(key,account)


def session_binding(job):
    return f"youtube-upload:v1:{job['id']}:{job['release_id']}:{job['snapshot']['connection_id']}"


def verified_open(row):
    opened=rpc('open',artifact_id=str(row['id']))
    if opened['checksum']!=row['checksum_sha256'] or not 0<opened['size']<=yt.MAX_SIZE:
        rpc('close',stream=opened['stream'])
        raise yt.UploadError('ARTIFACT_CONFLICT','Die Videodatei stimmt nicht mit der Freigabe überein.')
    return opened


def dispatch(conn, upload, queue):
    number=upload['dispatch_number'];identity=str(upload['publication_id'])
    job_id=f'youtube-{identity}-{number}'
    existing=queue.fetch_job(job_id)
    if existing:
        status=existing.get_status(refresh=True)
        if status in ('queued','deferred','scheduled'): return
        if status=='started' and existing.started_at and existing.started_at>datetime.now(timezone.utc)-timedelta(seconds=180): return
        number+=1
        conn.execute('UPDATE youtube_uploads SET dispatch_number=%s WHERE publication_id=%s',(number,identity))
        job_id=f'youtube-{identity}-{number}'
    conn.commit()  # Persist the delivery identity before Redis; session lock survives.
    queue.enqueue('app.youtube_jobs.run_upload',identity,job_id=job_id,job_timeout=180,result_ttl=86400,failure_ttl=86400)


def recover_uploads(queue):
    # Only explicitly started uploads are in this outbox. No historical queued
    # publication is activated by deployment or by an idle worker heartbeat.
    with database() as conn:
        candidates=conn.execute("SELECT u.publication_id FROM youtube_uploads u JOIN platform_publications p ON p.id=u.publication_id "
            "WHERE p.state='UPLOADING' AND u.available_at<=now() ORDER BY u.started_at LIMIT 100").fetchall()
    for row in candidates:
        with database() as conn:
            if not try_lock(conn,row['publication_id']): continue
            upload=conn.execute("SELECT u.* FROM youtube_uploads u JOIN platform_publications p ON p.id=u.publication_id "
                "WHERE u.publication_id=%s AND p.state='UPLOADING' AND u.available_at<=now()",(row['publication_id'],)).fetchone()
            if upload: dispatch(conn,upload,queue)


def enqueue_pending():
    with Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=3,socket_timeout=3) as redis:
        recover_uploads(Queue('default',connection=redis))


def fail(conn, identity, code, message, retryable=False, delay=30):
    upload=conn.execute('SELECT * FROM youtube_uploads WHERE publication_id=%s',(identity,)).fetchone()
    retry=retryable and upload['retries']<5
    if retry:
        try: validate(conn,identity)
        except (HTTPException,SocialError): retry=False
    conn.execute('UPDATE youtube_uploads SET error_code=%s,retries=LEAST(retries+1,5),available_at=now()+%s,updated_at=now() WHERE publication_id=%s',
        (code,timedelta(seconds=delay),identity))
    # UPLOADING was already validated; FAILED updates must work even after a
    # connection expires. Do not trigger a new authorization-dependent upload.
    conn.execute('UPDATE platform_publications SET state=%s,error_message=%s,updated_at=now() WHERE id=%s',
        ('UPLOADING' if retry else 'FAILED',message,identity))


def checkpoint(conn, identity, reply, size):
    offset,external_id=yt.progress(*reply,size)
    current=conn.execute('SELECT confirmed_bytes FROM youtube_uploads WHERE publication_id=%s',(identity,)).fetchone()['confirmed_bytes']
    if offset<current: raise yt.UploadError('YOUTUBE_RANGE_INVALID','YouTube meldet widersprüchlichen Fortschritt. Ergebnis zuerst prüfen.')
    delay=yt.retry_delay(reply[1]['retry-after']) if 'retry-after' in reply[1] else 0
    conn.execute("UPDATE youtube_uploads SET confirmed_bytes=%s,phase=%s,error_code=NULL,retries=CASE WHEN %s THEN 0 ELSE retries END,available_at=now()+%s,updated_at=now() WHERE publication_id=%s",
        (offset,'PROCESSING' if external_id else 'ACTIVE',bool(external_id or offset>current),timedelta(seconds=delay),identity))
    if external_id:
        conn.execute('UPDATE platform_publications SET external_id=%s,error_message=NULL,updated_at=now() WHERE id=%s',(external_id,identity))
    conn.commit()
    return offset,external_id


def run_upload(identity):
    identity=UUID(identity)
    with database() as conn:
        if not try_lock(conn,identity): return
        job=conn.execute('SELECT * FROM platform_publications WHERE id=%s',(identity,)).fetchone()
        upload=conn.execute('SELECT * FROM youtube_uploads WHERE publication_id=%s',(identity,)).fetchone()
        if not job or not upload or job['state']!='UPLOADING' or upload['available_at']>datetime.now(timezone.utc): return
        try:
            job,row,key,tokens=validate(conn,identity)
            if datetime.now(timezone.utc)-upload['started_at']>timedelta(days=7):
                raise yt.UploadError('YOUTUBE_DEADLINE','Der Upload-Zeitrahmen ist abgelaufen. Bestehenden Auftrag im Zielkonto prüfen.')
            if upload['phase'] in ('INITIATING','UNKNOWN'):
                raise yt.UploadError('YOUTUBE_RESULT_UNKNOWN','Upload-Start nicht eindeutig bestätigt. Ergebnis zuerst im Zielkonto klären; kein Neu-Upload.')
            with yt.http_client() as client:
                if upload['phase']=='PROCESSING':
                    if upload['poll_count']>=120: raise yt.UploadError('YOUTUBE_PROCESSING_TIMEOUT','YouTube-Verarbeitung dauert zu lange. Bestehendes Video im Konto prüfen.')
                    result=yt.status(client,tokens.access_token,job['external_id'],job['snapshot']['account_id'])
                    conn.execute('UPDATE youtube_uploads SET actual_visibility=%s WHERE publication_id=%s',(result['visibility'],identity))
                    conn.commit()  # Preserve actual visibility even when it differs from consent.
                    job,row,key,tokens=validate(conn,identity)
                    expected=job['snapshot']['profile']['status']['privacyStatus']
                    if result['visibility']!=expected:
                        raise yt.UploadError('YOUTUBE_VISIBILITY_CHANGED','YouTube-Sichtbarkeit weicht von der Freigabe ab. Bestehendes Video im Zielkonto prüfen.')
                    conn.execute("UPDATE youtube_uploads SET phase=%s,actual_visibility=%s,error_code=NULL,retries=0,poll_count=poll_count+1,available_at=now()+interval '60 seconds',updated_at=now() WHERE publication_id=%s",
                        ('COMPLETE' if result['complete'] else 'PROCESSING',result['visibility'],identity))
                    conn.execute('UPDATE platform_publications SET state=%s,error_message=NULL,updated_at=now() WHERE id=%s',('PUBLISHED' if result['complete'] else 'UPLOADING',identity))
                    return
                opened=verified_open(row)
                try:
                    if opened['size']!=upload['size_bytes']: raise yt.UploadError('ARTIFACT_CONFLICT','Die Dateigröße hat sich geändert.')
                    if upload['phase']=='READY':
                        # Commit before POST: a crash or lost response must never
                        # create a second resumable session on redelivery.
                        conn.execute("UPDATE youtube_uploads SET phase='INITIATING',updated_at=now() WHERE publication_id=%s",(identity,));conn.commit()
                        job,row,key,tokens=validate(conn,identity)
                        account_id,_=providers.account('youtube',tokens,client)
                        if account_id!=job['snapshot']['account_id']:
                            raise yt.UploadError('SOCIAL_ACCOUNT_CHANGED','Der aktuelle Zugang gehört zu einem anderen YouTube-Kanal.')
                        url=yt.initiate(client,tokens.access_token,job['snapshot']['profile'],opened['size'])
                        conn.execute("UPDATE youtube_uploads SET phase='ACTIVE',session_encrypted=%s,updated_at=now() WHERE publication_id=%s",
                            (seal(key,session_binding(job),{'url':url}),identity));conn.commit()
                    else:
                        url=yt.session_url(unseal(key,session_binding(job),upload['session_encrypted'])['url'])
                    job,row,key,tokens=validate(conn,identity)
                    reply=yt.probe(client,tokens.access_token,url,opened['size'])
                    offset,external_id=checkpoint(conn,identity,reply,opened['size'])
                    if external_id or 'retry-after' in reply[1]: return
                    # Session setup/probing may exceed the gateway's idle TTL.
                    # Reopen and rehash before reading the next bounded chunk.
                    rpc('close',stream=opened['stream']);opened=verified_open(row)
                    if opened['size']!=upload['size_bytes']: raise yt.UploadError('ARTIFACT_CONFLICT','Die Dateigröße hat sich geändert.')
                    data=bytearray();length=min(yt.CHUNK,opened['size']-offset)
                    while len(data)<length:
                        part=rpc('read',stream=opened['stream'],offset=offset+len(data),length=min(MEDIA_CHUNK,length-len(data)))
                        decoded=base64.b64decode(part['data'],validate=True)
                        if not decoded: raise yt.UploadError('MEDIA_CORRUPT','Die Videodatei konnte nicht vollständig gelesen werden.')
                        data.extend(decoded)
                    job,row,key,tokens=validate(conn,identity)
                    checkpoint(conn,identity,yt.send(client,tokens.access_token,url,opened['size'],offset,bytes(data)),opened['size'])
                finally:
                    try: rpc('close',stream=opened['stream'])
                    except (StageFailure,RedisError,OSError): pass
        except (HTTPException,SocialError,StageFailure,yt.UploadError,RedisError,OSError) as exc:
            conn.rollback()
            current=conn.execute('SELECT phase FROM youtube_uploads WHERE publication_id=%s',(identity,)).fetchone()
            initiating=current['phase']=='INITIATING'
            if initiating: conn.execute("UPDATE youtube_uploads SET phase='UNKNOWN' WHERE publication_id=%s",(identity,))
            detail=exc.detail if isinstance(exc,HTTPException) else None
            local_io=isinstance(exc,(RedisError,OSError))
            code=detail['code'] if detail else ('MEDIA_WORKER_UNAVAILABLE' if local_io else exc.code)
            message=detail['message'] if detail else ('Der Medien-Worker ist vorübergehend nicht verfügbar.' if local_io else exc.message if isinstance(exc,SocialError) else str(exc))
            if initiating: code='YOUTUBE_RESULT_UNKNOWN';message='Upload-Start nicht eindeutig bestätigt. Ergebnis zuerst im Zielkonto klären; kein Neu-Upload.'
            fail(conn,identity,code,message,(local_io or isinstance(exc,(StageFailure,yt.UploadError)) and exc.retryable) and not initiating,getattr(exc,'delay',30))
