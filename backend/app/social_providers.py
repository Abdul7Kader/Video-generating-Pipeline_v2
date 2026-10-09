"""Bounded official OAuth endpoints. No uploads and no arbitrary URL fetching."""
import base64
import hashlib
import json
from urllib.parse import urlencode
import httpx
from pydantic import BaseModel, ConfigDict, Field
from app.social_config import SocialError

SCOPES={'youtube':['https://www.googleapis.com/auth/youtube.readonly','https://www.googleapis.com/auth/youtube.upload'],
        'tiktok':['user.info.basic','video.publish']}
AUTH={'youtube':'https://accounts.google.com/o/oauth2/v2/auth','tiktok':'https://www.tiktok.com/v2/auth/authorize/'}
TOKEN={'youtube':'https://oauth2.googleapis.com/token','tiktok':'https://open.tiktokapis.com/v2/oauth/token/'}
REVOKE={'youtube':'https://oauth2.googleapis.com/revoke','tiktok':'https://open.tiktokapis.com/v2/oauth/revoke/'}
ACCOUNT={'youtube':'https://www.googleapis.com/youtube/v3/channels','tiktok':'https://open.tiktokapis.com/v2/user/info/'}
ALLOWED=set(TOKEN.values())|set(REVOKE.values())|set(ACCOUNT.values())
CREATOR='https://open.tiktokapis.com/v2/post/publish/creator_info/query/'
ALLOWED.add(CREATOR)


class CreatorInfo(BaseModel):
    model_config=ConfigDict(extra='ignore',hide_input_in_errors=True)
    privacy_level_options: list[str]=Field(min_length=1,max_length=4)
    creator_nickname: str=Field(min_length=1,max_length=300)
    max_video_post_duration_sec: int=Field(gt=0,le=86400,strict=True)
    comment_disabled: bool=Field(strict=True)
    duet_disabled: bool=Field(strict=True)
    stitch_disabled: bool=Field(strict=True)


def creator_info(tokens,client):
    try:
        value=remote(client,'POST',CREATOR,headers={'Authorization':'Bearer '+tokens.access_token},json={})
        return CreatorInfo.model_validate(value['data'])
    except (KeyError,ValueError,TypeError) as exc:
        raise SocialError('SOCIAL_CREATOR_INVALID','TikTok-Kontooptionen konnten nicht bestätigt werden.') from exc


class Tokens(BaseModel):
    model_config=ConfigDict(extra='ignore',allow_inf_nan=False,hide_input_in_errors=True)
    access_token: str=Field(min_length=1,max_length=16384,repr=False)
    refresh_token: str | None=Field(default=None,min_length=1,max_length=16384,repr=False)
    expires_in: int=Field(ge=1,le=31536000,strict=True)
    refresh_expires_in: int | None=Field(default=None,ge=1,le=315360000,strict=True)
    scope: str=Field(default='',max_length=4096)
    token_type: str='Bearer'
    open_id: str | None=Field(default=None,min_length=1,max_length=300)

    def scopes(self, provider):
        return sorted(set(self.scope.replace(',',' ').split()) & set(SCOPES[provider]))


def authorization_url(provider, config, state, verifier):
    entry=config.providers[provider]
    digest=hashlib.sha256(verifier.encode('ascii')).digest()
    challenge=digest.hex() if provider=='tiktok' else base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    params={'client_key' if provider=='tiktok' else 'client_id':entry.client_id,
            'redirect_uri':config.callback(provider),'response_type':'code','state':state,
            'scope':(',' if provider=='tiktok' else ' ').join(SCOPES[provider]),
            'code_challenge':challenge,'code_challenge_method':'S256'}
    if provider=='youtube': params.update(access_type='offline',prompt='consent')
    return AUTH[provider]+'?'+urlencode(params)


