"""Local publication drafts and immutable provider metadata, without uploads."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.production_stages import PexelsSource
from app.wan_contract import WanSceneSource

Platform=Literal['youtube','tiktok','instagram','facebook','x']
Visibility=Literal['private','unlisted','public','SELF_ONLY','MUTUAL_FOLLOW_FRIENDS','FOLLOWER_OF_CREATOR','PUBLIC_TO_EVERYONE']


class Target(BaseModel):
    model_config=ConfigDict(extra='forbid')
    visibility: Visibility


class Metadata(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(min_length=1,max_length=100)
    description: str=Field(default='',max_length=2000)
    synthetic_media: bool=Field(default=False,strict=True)
    made_for_kids: bool=Field(strict=True)
    paid_partnership: bool=Field(default=False,strict=True)
    own_brand: bool=Field(default=False,strict=True)
    allow_comments: bool=Field(default=False,strict=True)
    allow_duet: bool=Field(default=False,strict=True)
    allow_stitch: bool=Field(default=False,strict=True)
    tiktok_music_confirmed: bool=Field(default=False,strict=True)
    tiktok_brand_policy_confirmed: bool=Field(default=False,strict=True)
    targets: dict[Platform,Target]=Field(default_factory=dict,max_length=5)

    @field_validator('title','description')
    @classmethod
    def safe_text(cls,value):
        if any(ord(c)<32 and c not in '\n\t' for c in value) or '<' in value or '>' in value:
            raise ValueError('Invalid publishing text')
        return value.strip()

    @field_validator('title')
    @classmethod
    def not_blank(cls,value):
        if not value: raise ValueError('Title required')
        return value


class DraftInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=0,strict=True)
    checksum_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    metadata: Metadata


class ReleaseInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=1,strict=True)
    checksum_sha256: str=Field(pattern='^[a-f0-9]{64}$')
    reviewed_metadata: Literal[True]
    reviewed_sources: Literal[True]
    consent_to_publish: Literal[True]

    @field_validator('reviewed_metadata','reviewed_sources','consent_to_publish',mode='before')
    @classmethod
    def explicit(cls,value):
        if value is not True: raise ValueError('Explicit confirmation required')
        return value


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def profile(provider,metadata,credits,mode):
    synthetic=metadata.synthetic_media or mode=='CLOUD'
    description='\n\n'.join(s for s in [metadata.description,credits] if s)
    visibility=metadata.targets[provider].visibility
    if provider=='youtube':
        if visibility not in ('private','unlisted','public') or len(description.encode('utf-8'))>5000:
            raise ValueError('YouTube visibility or description invalid')
        return dict(snippet=dict(title=metadata.title,description=description),
            status=dict(privacyStatus=visibility,containsSyntheticMedia=synthetic,selfDeclaredMadeForKids=metadata.made_for_kids),
            paidProductPlacementDetails=dict(hasPaidProductPlacement=metadata.paid_partnership))
    if provider=='tiktok':
        caption='\n\n'.join(s for s in [metadata.title,description] if s)
        if visibility not in ('SELF_ONLY','MUTUAL_FOLLOW_FRIENDS','FOLLOWER_OF_CREATOR','PUBLIC_TO_EVERYONE') or len(caption.encode('utf-16-le'))//2>2200:
            raise ValueError('TikTok visibility or caption invalid')
        if metadata.paid_partnership and visibility=='SELF_ONLY':
            raise ValueError('TikTok paid partnership cannot be private')
        return dict(post_info=dict(title=caption,privacy_level=visibility,is_aigc=synthetic,
            brand_content_toggle=metadata.paid_partnership,brand_organic_toggle=metadata.own_brand,
            disable_comment=not metadata.allow_comments,disable_duet=not metadata.allow_duet,disable_stitch=not metadata.allow_stitch))
    raise ValueError('Platform profile not implemented')


def source_provenance(mode,positions,value):
    field='sources' if mode=='LOKAL' else 'wan_sources'
    other='wan_sources' if mode=='LOKAL' else 'sources'
    model=PexelsSource if mode=='LOKAL' else WanSceneSource
    sources=[model.model_validate(s) for s in value.get(field,[])]
    if not positions or len(sources)!=len(positions) or {s.scene_position for s in sources}!=set(positions) or value.get(other):
        raise ValueError('Incomplete or mixed source provenance')
    if any(s.artifact_key!=f'scene_{s.scene_position}' for s in sources): raise ValueError('Source scene mismatch')
    if mode=='CLOUD' and any(c.request.scene_position!=s.scene_position for s in sources for c in s.clips):
        raise ValueError('Clip scene mismatch')
    controlled=mode=='CLOUD' and any(c.execution=='CONTROLLED_TEST' for s in sources for c in s.clips)
    credits=('Videoquellen: Pexels\n'+'\n'.join(f'{s.creator}: {s.video_page}' for s in sources)+'\nhttps://www.pexels.com/license/') if mode=='LOKAL' else 'Visuelle Szenen mit KI erzeugt (Wan 2.2).'
    return dict(mode=mode,sources=value.get('sources',[]),wan_sources=value.get('wan_sources',[]),credits=credits,controlled_test=controlled)
