"""Private local installation settings. No credentials in API payloads."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, field_validator

PLATFORMS = {'youtube':'YouTube','tiktok':'TikTok','instagram':'Instagram','facebook':'Facebook','x':'X'}


class SocialError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    client_id: str = Field(min_length=1, max_length=500)
    client_secret: SecretStr = Field(min_length=1, max_length=2000)
    enabled: bool = Field(default=False, strict=True)
    zero_cost_confirmed: bool = Field(default=False, strict=True)
    checked_at: AwareDatetime | None = None
    review_status: Literal['UNVERIFIED','TEST_ONLY','APPROVED'] = 'UNVERIFIED'
    public_upload_approved: bool = Field(default=False, strict=True)
    public_creator_app_confirmed: bool = Field(default=False, strict=True)
    upload_enabled: bool = Field(default=False, strict=True)
    account_reference: str = Field(default='', max_length=300)


class SocialConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    origin: str = 'http://127.0.0.1:4177'
    video_mvp_accepted: bool = Field(default=False, strict=True)
    providers: dict[Literal['youtube','tiktok'], ProviderConfig] = Field(default_factory=dict)

    @field_validator('origin')
    @classmethod
    def local_origin(cls, value):
        uri=urlsplit(value)
        if (uri.scheme not in ('http','https') or uri.hostname not in ('localhost','127.0.0.1')
                or not uri.port or uri.username or uri.password or uri.path or uri.query or uri.fragment):
            raise ValueError('Only a fixed loopback origin with explicit port is supported')
        return value

    def callback(self, provider):
        return self.origin+f'/api/connections/{provider}/callback'


def load_config():
    path=os.environ.get('SOCIAL_CONFIG_PATH')
    if not path: return None
    try:
        if Path(path).stat().st_size > 32768: raise ValueError('oversized config')
        return SocialConfig.model_validate_json(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise SocialError('SOCIAL_CONFIG_INVALID','Die private Plattformkonfiguration ist ungültig.') from exc


def blockers(provider, config, now=None):
    if provider == 'x': return ['X benötigt zuerst eine gesonderte Kostenentscheidung.']
    if provider in ('facebook','instagram'):
        return ['Meta-Verbindung noch offen: eigene Entwickler-App, passende Seite beziehungsweise professionelles Instagram-Konto und App-Rechte prüfen.']
    if provider not in ('youtube','tiktok'): return ['Unbekannte Plattform.']
    if not config: return ['Eigene Entwickler-App und private Plattformkonfiguration fehlen.']
    entry=config.providers.get(provider)
    result=[]
    if not config.video_mvp_accepted: result.append('Die echte CLOUD-Videoabnahme steht noch aus.')
    if not entry: return result+['OAuth-Zugang der eigenen Entwickler-App fehlt.']
    if not entry.enabled: result.append('Die Verbindung ist in der privaten Konfiguration deaktiviert.')
    now=now or datetime.now(timezone.utc)
    if (not entry.zero_cost_confirmed or not entry.checked_at
            or not 0 <= (now-entry.checked_at).total_seconds() <= 86400 or not entry.account_reference.strip()):
        result.append('Aktueller Kontonachweis für kostenfreie API-Nutzung fehlt; vor dem Verbinden prüfen.')
    if entry.review_status == 'UNVERIFIED': result.append('App-Rechte und freigegebene Testkonten sind noch nicht geprüft.')
    return result


if __name__ == '__main__':
    import argparse
    from getpass import getpass
    from app.storage_settings import private_write
    parser=argparse.ArgumentParser(description='Create disabled private OAuth settings; credentials never enter command arguments.')
    parser.add_argument('path',type=Path)
    parser.add_argument('--provider',action='append',choices=['youtube','tiktok'],required=True)
    parser.add_argument('--origin',default='http://127.0.0.1:4177')
    args=parser.parse_args()
    if args.path.exists(): parser.error('Existing configuration will not be replaced')
    entries={}
    try:
        for provider in dict.fromkeys(args.provider):
            entries[provider]=ProviderConfig(client_id=getpass(PLATFORMS[provider]+' Client-ID/Key: '),
                client_secret=getpass(PLATFORMS[provider]+' Client-Secret: '))
        config=SocialConfig(origin=args.origin,providers=entries)
    except (ValueError,EOFError):
        parser.error('Invalid local origin or credential input; no configuration written')
    value=config.model_dump(mode='json')
    for provider,entry in entries.items():
        value['providers'][provider]['client_secret']=entry.client_secret.get_secret_value()
    private_write(args.path,value)
    print('Private Konfiguration erstellt. Verbindungen bleiben bis zur Video- und Kontoprüfung deaktiviert.')
