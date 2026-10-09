"""Save and approve exact publication metadata; explicitly start guarded uploads."""
from datetime import datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,Response
from psycopg.types.json import Jsonb
from redis.exceptions import RedisError
from app.api import require_project
from app.database import database
from app.media_access import require_access,same_origin,denied
from app.media_gateway import rpc
from app.production_stages import StageFailure
from app.publication_contract import DraftInput,ReleaseInput,Metadata,digest,profile,source_provenance
from app.social_config import PLATFORMS,SocialError,load_config,blockers
from app.social_api import configuration,require_origin,connection,stored_tokens,lock
from app import social_providers as providers

router=APIRouter(prefix='/api/projects/{project_id}/videos/{artifact_id}/publication')


def video(conn,project_id,artifact_id):
    require_project(conn,project_id,lock=True)
    row=conn.execute("SELECT a.*,r.script_version_id,r.state AS production_state,p.mode,s.title "
        "FROM artifacts a JOIN production_runs r ON r.id=a.production_run_id JOIN projects p ON p.id=a.project_id "
        "JOIN script_versions s ON s.id=r.script_version_id WHERE a.id=%s AND a.project_id=%s FOR UPDATE OF a",
        (artifact_id,project_id)).fetchone()
    if not row or row['kind']!='FINAL': raise denied(404,'ARTIFACT_NOT_FOUND','Fertiges Video nicht gefunden.')
    latest=conn.execute('SELECT id FROM script_versions WHERE project_id=%s ORDER BY version DESC LIMIT 1',(project_id,)).fetchone()
    if row['production_state']!='COMPLETED' or latest['id']!=row['script_version_id']:
        raise denied(409,'VIDEO_VERSION_OUTDATED','Bitte das Video der neuesten Skriptversion verwenden.')
    return row


def verify_file(row):
    try:
        opened=rpc('open',artifact_id=str(row['id']))
        try:
            if opened['checksum']!=row['checksum_sha256']:
                raise denied(409,'ARTIFACT_CONFLICT','Die Videodatei stimmt nicht mehr mit der Freigabe überein.')
        finally: rpc('close',stream=opened['stream'])
    except StageFailure as exc:
        raise denied(409 if exc.code=='MEDIA_CORRUPT' else 503,exc.code,str(exc)) from exc
    except (RedisError,OSError) as exc:
        raise denied(503,'MEDIA_WORKER_UNAVAILABLE','Der Medien-Worker ist momentan nicht verfügbar.') from exc


def provenance(conn,row):
    stage=conn.execute("SELECT result FROM production_steps WHERE production_run_id=%s AND name='SCENES' AND state='COMPLETED'",(row['production_run_id'],)).fetchone()
    value=stage['result'] if stage else {}
    positions=[s['position'] for s in conn.execute('SELECT position FROM scenes WHERE script_version_id=%s ORDER BY position',(row['script_version_id'],))]
    try: return source_provenance(row['mode'],positions,value)
    except (ValueError,TypeError) as exc:
        raise denied(409,'PUBLICATION_SOURCES_MISSING','Vollständige und passende Szenenherkunft fehlt. Bitte die Quellen prüfen.') from exc


