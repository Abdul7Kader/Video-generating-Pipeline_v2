"""Controlled visual input; real Piper, Remotion and FFmpeg. Tests only."""

import shutil
import subprocess

from app import production_stages
from app.media import checksum, media_root

real_stage = production_stages.execute_stage


def encoding_fixture(name, context):
    if name == 'STORAGE':
        raise production_stages.StageFailure('STAGE_UNAVAILABLE', 'Endablage bleibt in dieser isolierten Encodingprüfung deaktiviert.')
    if name != 'SCENES':
        return real_stage(name, context)
    folder = media_root()/'encoding-test-inputs'
    folder.mkdir(exist_ok=True)
    source = folder/'source.mp4'
    seconds = 2 if context['script']['title'] == 'short-source' else 8
    subprocess.run([shutil.which('ffmpeg'), '-v','error','-nostdin','-y','-f','lavfi','-i',
                    f'color=c=blue:s=480x854:r=30:d={seconds}', '-c:v','libx264','-preset','ultrafast',str(source)], check=True)
    return {'artifacts': [dict(key=f"scene_{s['position']}",kind='SOURCE',media_type=context['media_type'],
                             storage_path=source.relative_to(media_root()).as_posix(),checksum_sha256=checksum(source))
                          for s in context['scenes']]}


if __name__ == '__main__':
    production_stages.execute_stage = encoding_fixture
    production_stages.main()
