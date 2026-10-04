"""Bounded host-file transport through Redis, addressed only by artifact IDs."""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from uuid import UUID, uuid4
import psycopg
from psycopg.rows import dict_row
from redis import Redis
from redis.exceptions import RedisError
from app.media import media_root, safe_path
from app.production_stages import StageFailure

CHUNK=1024*1024


def namespace():
    return os.environ.get('MEDIA_RPC_NAMESPACE','video-pipeline:media')


def rpc(operation, **values):
    key=namespace()
    identity=uuid4().hex
    with Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=3,socket_timeout=12) as client:
        reply=key+':reply:'+identity
        client.rpush(key+':requests',json.dumps(dict(id=identity,time=time.time(),operation=operation,**values)))
        client.expire(key+':requests',30)
        item=client.blpop(reply,timeout=10)
        client.delete(reply)
        if not item: raise StageFailure('MEDIA_WORKER_UNAVAILABLE','Der Medien-Worker antwortet nicht. Bitte erneut versuchen.')
        value=json.loads(item[1])
        if 'error' in value: raise StageFailure(value['error'],value['message'])
        return value


class MediaGateway:
    def __init__(self):
        self.redis=Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=3,socket_timeout=3)
        self.database_url=os.environ['DATABASE_URL']
        self.key=namespace()
        self.stop_event=threading.Event()
        self.streams={}
        self.thread=threading.Thread(target=self.serve,name='media-gateway',daemon=True)

    def start(self):
        self.thread.start()
        return self

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=4)

    def open_artifact(self, identity):
        identity=str(UUID(identity))
        with psycopg.connect(self.database_url,row_factory=dict_row) as conn:
            row=conn.execute("SELECT a.storage_path,a.checksum_sha256,a.project_id,r.id AS run_id,v.version,s.result FROM artifacts a "
                             "JOIN production_runs r ON r.id=a.production_run_id "
                             "JOIN script_versions v ON v.id=r.script_version_id "
                             "JOIN production_steps s ON s.production_run_id=r.id AND s.name='STORAGE' "
                             "WHERE a.id=%s AND a.kind='FINAL' AND a.media_type='FINAL_VIDEO' "
                             "AND r.state='COMPLETED' AND s.state='COMPLETED'",(identity,)).fetchone()
        if not row: raise StageFailure('MEDIA_NOT_AVAILABLE','Dieses Video ist noch nicht fertig abgelegt.')
        root=media_root()
        storage=row['result']['storage']
        manifest_path=safe_path(root,storage['manifest_path'])
        raw=manifest_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=storage['manifest_sha256']:
            raise StageFailure('MEDIA_CORRUPT','Die gespeicherten Videodaten sind beschädigt.')
        manifest=json.loads(raw)
        final=manifest['final']
        if (manifest['project_id']!=str(row['project_id']) or manifest['run_id']!=str(row['run_id'])
                or manifest['script_version']!=row['version']
                or final['storage_path']!=row['storage_path'] or final['checksum_sha256']!=row['checksum_sha256']):
            raise StageFailure('MEDIA_CORRUPT','Die gespeicherten Videodaten stimmen nicht überein.')
        path=safe_path(root,row['storage_path'])
        handle=path.open('rb')
        try:
            digest=hashlib.sha256()
            while data:=handle.read(CHUNK): digest.update(data)
            size=handle.tell()
            if digest.hexdigest()!=row['checksum_sha256'] or size!=manifest['encoding']['size_bytes']:
                raise StageFailure('MEDIA_CORRUPT','Die gespeicherte Videodatei ist beschädigt.')
            handle.seek(0)
            if len(self.streams)>=16: raise StageFailure('MEDIA_BUSY','Zu viele Videoabrufe. Bitte kurz warten.')
            token=secrets.token_hex(16)
            self.streams[token]=(handle,size,time.monotonic())
            return dict(stream=token,size=size,checksum=row['checksum_sha256'])
        except BaseException:
            handle.close()
            raise

    def dispatch(self, value):
        operation=value['operation']
        if operation=='info': return dict(path=str(media_root()))
        if operation=='open': return self.open_artifact(value['artifact_id'])
        if operation=='close':
            item=self.streams.pop(value['stream'],None)
            if item: item[0].close()
            return {}
        if operation=='read':
            token=value['stream']; handle,size,_=self.streams[token]
            offset=value['offset']; length=value['length']
            if not isinstance(offset,int) or not isinstance(length,int) or offset<0 or length<1 or length>CHUNK or offset+length>size:
                raise ValueError('invalid range')
            handle.seek(offset); data=handle.read(length)
            if len(data)!=length: raise StageFailure('MEDIA_CORRUPT','Die Videodatei wurde während des Abrufs verändert.')
            self.streams[token]=(handle,size,time.monotonic())
            return dict(data=base64.b64encode(data).decode('ascii'))
        raise ValueError('invalid operation')

    def serve(self):
        try:
            while not self.stop_event.is_set():
                for token,(handle,_,touched) in list(self.streams.items()):
                    if time.monotonic()-touched>30:
                        handle.close(); del self.streams[token]
                try:
                    item=self.redis.blpop(self.key+':requests',timeout=1)
                    if not item: continue
                    if len(item[1])>4096: continue
                    value=json.loads(item[1])
                    identity=value['id']
                    if len(identity)!=32 or not all(c in '0123456789abcdef' for c in identity) or abs(time.time()-value['time'])>15: continue
                    try:
                        result=self.dispatch(value)
                    except StageFailure as exc:
                        result=dict(error=exc.code,message=str(exc))
                    except (OSError,ValueError,KeyError,TypeError,psycopg.Error):
                        result=dict(error='MEDIA_NOT_AVAILABLE',message='Die gespeicherte Videodatei ist momentan nicht verfügbar.')
                    reply=self.key+':reply:'+identity
                    with self.redis.pipeline() as pipe:
                        pipe.rpush(reply,json.dumps(result)); pipe.expire(reply,15); pipe.execute()
                except (RedisError,OSError,ValueError,KeyError,TypeError):
                    self.stop_event.wait(1)
        finally:
            for handle,_,_ in self.streams.values(): handle.close()
            self.streams.clear(); self.redis.close()