def readiness(conn):
    try: config=load_config()
    except SocialError: config=None
    result=[];now=datetime.now(timezone.utc)
    for provider,label in PLATFORMS.items():
        problems=blockers(provider,config)
        if provider in ('facebook','instagram'):
            problems.append('Veröffentlichungsadapter noch offen; die Kontoverbindung startet keinen Upload.')
        if provider=='tiktok' and (not config or not config.providers.get(provider) or not config.providers[provider].public_creator_app_confirmed):
            problems.append('TikTok Direct Post erlaubt keine reine Eigen-/Teamkonto-Utility. Zulässigen Nutzungskreis der Entwickler-App zuerst nachweisen.')
        row=conn.execute('SELECT * FROM social_connections WHERE provider=%s',(provider,)).fetchone()
        if not row or row['state']!='CONNECTED' or not row['expires_at'] or row['expires_at']<=now:
            problems.append('Verbundenes Zielkonto mit gültigem Zugang und allen Rechten fehlt.')
        if not problems:
            try:
                _,key=configuration(provider);connection(conn,provider,config);stored_tokens(key,row)
            except Exception as exc:
                # Only known access/configuration failures become a safe hint.
                from fastapi import HTTPException
                if not isinstance(exc,(HTTPException,SocialError)): raise
                problems.append('Zugang oder private Konfiguration muss geprüft werden.')
        result.append(dict(provider=provider,label=label,ready=not problems,problems=problems,
            account_title=row['account_title'] if row and row['tokens_encrypted'] else None))
    return result


def bindings_match(conn,release):
    for provider,target in release['snapshot']['targets'].items():
        try:
            source=release['snapshot']['provenance']
            expected=profile(provider,Metadata.model_validate(release['snapshot']['metadata']),source['credits'],source['mode'])
            if expected!=target['profile']: return False
        except (ValueError,KeyError,TypeError): return False
        row=conn.execute('SELECT * FROM social_connections WHERE provider=%s',(provider,)).fetchone()
        if not row or row['state']!='CONNECTED' or any(str(row[key])!=str(target[key]) for key in ('account_id','config_fingerprint')) or str(row['id'])!=target['connection_id']:
            return False
    return True


def state(conn,row):
    draft=conn.execute('SELECT * FROM publication_drafts WHERE artifact_id=%s',(row['id'],)).fetchone()
    jobs=conn.execute('SELECT p.id,p.platform,p.state,p.release_id,p.external_id,p.error_message,u.phase,u.confirmed_bytes,u.size_bytes,u.actual_visibility,u.error_code,u.available_at '
        'FROM platform_publications p LEFT JOIN youtube_uploads u ON u.publication_id=p.id WHERE p.artifact_id=%s ORDER BY p.platform',(row['id'],)).fetchall()
    source=provenance(conn,row)
    metadata=Metadata.model_validate(draft['metadata']).model_dump(mode='json') if draft else Metadata(title=row['title'],made_for_kids=False,synthetic_media=row['mode']=='CLOUD').model_dump(mode='json')
    release=conn.execute('SELECT * FROM publication_releases WHERE artifact_id=%s ORDER BY revision DESC LIMIT 1',(row['id'],)).fetchone()
    platforms=readiness(conn)
    valid=bool(release and not release['invalidated_at'] and draft and release['revision']==draft['revision'] and draft['provenance_hash']==digest(source) and draft['checksum_sha256']==row['checksum_sha256'])
    valid=valid and bindings_match(conn,release) and all(p['ready'] for p in platforms if p['provider'] in metadata['targets'])
    return dict(checksum_sha256=row['checksum_sha256'],revision=draft['revision'] if draft else 0,metadata=metadata,
        provenance=source,platforms=platforms,release_id=release['id'] if valid else None,jobs=jobs,
        upload_available=youtube_available())


def youtube_available():
    try:
        config=load_config()
        return bool(config and not blockers('youtube',config) and config.providers['youtube'].upload_enabled)
    except SocialError: return False


@router.get('')
def get_publication(project_id:UUID,artifact_id:UUID,request:Request):
    require_access(request)
    with database() as conn:
        row=video(conn,project_id,artifact_id);verify_file(row)
        return state(conn,row)


