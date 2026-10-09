"""Facebook Login for Page/linked professional Instagram accounts. No uploads."""
import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode
from app.social_config import SocialError
from app.social_providers import SCOPES, remote, parse_tokens, ALLOWED

# Matched to Meta's official Python SDK configuration on 2026-10-09.
VERSION='v26.0'
GRAPH='https://graph.facebook.com/'+VERSION
TOKEN=GRAPH+'/oauth/access_token'
DEBUG=GRAPH+'/debug_token'
PERMISSIONS=GRAPH+'/me/permissions'
PAGES=GRAPH+'/me/accounts'
ALLOWED.update((TOKEN,DEBUG,PERMISSIONS,PAGES))


class GraphLogFilter(logging.Filter):
    def filter(self,record):
        # Official GET token exchanges include credentials in query strings.
        # httpx INFO logs must never retain those strings.
        if record.name=='httpx' and isinstance(record.args,tuple):
            record.args=tuple(str(arg).split('?',1)[0] if str(arg).startswith(GRAPH) else arg for arg in record.args)
        return True


logging.getLogger('httpx').addFilter(GraphLogFilter())


def authorization_url(provider,config,state):
    return 'https://www.facebook.com/'+VERSION+'/dialog/oauth?'+urlencode(dict(
        client_id=config.providers[provider].client_id,redirect_uri=config.callback(provider),
        response_type='code',state=state,scope=','.join(SCOPES[provider]),auth_type='rerequest'))


def exchange(provider,config,code,client):
    entry=config.providers[provider]
    value=remote(client,'GET',TOKEN,params=dict(client_id=entry.client_id,
        client_secret=entry.client_secret.get_secret_value(),redirect_uri=config.callback(provider),code=code))
    tokens=parse_tokens(value)
    tokens.meta_app_id=entry.client_id
    tokens.meta_page_id=entry.meta_page_id
    tokens.meta_expires_at=int(time.time())+tokens.expires_in
    return tokens


def long_lived(provider,config,tokens,client):
    entry=config.providers[provider]
    value=remote(client,'GET',TOKEN,params=dict(client_id=entry.client_id,
        client_secret=entry.client_secret.get_secret_value(),grant_type='fb_exchange_token',
        fb_exchange_token=tokens.access_token))
    if 'expires_in' not in value and 'expires' in value: value['expires_in']=value['expires']
    result=parse_tokens(value)
    result.meta_app_id=tokens.meta_app_id
    result.meta_page_id=tokens.meta_page_id
    result.meta_expires_at=int(time.time())+result.expires_in
    return result


def arguments(entry,tokens,**params):
    proof=hmac.new(entry.client_secret.get_secret_value().encode(),tokens.access_token.encode(),hashlib.sha256).hexdigest()
    return dict(params=params|{'appsecret_proof':proof},headers={'Authorization':'Bearer '+tokens.access_token})


def invalid():
    return SocialError('SOCIAL_ACCOUNT_INELIGIBLE','Meta-Zugang, Seitenrechte oder verknüpftes professionelles Instagram-Konto nicht eindeutig bestätigt.')


def account(provider,config,tokens,client):
    entry=config.providers[provider]
    if tokens.meta_app_id!=entry.client_id or tokens.meta_page_id!=entry.meta_page_id: raise invalid()
    debug=remote(client,'GET',DEBUG,params={'input_token':tokens.access_token},
        headers={'Authorization':'Bearer '+entry.client_id+'|'+entry.client_secret.get_secret_value()})
    try:
        data=debug['data'];now=int(time.time())
        expires=data['expires_at'];data_expires=data.get('data_access_expires_at',0)
        user=data['user_id']
        if (data['is_valid'] is not True or data['app_id']!=entry.client_id or data['type']!='USER'
                or type(expires) is not int or expires<=now or type(data_expires) is not int or data_expires<0
                or not isinstance(user,str) or not user.isascii() or not user.isdecimal() or not 1<=len(user)<=32
                or (tokens.meta_user_id and tokens.meta_user_id!=user)):
            raise ValueError('invalid grant')
        expiry=min(expires,tokens.meta_expires_at or expires,data_expires or expires)
        if expiry<=now: raise SocialError('SOCIAL_REAUTH_REQUIRED','Meta-Zugang abgelaufen. Zustimmung erneut erteilen.')
        scopes=data['scopes']
        if not isinstance(scopes,list) or any(not isinstance(s,str) for s in scopes): raise ValueError('invalid scopes')
        permissions=remote(client,'GET',PERMISSIONS,**arguments(entry,tokens,limit=100))
        granted={p['permission'] for p in permissions['data'] if p['status']=='granted'}
        tokens.scope=' '.join(sorted(set(scopes)&granted&set(SCOPES[provider])))
        tokens.meta_user_id=user;tokens.meta_expires_at=expiry
        selected=[];after=None;seen=set()
        # Bound pagination, construct each URL ourselves; never follow next URLs.
        for _ in range(10):
            fields='id,name,tasks'+(',instagram_business_account{id,username}' if provider=='instagram' else '')
            params={'fields':fields,'limit':100}
            if after: params['after']=after
            pages=remote(client,'GET',PAGES,**arguments(entry,tokens,**params))
            items=pages['data']
            if not isinstance(items,list): raise ValueError('invalid pages')
            selected.extend(p for p in items if p['id']==entry.meta_page_id)
            paging=pages.get('paging',{})
            if not paging.get('next'): break
            after=paging['cursors']['after']
            if not isinstance(after,str) or not 1<=len(after)<=2048 or after in seen: raise ValueError('invalid cursor')
            seen.add(after)
        else: raise ValueError('too many pages')
        if len(selected)!=1: raise ValueError('target missing or ambiguous')
        page=selected[0]
        if not {'CREATE_CONTENT','MANAGE'}&set(page['tasks']): raise ValueError('no content rights')
        if provider=='instagram':
            target=page['instagram_business_account'];identity,title=target['id'],target['username']
        else: identity,title=page['id'],page['name']
        if (not isinstance(identity,str) or not identity.isascii() or not identity.isdecimal() or not 1<=len(identity)<=32
                or not isinstance(title,str) or not 1<=len(title)<=300): raise ValueError('invalid account')
        return identity,title
    except (KeyError,ValueError,TypeError,AttributeError) as exc:
        raise invalid() from exc


def revoke(provider,config,tokens,client):
    entry=config.providers[provider]
    value=remote(client,'DELETE',PERMISSIONS,**arguments(entry,tokens))
    if value.get('success') is not True:
        raise SocialError('SOCIAL_REVOKE_FAILED','Meta hat den App-Widerruf nicht bestätigt.')
