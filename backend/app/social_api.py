"""Single-operator connections with one-time OAuth and encrypted persistence."""
from datetime import datetime, timezone, timedelta
import hashlib
import logging
import secrets
from urllib.parse import urlsplit
from uuid import uuid4
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Literal
from app.database import database
from app.media_access import COOKIE, denied, require_access, same_origin
from app.social_config import PLATFORMS, SocialError, load_config, blockers
from app.social_crypto import load_key, seal, unseal
from app import social_providers as providers

router=APIRouter(prefix='/api/connections')


class CallbackLogFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args,tuple) and len(record.args)==5:
            args=list(record.args)
            if isinstance(args[2],str) and args[2].startswith('/api/connections/') and '/callback' in args[2]:
                args[2]=args[2].split('?',1)[0];record.args=tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(CallbackLogFilter())


def digest(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()


def fingerprint(config, provider):
    entry=config.providers[provider]
    return digest(config.origin+'\0'+entry.client_id+'\0'+entry.client_secret.get_secret_value())


def binding(provider, identity, fingerprint_value):
    return f'social:v1:{provider}:{identity}:{fingerprint_value}'


def cookie_name(provider): return 'video_oauth_'+provider


def stored_tokens(key,row):
    try:
        return providers.Tokens.model_validate(unseal(key,binding(row['provider'],row['id'],row['config_fingerprint']),row['tokens_encrypted']))
    except ValueError as exc:
        raise SocialError('SOCIAL_TOKEN_INVALID','Gespeicherte Zugangsdaten sind ungültig. Bitte Schlüssel und Sicherung prüfen.') from exc


def lock(conn,provider):
    # database() returns a fresh connection that closes at context exit. This
    # session lock survives the durable OAuth checkpoints and dies on close.
    if not conn.execute("SELECT pg_try_advisory_lock(hashtextextended(current_schema() || ':social:' || %s,25)) AS ok",(provider,)).fetchone()['ok']:
        raise denied(409,'SOCIAL_BUSY','Eine Kontoänderung läuft bereits. Bitte erneut versuchen.')


def configuration(provider, active=True):
    if provider not in PLATFORMS: raise denied(404,'SOCIAL_PLATFORM_UNKNOWN','Unbekannte Plattform.')
    try:
        config=load_config()
        problems=blockers(provider,config) if active else []
        if active and problems: raise denied(409,'SOCIAL_NOT_READY',problems[0])
        if not config or provider not in config.providers:
            raise denied(409,'SOCIAL_NOT_CONFIGURED','Eigener OAuth-Zugang fehlt.')
        return config,load_key()
    except SocialError as exc:
        raise denied(503,exc.code,exc.message) from exc


def require_origin(request,config):
    if (request.headers.get('origin')!=config.origin
            or request.headers.get('host')!=urlsplit(config.origin).netloc):
        raise denied(403,'ORIGIN_REJECTED','Diese Änderung muss über die lokale Anwendung erfolgen.')


def public(row, provider, config, problems):
    now=datetime.now(timezone.utc)
    state=row['state'] if row else 'DISCONNECTED'
    connected=bool(row and row['tokens_encrypted'])
    missing=sorted(set(providers.SCOPES.get(provider,[]))-set(row['scopes'] if row else []))
    if connected:
        if not config or provider not in config.providers or row['config_fingerprint']!=fingerprint(config,provider):
            problems=problems+['OAuth-Konfiguration geändert. Ursprünglichen Zugang für den Widerruf wiederherstellen.']
        if missing: problems=problems+['Fehlende Berechtigungen: '+', '.join(missing)]
        if state=='REAUTH_REQUIRED': problems=problems+['Zugang oder Zielkonto nicht bestätigt. Den bisherigen Zugang zuerst widerrufen und dann neu verbinden.']
        if state=='REVOKE_FAILED': problems=problems+['Widerruf noch nicht bestätigt. Die Verbindung bleibt für weitere Nutzung gesperrt.']
        if row['refresh_expires_at'] and row['refresh_expires_at']<=now:
            state='REAUTH_REQUIRED';problems=problems+['Dauerhafte Zustimmung abgelaufen. Bitte erneut verbinden.']
        if row['expires_at'] and row['expires_at']<=now and state in ('CONNECTED','LIMITED'):
            state='EXPIRED';problems=problems+['Zugang erneuern oder das Konto erneut verbinden.']
    matching=bool(connected and config and provider in config.providers and row['config_fingerprint']==fingerprint(config,provider))
    return dict(provider=provider,label=PLATFORMS[provider],state=state,
        account_title=row['account_title'] if connected else None,
        scopes=row['scopes'] if connected else [],expires_at=row['expires_at'] if connected else None,
        can_connect=not blockers(provider,config) and not connected and not any('Schlüssel' in p for p in problems),
        can_refresh=matching and not blockers(provider,config) and state not in ('REVOKE_FAILED','REAUTH_REQUIRED'),
        can_disconnect=matching,can_forget=connected,problems=problems,
        review_status=config.providers[provider].review_status if config and provider in config.providers else 'UNVERIFIED')


@router.get('')
def list_connections(request:Request,response:Response):
    require_access(request)
    response.headers['Cache-Control']='no-store'
    try: config=load_config();config_problem=None
    except SocialError as exc: config=None;config_problem=exc.message
    try: load_key();key_problem=None
    except SocialError as exc: key_problem=exc.message
    with database() as conn:
        rows={r['provider']:r for r in conn.execute('SELECT * FROM social_connections')}
    result=[]
    for provider in PLATFORMS:
        problems=blockers(provider,config)
        if config_problem: problems.append(config_problem)
        if key_problem and provider in ('youtube','tiktok'): problems.append(key_problem)
        item=public(rows.get(provider),provider,config,problems)
        if key_problem: item.update(can_connect=False,can_refresh=False,can_disconnect=False)
        result.append(item)
    return {'connections':result}


@router.post('/{provider}/authorize')
def authorize(provider:str,request:Request,response:Response):
    require_access(request)
    config,key=configuration(provider);require_origin(request,config)
    state,nonce,verifier=secrets.token_urlsafe(32),secrets.token_urlsafe(32),secrets.token_urlsafe(48)
    now=datetime.now(timezone.utc)
    session=request.cookies[COOKIE]
    expires=min(now+timedelta(minutes=10),datetime.fromtimestamp(int(session.split('.')[0]),timezone.utc))
    fp=fingerprint(config,provider)
    with database() as conn:
        lock(conn,provider)
        row=conn.execute('SELECT * FROM social_connections WHERE provider=%s',(provider,)).fetchone()
        if row and row['tokens_encrypted']:
            raise denied(409,'SOCIAL_REVOKE_PENDING','Bestehenden Zugang erneuern oder vor einer neuen Zustimmung zuerst widerrufen.')
        identity=row['id'] if row else uuid4()
        conn.execute('DELETE FROM social_oauth_attempts WHERE provider=%s OR expires_at<=now()',(provider,))
        conn.execute('INSERT INTO social_oauth_attempts(provider,state_hash,binding_hash,session_hash,config_fingerprint,connection_id,verifier_encrypted,expires_at) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(provider,digest(state),digest(nonce),digest(session),fp,identity,
            seal(key,binding(provider,identity,fp)+':verifier',{'verifier':verifier}),expires))
    response.set_cookie(cookie_name(provider),nonce,max_age=max(1,int((expires-now).total_seconds())),
        httponly=True,samesite='lax',secure=config.origin.startswith('https:'),path='/api/connections/'+provider)
    response.headers['Cache-Control']='no-store'
    return {'authorization_url':providers.authorization_url(provider,config,state,verifier)}