@router.put('')
def save_draft(project_id:UUID,artifact_id:UUID,body:DraftInput,request:Request):
    require_access(request);same_origin(request)
    with database() as conn:
        row=video(conn,project_id,artifact_id)
        if row['checksum_sha256']!=body.checksum_sha256: raise denied(409,'ARTIFACT_CONFLICT','Die Videodatei hat sich geändert.')
        source=provenance(conn,row);metadata=body.metadata.model_dump(mode='json')
        if row['mode']=='CLOUD': metadata['synthetic_media']=True
        draft=conn.execute('SELECT * FROM publication_drafts WHERE artifact_id=%s FOR UPDATE',(artifact_id,)).fetchone()
        revision=draft['revision'] if draft else 0
        if revision!=body.expected_revision: raise denied(409,'PUBLICATION_VERSION_CONFLICT','Der Entwurf wurde geändert. Bitte neu laden.')
        previous_release=conn.execute('SELECT * FROM publication_releases WHERE artifact_id=%s AND revision=%s',(artifact_id,revision)).fetchone()
        if draft and draft['metadata']==metadata and draft['checksum_sha256']==body.checksum_sha256 and draft['provenance_hash']==digest(source) and (not previous_release or bindings_match(conn,previous_release)):
            return state(conn,row)
        if conn.execute("SELECT 1 FROM platform_publications WHERE artifact_id=%s AND state<>'QUEUED'",(artifact_id,)).fetchone():
            raise denied(409,'PUBLICATION_STARTED','Ein Auftrag wurde bereits gestartet. Seine freigegebenen Angaben bleiben unverändert.')
        conn.execute('DELETE FROM platform_publications WHERE artifact_id=%s',(artifact_id,))
        conn.execute('UPDATE publication_releases SET invalidated_at=now() WHERE artifact_id=%s AND invalidated_at IS NULL',(artifact_id,))
        conn.execute('INSERT INTO publication_drafts(artifact_id,revision,checksum_sha256,provenance_hash,metadata) VALUES (%s,%s,%s,%s,%s) '
            'ON CONFLICT(artifact_id) DO UPDATE SET revision=EXCLUDED.revision,checksum_sha256=EXCLUDED.checksum_sha256,provenance_hash=EXCLUDED.provenance_hash,metadata=EXCLUDED.metadata,updated_at=now()',
            (artifact_id,revision+1,body.checksum_sha256,digest(source),Jsonb(metadata)))
        return state(conn,row)


def eligible(conn,provider,request):
    if provider not in ('youtube','tiktok'):
        raise denied(409,'PUBLICATION_ADAPTER_UNAVAILABLE','Der Veröffentlichungsadapter für diese Plattform ist noch offen.')
    config,key=configuration(provider);require_origin(request,config);lock(conn,provider)
    if provider=='tiktok' and not config.providers[provider].public_creator_app_confirmed:
        raise denied(409,'PUBLICATION_TIKTOK_USE_BLOCKED','TikTok Direct Post erlaubt keine reine Eigen-/Teamkonto-Utility. Zulässigen Nutzungskreis der App zuerst prüfen.')
    row=connection(conn,provider,config)
    if row['state']!='CONNECTED' or not row['expires_at'] or row['expires_at']<=datetime.now(timezone.utc) or not set(providers.SCOPES[provider])<=set(row['scopes']):
        raise denied(409,'PUBLICATION_CONNECTION_INVALID','Zielkonto erneuern und fehlende Berechtigungen prüfen.')
    return config,row,stored_tokens(key,row)


@router.post('/options/{provider}')
def options(project_id:UUID,artifact_id:UUID,provider:str,request:Request):
    require_access(request);same_origin(request)
    try:
        with database() as conn:
            video(conn,project_id,artifact_id);config,row,tokens=eligible(conn,provider,request)
            entry=config.providers[provider]
            if provider=='youtube': choices=['private']+(['unlisted','public'] if entry.public_upload_approved and entry.review_status=='APPROVED' else [])
            else:
                with providers.http_client() as client: info=providers.creator_info(tokens,client)
                choices=[v for v in info.privacy_level_options if v in ('SELF_ONLY','MUTUAL_FOLLOW_FRIENDS','FOLLOWER_OF_CREATOR','PUBLIC_TO_EVERYONE')]
                if not entry.public_upload_approved or entry.review_status!='APPROVED': choices=[v for v in choices if v=='SELF_ONLY']
            return dict(choices=choices,account_title=info.creator_nickname if provider=='tiktok' else row['account_title'],interactions=dict(
                allow_comments=not info.comment_disabled,allow_duet=not info.duet_disabled,allow_stitch=not info.stitch_disabled) if provider=='tiktok' else {})
    except SocialError as exc: raise denied(409,exc.code,exc.message) from exc


