"""Local storage and probing shared by media stages."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from uuid import UUID

from app.production_stages import StageFailure

ROOT = Path(__file__).resolve().parents[2]


def media_root():
    configured=os.environ.get('MEDIA_ROOT')
    if os.environ.get('WORKER_CONFIG_PATH'):
        config=Path(os.environ['WORKER_CONFIG_PATH'])
        if config.exists():
            configured=json.loads(config.read_text(encoding='utf-8')).get('MEDIA_ROOT') or configured
    root = Path(configured or ROOT / '.data' / 'media').expanduser()
    if not root.is_absolute():
        raise StageFailure('MEDIA_ROOT_INVALID', 'MEDIA_ROOT muss ein absoluter Ordnerpfad sein.')
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def safe_path(root, relative):
    """Resolve stored POSIX paths beneath the operator's configured root."""
    value = str(relative)
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or any(c in value for c in ('\\', ':', '\0')) or str(path) == '.':
        raise StageFailure('MEDIA_PATH_INVALID', 'Der gespeicherte Medienpfad ist ungültig.')
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise StageFailure('MEDIA_PATH_INVALID', 'Der Medienpfad liegt außerhalb des gewählten Speichers.')
    return resolved


def run_folder(root, context, stage):
    """New production files belong to an immutable project/version/run."""
    try:
        run = str(UUID(str(context['run_id'])))
        if 'project_id' not in context:
            # Compatibility for earlier isolated adapter contexts. The normal
            # production parent always supplies project_id and script.version.
            relative = f'{stage}/{run}'
        else:
            project = str(UUID(str(context['project_id'])))
            version = context['script']['version']
            if type(version) is not int or version < 1:
                raise ValueError('invalid version')
            relative = f'projects/{project}/versions/{version}/runs/{run}/{stage}'
        folder = safe_path(root, relative)
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise StageFailure('MEDIA_CONTEXT_INVALID', 'Projekt, Version oder Speicherordner sind ungültig.') from exc


def ffprobe_path():
    executable = os.environ.get('FFPROBE_PATH') or shutil.which('ffprobe')
    if not executable or not Path(executable).is_file():
        raise StageFailure('FFPROBE_REQUIRED', 'ffprobe fehlt. FFmpeg installieren und ffprobe im Worker-PATH oder als FFPROBE_PATH einrichten.')
    return executable


def write_json(path, value):
    part = path.with_suffix('.json.part')
    try:
        with part.open('w',encoding='utf-8') as output:
            json.dump(value,output,ensure_ascii=False)
            output.flush(); os.fsync(output.fileno())
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