def save_tokens(conn,provider,config,key,identity,tokens,account_id,account_title,previous=None,verified=True):
    now=datetime.now(timezone.utc);fp=fingerprint(config,provider)
    scopes=tokens.scopes(provider)
    state='CONNECTED' if set(providers.SCOPES[provider])<=set(scopes) else 'LIMITED'
    if not tokens.refresh_token or not verified: state='REAUTH_REQUIRED'
    refresh_expiry=now+timedelta(seconds=tokens.refresh_expires_in) if tokens.refresh_expires_in else (previous['refresh_expires_at'] if previous else None)
    conn.execute('INSERT INTO social_connections(provider,id,config_fingerprint,account_id,account_title,scopes,tokens_encrypted,expires_at,refresh_expires_at,state) '
        'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (provider) DO UPDATE SET '
        'id=EXCLUDED.id,config_fingerprint=EXCLUDED.config_fingerprint,account_id=EXCLUDED.account_id,account_title=EXCLUDED.account_title,scopes=EXCLUDED.scopes,'
        'tokens_encrypted=EXCLUDED.tokens_encrypted,expires_at=EXCLUDED.expires_at,refresh_expires_at=EXCLUDED.refresh_expires_at,state=EXCLUDED.state,error_code=NULL,updated_at=now()',
        (provider,identity,fp,account_id,account_title,Jsonb(scopes),seal(key,binding(provider,identity,fp),tokens.model_dump()),
         now+timedelta(seconds=tokens.expires_in),refresh_expiry,state))