@router.post('/approval',status_code=201)
def approve_publication(project_id:UUID,artifact_id:UUID,body:ReleaseInput,request:Request,response:Response):
    require_access(request);same_origin(request)
    try:
        with database() as conn:
            row=video(conn,project_id,artifact_id);verify_file(row);source=provenance(conn,row)
            draft=conn.execute('SELECT * FROM publication_drafts WHERE artifact_id=%s FOR UPDATE',(artifact_id,)).fetchone()
            if not draft or draft['revision']!=body.expected_revision or draft['checksum_sha256']!=body.checksum_sha256 or row['checksum_sha256']!=body.checksum_sha256 or draft['provenance_hash']!=digest(source):
                raise denied(409,'PUBLICATION_VERSION_CONFLICT','Datei, Herkunft oder Entwurf geändert. Bitte erneut prüfen und speichern.')
            approval=conn.execute("SELECT id FROM approvals WHERE artifact_id=%s AND kind='VIDEO' AND checksum_sha256=%s",(artifact_id,body.checksum_sha256)).fetchone()
            if not approval: raise denied(409,'VIDEO_APPROVAL_REQUIRED','Bitte zuerst Bild und Ton des Videos freigeben.')
            metadata=Metadata.model_validate(draft['metadata'])
            if source['controlled_test']: raise denied(409,'PUBLICATION_TEST_VIDEO','Kontrollierte Testclips sind kein echtes Veröffentlichungsvideo.')
            if not metadata.targets: raise denied(409,'PUBLICATION_TARGET_REQUIRED','Mindestens eine berechtigte Zielplattform wählen.')
            targets={}
            for provider in sorted(metadata.targets):
                config,connected,tokens=eligible(conn,provider,request)
                try: prepared=profile(provider,metadata,source['credits'],row['mode'])
                except ValueError as exc: raise denied(409,'PUBLICATION_PROFILE_INVALID',str(exc)) from exc
                visibility=metadata.targets[provider].visibility
                if visibility not in ('private','SELF_ONLY') and (not config.providers[provider].public_upload_approved or config.providers[provider].review_status!='APPROVED'):
                    raise denied(409,'PUBLICATION_PRIVATE_ONLY','Die App ist nur für private Testveröffentlichungen freigegeben.')
                if provider=='tiktok':
                    if not metadata.tiktok_music_confirmed or (metadata.paid_partnership and not metadata.tiktok_brand_policy_confirmed):
                        raise denied(409,'PUBLICATION_TIKTOK_CONSENT','Bitte TikTok-Musikbedingungen und gegebenenfalls die Branded Content Policy bestätigen.')
                    with providers.http_client() as client: info=providers.creator_info(tokens,client)
                    if any(getattr(metadata,'allow_'+name) and getattr(info,('comment' if name=='comments' else name)+'_disabled') for name in ('comments','duet','stitch')):
                        raise denied(409,'PUBLICATION_CREATOR_LIMIT','TikTok erlaubt eine ausgewählte Interaktion aktuell nicht.')
                    encoding=conn.execute("SELECT result FROM production_steps WHERE production_run_id=%s AND name='ENCODING' AND state='COMPLETED'",(row['production_run_id'],)).fetchone()
                    duration=(encoding['result'] or {}).get('encoding',{}).get('duration_seconds') if encoding else None
                    if visibility not in info.privacy_level_options or not isinstance(duration,(float,int)) or duration>info.max_video_post_duration_sec:
                        raise denied(409,'PUBLICATION_CREATOR_LIMIT','TikTok erlaubt diese Sichtbarkeit oder Videodauer aktuell nicht.')
                targets[provider]=dict(profile=prepared,connection_id=str(connected['id']),account_id=connected['account_id'],config_fingerprint=connected['config_fingerprint'])
            snapshot=dict(metadata=metadata.model_dump(mode='json'),provenance=source,targets=targets)
            release=conn.execute('SELECT * FROM publication_releases WHERE artifact_id=%s AND revision=%s',(artifact_id,draft['revision'])).fetchone()
            if release:
                if release['invalidated_at'] or release['snapshot']!=snapshot: raise denied(409,'PUBLICATION_CONNECTION_CHANGED','Zielkonto oder Freigabe geändert. Entwurf erneut speichern und prüfen.')
                response.status_code=200
            else:
                release=conn.execute('INSERT INTO publication_releases(artifact_id,revision,checksum_sha256,snapshot) VALUES (%s,%s,%s,%s) RETURNING *',
                    (artifact_id,draft['revision'],body.checksum_sha256,Jsonb(snapshot))).fetchone()
                for provider,target in targets.items():
                    conn.execute('INSERT INTO platform_publications(project_id,artifact_id,video_approval_id,platform,release_id,snapshot) VALUES (%s,%s,%s,%s,%s,%s)',
                        (project_id,artifact_id,approval['id'],provider.upper(),release['id'],Jsonb(target)))
            return dict(release_id=release['id'],revision=release['revision'],jobs=state(conn,row)['jobs'],upload_available=youtube_available())
    except SocialError as exc: raise denied(409,exc.code,exc.message) from exc


