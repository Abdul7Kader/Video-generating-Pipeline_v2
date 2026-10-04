"""Verified, non-destructive changes of the installation's media directory."""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import UUID, uuid4
from app.media import checksum, media_root, write_json
from app.production_stages import StageFailure

MARKER = '.video-pipeline-store.json'
LEGACY_DIRS = {'projects','sources','speech','graphics','encoding','pexels-search'}


def storage_lock(conn, shared=False):
    function='pg_try_advisory_lock_shared' if shared else 'pg_try_advisory_lock'
    return conn.execute(f"SELECT {function}(hashtextextended(current_schema() || ':media-storage',13)) AS locked").fetchone()['locked']


def config_path():
    return Path(os.environ.get('WORKER_CONFIG_PATH') or Path.home()/'.config/video-pipeline/worker.json')


def private_write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    part = path.with_suffix('.json.part')
    try:
        with part.open('w',encoding='utf-8') as output:
            json.dump(value,output,ensure_ascii=False,indent=2)
            output.flush(); os.fsync(output.fileno())
        if os.name == 'nt':
            flags={'creationflags':subprocess.CREATE_NO_WINDOW}
            identity=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True,**flags)
            sid=next(csv.reader([identity.strip()]))[1]
            if not re.fullmatch(r'S-1-[0-9-]+',sid): raise ValueError('invalid identity')
            subprocess.run(['icacls',str(part),'/inheritance:r','/grant:r',f'*{sid}:(F)','*S-1-5-18:(F)'],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,**flags)
        else:
            part.chmod(0o600)
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def initialize_store():
    root=media_root()
    config=config_path()
    if config.exists():
        settings=json.loads(config.read_text(encoding='utf-8'))
    else:
        # Preserve environment-only installations when creating their UI settings.
        names=('DATABASE_URL','REDIS_URL','PEXELS_API_KEY','MEDIA_ROOT','FFPROBE_PATH','FFMPEG_PATH',
               'PIPER_MODEL_PATH','REMOTION_NODE_PATH','REMOTION_BROWSER_EXECUTABLE')
        settings={name:os.environ[name] for name in names if os.environ.get(name)}
    marker=root/MARKER
    if marker.exists():
        identity=str(UUID(json.loads(marker.read_text(encoding='utf-8'))['store_id']))
        if settings.get('MEDIA_STORE_ID') and settings['MEDIA_STORE_ID'] != identity:
            raise StageFailure('STORAGE_ID_MISMATCH','Der gewählte Ordner gehört zu einer anderen Pipeline-Installation.')
    else:
        if any(p.name not in LEGACY_DIRS for p in root.iterdir()):
            raise StageFailure('STORAGE_NOT_EMPTY','Der bisherige Medienordner enthält fremde Dateien. Einen eigenen Pipeline-Ordner verwenden.')
        identity=str(uuid4())
        write_json(marker,{'schema_version':1,'store_id':identity})
    if settings.get('MEDIA_STORE_ID') != identity or settings.get('MEDIA_ROOT') != str(root):
        settings.update(MEDIA_STORE_ID=identity,MEDIA_ROOT=str(root))
        private_write(config,settings)
    os.environ['MEDIA_ROOT']=str(root)
    return identity


def chosen_path(value):
    if not isinstance(value,str) or not value.strip() or any(c in value for c in ('\0','\r','\n')):
        raise StageFailure('STORAGE_PATH_INVALID','Bitte einen vollständigen Ordnerpfad eingeben.')
    path=Path(value.strip()).expanduser()
    if not path.is_absolute() or path == Path(path.anchor):
        raise StageFailure('STORAGE_PATH_INVALID','Bitte einen vollständigen Unterordner wählen, kein ganzes Laufwerk.')
    # A chosen root may not secretly redirect through a junction or symlink.
    for item in (path,*path.parents):
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise StageFailure('STORAGE_PATH_INVALID','Bitte einen direkten Ordnerpfad ohne Verknüpfungen wählen.')
    return path.resolve()


def store_files(root):
    files=[]
    for item in root.rglob('*'):
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()) or not item.resolve().is_relative_to(root):
            raise StageFailure('STORAGE_PATH_INVALID','Verknüpfte Dateien können nicht sicher übernommen werden.')
        if item.is_file() and item.name != MARKER:
            files.append(item)
    return files


def copy_store(source, target, identity, progress):
    """Copy only an owned tree; never delete the source or replace conflicts."""
    source=source.resolve(); target=chosen_path(str(target))
    if target == source:
        progress(0,0); return
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise StageFailure('STORAGE_PATH_INVALID','Bisheriger und neuer Speicher dürfen nicht ineinander liegen.')
    if json.loads((source/MARKER).read_text(encoding='utf-8')).get('store_id') != identity:
        raise StageFailure('STORAGE_ID_MISMATCH','Die Herkunft des bisherigen Speichers ist nicht bestätigt.')
    marker=target/MARKER
    if marker.is_symlink() or (hasattr(marker,'is_junction') and marker.is_junction()):
        raise StageFailure('STORAGE_PATH_INVALID','Verknüpfte Speicher können nicht übernommen werden.')
    if target.exists() and any(target.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('store_id') != identity:
            raise StageFailure('STORAGE_NOT_EMPTY','Der neue Ordner enthält bereits fremde Dateien. Einen leeren Pipeline-Ordner wählen.')
    target.mkdir(parents=True,exist_ok=True)
    if not marker.exists(): write_json(marker,{'schema_version':1,'store_id':identity})
    files=store_files(source)
    total=sum(p.stat().st_size for p in files)
    done=0; progress(total,done)
    for path in files:
        destination=target/path.relative_to(source)
        if destination.is_symlink() or not destination.resolve().is_relative_to(target):
            raise StageFailure('STORAGE_PATH_INVALID','Der Zielpfad liegt außerhalb des neuen Speichers.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        expected=checksum(path)
        if destination.exists():
            if not destination.is_file() or checksum(destination) != expected:
                raise StageFailure('STORAGE_FILE_CONFLICT','Im Ziel liegt eine abweichende Datei. Es wurde nichts überschrieben.')
        else:
            part=destination.with_name(destination.name+'.copy-part')
            if part.is_symlink() or not part.resolve().is_relative_to(target):
                raise StageFailure('STORAGE_PATH_INVALID','Eine verknüpfte Teildatei kann nicht übernommen werden.')
            try:
                with path.open('rb') as incoming, part.open('wb') as outgoing:
                    while data:=incoming.read(1024*1024): outgoing.write(data)
                    outgoing.flush(); os.fsync(outgoing.fileno())
                if checksum(part) != expected:
                    raise StageFailure('STORAGE_COPY_INVALID','Eine Datei konnte nicht unverändert übernommen werden.')
                part.replace(destination)
            finally:
                part.unlink(missing_ok=True)
        done+=path.stat().st_size; progress(total,done)


def activate_store(path, identity):
    settings=json.loads(config_path().read_text(encoding='utf-8'))
    settings.update(MEDIA_ROOT=str(path),MEDIA_STORE_ID=identity)
    private_write(config_path(),settings)
    os.environ['MEDIA_ROOT']=str(path)
