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
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from argon2.low_level import Type
from app.database import database

router = APIRouter(prefix='/api')
COOKIE = 'video_media_session'
SESSION_SECONDS = 14400
PASSWORDS = PasswordHasher(type=Type.ID,time_cost=3,memory_cost=65536,parallelism=4,salt_len=16,hash_len=32)


def denied(status, code, message):
    return HTTPException(status, detail={'code':code,'message':message})


def same_origin(request):
    if request.headers.get('origin') != f"{request.url.scheme}://{request.headers.get('host')}":
        raise denied(403, 'ORIGIN_REJECTED', 'Diese Änderung muss über die lokale Anwendung erfolgen.')


def settings():
    with database() as conn:
        return conn.execute('SELECT * FROM media_access WHERE singleton=true').fetchone()


def legacy_password_hash(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=16384, r=8, p=1,
                          dklen=32, maxmem=64*1024*1024).hex()


def password_hash(password):
    return PASSWORDS.hash(password)


def verify_password(password, row):
    """Legacy verification exists only to upgrade after a successful login."""
    try:
        encoded=row['password_hash']
        if encoded.startswith('$argon2id$'):
            PASSWORDS.verify(encoded,password)
            return True, PASSWORDS.check_needs_rehash(encoded)
        valid=hmac.compare_digest(legacy_password_hash(password,row['password_salt']),encoded)
        return valid,valid
    except (VerificationError,InvalidHashError,ValueError,TypeError,KeyError):
        return False,False


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
        with database() as conn:
            conn.execute('INSERT INTO media_access (password_salt,password_hash,session_secret) VALUES (%s,%s,%s) '
                         'ON CONFLICT DO NOTHING', ('',password_hash(body.password),secrets.token_hex(32)))
        row = settings()
    valid,renew=verify_password(body.password,row)
    if not valid:
        raise denied(401,'MEDIA_PASSWORD_INVALID','Das Passwort ist nicht richtig.')
    if renew:
        with database() as conn:
            conn.execute("UPDATE media_access SET password_hash=%s,password_salt='' WHERE singleton=true AND password_hash=%s",
                         (password_hash(body.password),row['password_hash']))
    if old_session := request.cookies.get(COOKIE):
        with database() as conn:
            conn.execute('DELETE FROM social_oauth_attempts WHERE session_hash=%s',
                         (hashlib.sha256(old_session.encode('utf-8')).hexdigest(),))
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
    # Cancel pending connection grants when this operator session ends.
    if session := request.cookies.get(COOKIE):
        with database() as conn:
            conn.execute('DELETE FROM social_oauth_attempts WHERE session_hash=%s',
                         (hashlib.sha256(session.encode('utf-8')).hexdigest(),))
    response.delete_cookie(COOKIE,path='/api',httponly=True,samesite='strict')
    return {'authorized':False}