def remote(client, method, url, **kwargs):
    if url not in ALLOWED: raise SocialError('SOCIAL_ENDPOINT_INVALID','Nicht freigegebener Plattformendpunkt.')
    try:
        with client.stream(method,url,**kwargs) as response:
            data=bytearray()
            for block in response.iter_bytes():
                data.extend(block)
                if len(data)>262144: raise ValueError('oversized response')
            if response.status_code>=400:
                # Never echo provider error descriptions, codes, URLs or tokens.
                code='SOCIAL_REAUTH_REQUIRED' if response.status_code in (400,401,403) else 'SOCIAL_PROVIDER_UNAVAILABLE'
                raise SocialError(code,'Plattformzugang abgelehnt. Rechte prüfen und das Konto erneut verbinden.'
                    if code=='SOCIAL_REAUTH_REQUIRED' else 'Die Plattform antwortet derzeit nicht zuverlässig. Bitte erneut versuchen.')
            if not 200<=response.status_code<300: raise ValueError('redirect refused')
            value=json.loads(data) if data else {}
            if not isinstance(value,dict) or value.get('error') not in (None,{},''):
                if not (isinstance(value.get('error'),dict) and value['error'].get('code')=='ok'):
                    raise ValueError('provider error')
            return value
    except (httpx.HTTPError, ValueError) as exc:
        raise SocialError('SOCIAL_PROVIDER_UNAVAILABLE','Ungültige oder fehlende Plattformantwort. Bitte erneut versuchen.') from exc


def http_client():
    return httpx.Client(timeout=10,verify=True,follow_redirects=False,trust_env=False)


def credentials(provider, entry):
    return {'client_key' if provider=='tiktok' else 'client_id':entry.client_id,
            'client_secret':entry.client_secret.get_secret_value()}


def parse_tokens(value, previous=None):
    try:
        token=Tokens.model_validate(value)
        if token.token_type.lower()!='bearer': raise ValueError('unsupported token')
        if previous:
            if not token.refresh_token: token.refresh_token=previous.refresh_token
            if 'scope' not in value: token.scope=previous.scope
        return token
    except (ValueError, TypeError) as exc:
        raise SocialError('SOCIAL_TOKEN_RESPONSE_INVALID','Die Plattform hat keine gültigen Zugangsdaten geliefert.') from exc


def exchange(provider, config, code, verifier, client):
    body=credentials(provider,config.providers[provider])
    body.update(grant_type='authorization_code',code=code,redirect_uri=config.callback(provider),code_verifier=verifier)
    return parse_tokens(remote(client,'POST',TOKEN[provider],data=body))


def refresh(provider, config, previous, client):
    if not previous.refresh_token:
        raise SocialError('SOCIAL_REAUTH_REQUIRED','Dauerhafte Zustimmung fehlt. Das Konto erneut verbinden.')
    body=credentials(provider,config.providers[provider])
    body.update(grant_type='refresh_token',refresh_token=previous.refresh_token)
    result=parse_tokens(remote(client,'POST',TOKEN[provider],data=body),previous)
    if provider=='tiktok' and result.open_id!=previous.open_id:
        raise SocialError('SOCIAL_ACCOUNT_CHANGED','Die erneuerten Tokens gehören zu einem anderen Konto.')
    return result


def account(provider, tokens, client):
    params={'part':'snippet','mine':'true','maxResults':'2'} if provider=='youtube' else {'fields':'open_id,display_name'}
    value=remote(client,'GET',ACCOUNT[provider],params=params,headers={'Authorization':'Bearer '+tokens.access_token})
    try:
        if provider=='youtube':
            items=value['items']
            if len(items)!=1: raise ValueError('missing or ambiguous channel')
            identity,title=items[0]['id'],items[0]['snippet']['title']
        else:
            user=value['data']['user']; identity,title=user['open_id'],user['display_name']
            if identity!=tokens.open_id: raise ValueError('wrong TikTok account')
        if not isinstance(identity,str) or not 1<=len(identity)<=300 or not isinstance(title,str) or not 1<=len(title)<=300:
            raise ValueError('invalid identity')
        return identity,title
    except (KeyError, ValueError, TypeError) as exc:
        raise SocialError('SOCIAL_ACCOUNT_INELIGIBLE','Kein eindeutig berechtigtes Zielkonto gefunden. YouTube-Kanal beziehungsweise TikTok-Kontozugang prüfen.') from exc


def revoke(provider, config, tokens, client):
    body={'token':tokens.refresh_token or tokens.access_token}
    if provider=='tiktok': body=dict(credentials(provider,config.providers[provider]),token=tokens.access_token)
    remote(client,'POST',REVOKE[provider],data=body)
