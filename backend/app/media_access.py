"""One local operator session for media and storage settings, never URL tokens."""
import hashlib
import hmac
import os
import secrets
import time
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from redis.exceptions import RedisError
from app.database import database

router = APIRouter(prefix='/api')
COOKIE = 'video_media_session'
SESSION_SECONDS = 14400


def denied(status, code, message):
    return HTTPException(status, detail={'code':code,'message':message})


def same_origin(request):
    if request.headers.get('origin') != f"{request.url.scheme}://{request.headers.get('host')}":
        raise denied(403, 'ORIGIN_REJECTED', 'Diese Änderung muss über die lokale Anwendung erfolgen.')


def settings():
    with database() as conn:
        return conn.execute('SELECT * FROM media_access WHERE singleton=true').fetchone()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=16384, r=8, p=1,
                          dklen=32, maxmem=64*1024*1024).hex()


def authorized(request, row=None):
    row = row or settings()
    try:
        value = request.cookies.get(COOKIE, '')
        expiry, nonce, signature = value.split('.')
        if not row or int(expiry) <= time.time() or int(expiry) > time.time()+SESSION_SECONDS or len(nonce) != 32:
            return False
        expected = hmac.new(bytes.fromhex(row['session_secret']), f'{expiry}.{nonce}'.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def require_access(request: Request):
    if not authorized(request):
        raise denied(401, 'MEDIA_AUTH_REQUIRED', 'Videos und Speichereinstellungen zuerst mit deinem Passwort entsperren.')


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=10, max_length=200)


@router.get('/media-session')
def status(request: Request):
    row = settings()
    return {'configured':bool(row), 'authorized':authorized(request,row) if row else False}


@router.post('/media-session')
def login(body: Login, request: Request, response: Response):
    same_origin(request)
    connection = Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=3,socket_timeout=3)
    key = os.environ.get('MEDIA_RPC_NAMESPACE','video-pipeline:media')+':login-attempts'
    try:
        count = connection.incr(key)
        if count == 1: connection.expire(key,300)
        if count > 10:
            raise denied(429,'LOGIN_LIMIT','Zu viele fehlgeschlagene Anmeldungen. Bitte in fünf Minuten erneut versuchen.')
    except RedisError as exc:
        raise denied(503,'MEDIA_ACCESS_UNAVAILABLE','Der Videozugriff ist derzeit nicht erreichbar.') from exc
    row = settings()
    if row is None:
        salt = secrets.token_hex(16)
        with database() as conn:
            conn.execute('INSERT INTO media_access (password_salt,password_hash,session_secret) VALUES (%s,%s,%s) '
                         'ON CONFLICT DO NOTHING', (salt,password_hash(body.password,salt),secrets.token_hex(32)))
        row = settings()
    if not hmac.compare_digest(password_hash(body.password,row['password_salt']),row['password_hash']):
        raise denied(401,'MEDIA_PASSWORD_INVALID','Das Passwort ist nicht richtig.')
    connection.delete(key)
    expiry, nonce = str(int(time.time())+SESSION_SECONDS), secrets.token_hex(16)
    signature = hmac.new(bytes.fromhex(row['session_secret']),f'{expiry}.{nonce}'.encode(),hashlib.sha256).hexdigest()
    response.set_cookie(COOKIE,f'{expiry}.{nonce}.{signature}',max_age=SESSION_SECONDS,httponly=True,samesite='strict',
                        secure=request.url.scheme=='https',path='/api')
    response.headers['Cache-Control']='no-store'
    return {'configured':True,'authorized':True}


@router.delete('/media-session')
def logout(request: Request, response: Response):
    same_origin(request)
    response.delete_cookie(COOKIE,path='/api',httponly=True,samesite='strict')
    return {'authorized':False}
