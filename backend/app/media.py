"""Local storage and probing shared by media stages."""

import hashlib
import json
import os
from pathlib import Path
import shutil

from app.production_stages import StageFailure

ROOT = Path(__file__).resolve().parents[2]


def media_root():
    root = Path(os.environ.get('MEDIA_ROOT') or ROOT / '.data' / 'media').expanduser()
    if not root.is_absolute():
        raise StageFailure('MEDIA_ROOT_INVALID', 'MEDIA_ROOT muss ein absoluter Ordnerpfad sein.')
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def ffprobe_path():
    executable = os.environ.get('FFPROBE_PATH') or shutil.which('ffprobe')
    if not executable or not Path(executable).is_file():
        raise StageFailure('FFPROBE_REQUIRED', 'ffprobe fehlt. FFmpeg installieren und ffprobe im Worker-PATH oder als FFPROBE_PATH einrichten.')
    return executable


def write_json(path, value):
    part = path.with_suffix('.json.part')
    try:
        part.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
