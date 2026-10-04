"""Authenticated MP4 streaming with bounded single HTTP byte ranges."""
import base64
import re
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from app.media_access import denied, require_access
from app.media_gateway import CHUNK, rpc
from app.production_stages import StageFailure


def byte_range(value, size):
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or not any(match.groups()): raise ValueError('invalid range')
    left,right=match.groups()
    if not left:
        length=int(right)
        if length<1: raise ValueError('empty suffix')
        return max(0,size-length),size-1
    start=int(left); end=min(int(right),size-1) if right else size-1
    if start>=size or end<start: raise ValueError('unsatisfiable range')
    return start,end


def deliver(artifact_id, request: Request):
    require_access(request)
    try:
        opened=rpc('open',artifact_id=str(artifact_id))
    except StageFailure as exc:
        raise denied(409 if exc.code=='MEDIA_CORRUPT' else 503 if exc.code=='MEDIA_WORKER_UNAVAILABLE' else 404,exc.code,str(exc)) from exc
    except (RedisError,OSError) as exc:
        raise denied(503,'MEDIA_WORKER_UNAVAILABLE','Der Medien-Worker ist momentan nicht verfügbar.') from exc
    token=opened['stream']; size=opened['size']; etag='"'+opened['checksum']+'"'
    def close():
        try: rpc('close',stream=token)
        except (StageFailure,RedisError,OSError): pass
    headers={'Accept-Ranges':'bytes','ETag':etag,'Cache-Control':'private, no-store',
             'Content-Disposition':f'inline; filename="video-{artifact_id}.mp4"','X-Content-Type-Options':'nosniff'}
    start,end=0,size-1; status=200
    if request.headers.get('range') and request.headers.get('if-range',etag)==etag:
        try: start,end=byte_range(request.headers['range'],size)
        except ValueError:
            close()
            return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{size}'})
        status=206; headers['Content-Range']=f'bytes {start}-{end}/{size}'
    headers['Content-Length']=str(end-start+1)
    if request.method=='HEAD':
        close(); return Response(status_code=status,headers=headers,media_type='video/mp4')
    def content():
        try:
            offset=start
            while offset<=end:
                length=min(CHUNK,end-offset+1)
                value=rpc('read',stream=token,offset=offset,length=length)
                data=base64.b64decode(value['data'],validate=True)
                if len(data)!=length: raise ValueError('incomplete media block')
                yield data; offset+=length
        finally: close()
    return StreamingResponse(content(),status_code=status,headers=headers,media_type='video/mp4')
