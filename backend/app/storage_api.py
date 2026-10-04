"""Authenticated settings and persistent copy status; paths belong to the host."""
import os
from uuid import UUID
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from app.database import database
from app.media_access import denied, require_access, same_origin
from app.media_gateway import rpc
from app.production_stages import StageFailure
from app.storage_jobs import dispatch_change
from app.storage_settings import storage_lock

router=APIRouter(prefix='/api')


def host_info():
    try: return rpc('info')
    except (StageFailure,RedisError,OSError) as exc:
        raise denied(503,'MEDIA_WORKER_UNAVAILABLE','Der Medien-Worker antwortet nicht. Bitte erneut versuchen.') from exc


@router.get('/storage')
def storage(request: Request):
    require_access(request)
    info=host_info()
    with database() as conn:
        change=conn.execute('SELECT * FROM storage_changes ORDER BY created_at DESC LIMIT 1').fetchone()
    return dict(**info,change=change)


class StorageInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    path: str=Field(min_length=1,max_length=4096)
    expected_path: str=Field(min_length=1,max_length=4096)


@router.post('/storage/changes',status_code=202)
def change(body: StorageInput, request: Request):
    require_access(request); same_origin(request)
    if any(c in body.path for c in ('\0','\r','\n')):
        raise denied(422,'STORAGE_PATH_INVALID','Bitte einen vollständigen Ordnerpfad eingeben.')
    info=host_info()
    if info['path']!=body.expected_path:
        raise denied(409,'STORAGE_CHANGED','Der Speicher wurde inzwischen geändert. Bitte neu laden.')
    with database() as conn:
        if not storage_lock(conn):
            raise denied(409,'STORAGE_BUSY','Während einer Produktion kann der Speicher nicht geändert werden.')
        current=conn.execute("SELECT * FROM storage_changes WHERE state IN ('QUEUED','RUNNING')").fetchone()
        if current:
            if current['new_path']==body.path: return current
            raise denied(409,'STORAGE_BUSY','Eine Speicherübernahme läuft bereits.')
        if conn.execute("SELECT EXISTS (SELECT 1 FROM production_runs WHERE state IN ('QUEUED','RUNNING')) AS busy").fetchone()['busy']:
            raise denied(409,'STORAGE_BUSY','Bitte die laufende Produktion zuerst abschließen oder abbrechen.')
        row=conn.execute('INSERT INTO storage_changes(old_path,new_path) VALUES (%s,%s) RETURNING *',(info['path'],body.path.strip())).fetchone()
    # Outbox is durable before Redis dispatch, including a lost enqueue reply.
    try:
        with database() as conn:
            row=conn.execute('SELECT * FROM storage_changes WHERE id=%s FOR UPDATE',(row['id'],)).fetchone()
            queue=Queue('default',connection=Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=3,socket_timeout=3))
            dispatch_change(conn,row,queue)
    except (RedisError,OSError):
        pass
    return row


@router.get('/storage/changes/{change_id}')
def change_status(change_id: UUID,request: Request):
    require_access(request)
    with database() as conn:
        row=conn.execute('SELECT * FROM storage_changes WHERE id=%s',(change_id,)).fetchone()
    if not row: raise denied(404,'STORAGE_CHANGE_NOT_FOUND','Speicherübernahme nicht gefunden.')
    return row