@router.post('/jobs/{publication_id}/youtube',status_code=202)
def start_youtube(project_id:UUID,artifact_id:UUID,publication_id:UUID,request:Request):
    require_access(request);same_origin(request)
    from app import youtube_jobs as jobs
    from app.youtube_upload import UploadError
    try:
        with database() as conn:
            if not jobs.try_lock(conn,publication_id): raise denied(409,'YOUTUBE_BUSY','Der YouTube-Auftrag läuft bereits.')
            job,row,_,_=jobs.validate(conn,publication_id,project_id,artifact_id)
            config,_=configuration('youtube');require_origin(request,config)
            upload=conn.execute('SELECT * FROM youtube_uploads WHERE publication_id=%s',(publication_id,)).fetchone()
            if upload and upload['phase'] in ('UNKNOWN','INITIATING'):
                raise denied(409,'YOUTUBE_RESULT_UNKNOWN','Upload-Start nicht eindeutig bestätigt. Ergebnis zuerst im Zielkonto klären.')
            if job['state']=='PUBLISHED': return {'state':'PUBLISHED'}
            opened=jobs.verified_open(row)
            try:
                if upload and opened['size']!=upload['size_bytes']: raise denied(409,'ARTIFACT_CONFLICT','Die Dateigröße hat sich geändert.')
                if not upload:
                    conn.execute('INSERT INTO youtube_uploads(publication_id,size_bytes) VALUES (%s,%s)',(publication_id,opened['size']))
                elif job['state']=='FAILED':
                    # Manual retry preserves session/external ID and backoff.
                    conn.execute('UPDATE youtube_uploads SET retries=0,poll_count=0,error_code=NULL WHERE publication_id=%s',(publication_id,))
                conn.execute("UPDATE platform_publications SET state='UPLOADING',error_message=NULL,updated_at=now() WHERE id=%s",(publication_id,))
            finally: rpc('close',stream=opened['stream'])
        try: jobs.enqueue_pending();queued=True
        except (RedisError,OSError): queued=False
        return {'state':'UPLOADING','worker_queued':queued}
    except (SocialError,StageFailure,UploadError) as exc:
        raise denied(409,exc.code,exc.message if isinstance(exc,SocialError) else str(exc)) from exc