@router.get('/{provider}/callback',include_in_schema=False)
def callback(provider:str,request:Request):
    config,key=configuration(provider)
    if request.headers.get('host')!=urlsplit(config.origin).netloc:
        raise denied(403,'ORIGIN_REJECTED','Ungültiger Rückweg der Kontoverbindung.')
    values=request.query_params
    state=values.get('state','');nonce=request.cookies.get(cookie_name(provider),'')
    if not 1<=len(state)<=128 or not 1<=len(nonce)<=128:
        raise denied(400,'SOCIAL_STATE_INVALID','Kontoverbindung abgelaufen oder nicht in diesem Browser gestartet.')
    for name in ('state','code','error'):
        if len(values.getlist(name))>1: raise denied(400,'SOCIAL_STATE_INVALID','Mehrdeutiger OAuth-Rückweg.')
    error=None
    with database() as conn:
        lock(conn,provider)
        attempt=conn.execute('UPDATE social_oauth_attempts SET consumed=true WHERE provider=%s AND state_hash=%s AND binding_hash=%s AND consumed=false AND expires_at>now() RETURNING *',
            (provider,digest(state),digest(nonce))).fetchone()
        if not attempt: raise denied(400,'SOCIAL_STATE_INVALID','Kontoverbindung abgelaufen, bereits verwendet oder in einem anderen Browser gestartet.')
        conn.commit()  # a lost process/response cannot make the state reusable
        try:
            if attempt['config_fingerprint']!=fingerprint(config,provider):
                raise SocialError('SOCIAL_CONFIG_CHANGED','OAuth-Konfiguration geändert. Bitte neu verbinden.')
            # Strict media cookie may be absent on the cross-site callback. When
            # present it must belong to the session that created this attempt.
            if COOKIE in request.cookies and digest(request.cookies[COOKIE])!=attempt['session_hash']:
                raise SocialError('SOCIAL_STATE_INVALID','Die Betreibersitzung hat sich geändert.')
            code=values.get('code','')
            if values.get('error') or not 1<=len(code)<=4096:
                raise SocialError('SOCIAL_CONSENT_DENIED','Kontoverbindung nicht freigegeben.')
            identity=attempt['connection_id'];fp=attempt['config_fingerprint']
            verifier=unseal(key,binding(provider,identity,fp)+':verifier',attempt['verifier_encrypted'])['verifier']
            previous=conn.execute('SELECT * FROM social_connections WHERE provider=%s',(provider,)).fetchone()
            if previous and previous['tokens_encrypted']:
                raise SocialError('SOCIAL_REVOKE_PENDING','Bestehenden Zugang zuerst widerrufen.')
            with providers.http_client() as client:
                tokens=providers.exchange(provider,config,code,verifier,client)
                # Persist the received grant before account lookup so an
                # ineligible/failed lookup still leaves a revocable credential.
                save_tokens(conn,provider,config,key,identity,tokens,None,None,verified=False)
                conn.commit()  # unverified grant survives a failed lookup/process
                account_id,title=providers.account(provider,tokens,client)
                pending=conn.execute('SELECT provider FROM social_oauth_attempts WHERE provider=%s AND state_hash=%s AND expires_at>now() FOR UPDATE',(provider,digest(state))).fetchone()
                if not pending:
                    # Logout canceled the pending grant. Revoke the new token;
                    # if that fails the staged credential remains recoverable.
                    try:
                        providers.revoke(provider,config,tokens,client)
                        clear_local(conn,provider)
                    except SocialError:
                        conn.execute("UPDATE social_connections SET state='REVOKE_FAILED' WHERE provider=%s",(provider,))
                    raise SocialError('SOCIAL_STATE_INVALID','Die Betreibersitzung wurde beendet. Bitte neu anmelden.')
            save_tokens(conn,provider,config,key,identity,tokens,account_id,title,previous)
        except SocialError as exc:
            error=exc.code  # consumed even after failure; never replay a code
            conn.execute("UPDATE social_connections SET error_code=%s WHERE provider=%s AND state='REAUTH_REQUIRED'",(error,provider))
        conn.execute('DELETE FROM social_oauth_attempts WHERE provider=%s AND state_hash=%s',(provider,digest(state)))
    result=RedirectResponse(config.origin+'/?connections='+provider+'&connection_result='+(error or 'CONNECTED'),status_code=303)
    result.delete_cookie(cookie_name(provider),path='/api/connections/'+provider,httponly=True,samesite='lax',secure=config.origin.startswith('https:'))
    result.headers.update({'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    return result


def connection(conn,provider,config):
    row=conn.execute('SELECT * FROM social_connections WHERE provider=%s FOR UPDATE',(provider,)).fetchone()
    if not row or not row['tokens_encrypted']: raise denied(409,'SOCIAL_NOT_CONNECTED','Das Konto ist nicht verbunden.')
    if row['config_fingerprint']!=fingerprint(config,provider):
        raise denied(409,'SOCIAL_CONFIG_CHANGED','OAuth-Zugang geändert. Ursprüngliche Konfiguration wiederherstellen oder beim Anbieter widerrufen.')
    return row


@router.post('/{provider}/refresh')
def refresh_connection(provider:str,request:Request):
    require_access(request)
    config,key=configuration(provider);require_origin(request,config)
    error=None
    with database() as conn:
        lock(conn,provider);row=connection(conn,provider,config)
        if row['state']=='REVOKE_FAILED': raise denied(409,'SOCIAL_REVOKE_PENDING','Den ausstehenden Widerruf zuerst abschließen.')
        received=False
        try:
            if row['refresh_expires_at'] and row['refresh_expires_at']<=datetime.now(timezone.utc):
                raise SocialError('SOCIAL_REAUTH_REQUIRED','Dauerhafte Zustimmung abgelaufen. Bitte neu verbinden.')
            previous=stored_tokens(key,row)
            with providers.http_client() as client:
                tokens=providers.refresh(provider,config,previous,client)
                # A rotating refresh token may already invalidate the previous
                # one. Preserve the replacement before any further HTTP call.
                save_tokens(conn,provider,config,key,row['id'],tokens,row['account_id'],row['account_title'],row,verified=False)
                conn.commit()
                received=True
                account_id,title=providers.account(provider,tokens,client)
            if account_id!=row['account_id']: raise SocialError('SOCIAL_ACCOUNT_CHANGED','Die erneuerten Tokens gehören zu einem anderen Zielkonto.')
            save_tokens(conn,provider,config,key,row['id'],tokens,account_id,title,row)
        except SocialError as exc:
            error=exc
            if received or exc.code in ('SOCIAL_REAUTH_REQUIRED','SOCIAL_ACCOUNT_CHANGED'):
                conn.execute("UPDATE social_connections SET state='REAUTH_REQUIRED',error_code=%s,updated_at=now() WHERE provider=%s",(exc.code,provider))
    if error: raise denied(409,error.code,error.message)
    return {'state':'UPDATED'}


@router.delete('/{provider}')
def disconnect(provider:str,request:Request):
    require_access(request)
    config,key=configuration(provider,active=False);require_origin(request,config)
    error=None
    with database() as conn:
        lock(conn,provider)
        row=conn.execute('SELECT * FROM social_connections WHERE provider=%s FOR UPDATE',(provider,)).fetchone()
        if not row or not row['tokens_encrypted']: return {'state':'DISCONNECTED'}
        row=connection(conn,provider,config)
        try:
            tokens=stored_tokens(key,row)
            with providers.http_client() as client: providers.revoke(provider,config,tokens,client)
            clear_local(conn,provider)
        except SocialError as exc:
            error=exc
            conn.execute("UPDATE social_connections SET state='REVOKE_FAILED',error_code=%s,updated_at=now() WHERE provider=%s",(exc.code,provider))
    if error: raise denied(503,'SOCIAL_REVOKE_FAILED','Widerruf nicht bestätigt. Der Zugang bleibt gesperrt; bitte den Widerruf erneut versuchen oder beim Anbieter entfernen.')
    return {'state':'DISCONNECTED'}


class LocalRemoval(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provider_access_removed: Literal[True]

    @field_validator('provider_access_removed',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True: raise ValueError('Explicit provider removal confirmation required')
        return value


def clear_local(conn,provider):
    conn.execute("UPDATE social_connections SET state='DISCONNECTED',account_id=NULL,account_title=NULL,scopes='[]',tokens_encrypted=NULL,expires_at=NULL,refresh_expires_at=NULL,error_code=NULL,updated_at=now() WHERE provider=%s",(provider,))
    conn.execute('DELETE FROM social_oauth_attempts WHERE provider=%s',(provider,))


@router.post('/{provider}/forget')
def forget(provider:str,body:LocalRemoval,request:Request):
    """Recovery after an operator removes access in the provider's own console."""
    require_access(request);same_origin(request)
    if provider not in ('youtube','tiktok'): raise denied(404,'SOCIAL_PLATFORM_UNKNOWN','Unbekannte Plattform.')
    with database() as conn:
        lock(conn,provider)
        clear_local(conn,provider)
    return {'state':'DISCONNECTED','provider_revoke_verified':False}
