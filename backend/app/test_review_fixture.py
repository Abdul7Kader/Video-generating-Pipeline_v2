"""Distinct controlled MP4 inputs; speech, graphics, encoding and storage are real."""
import shutil
import subprocess
from app import production_stages
from app.media import media_root, checksum
from app.test_encoding_fixture import real_stage


def review_fixture(name, context):
    if name != 'SCENES':
        return real_stage(name, context)
    root = media_root()
    folder = root / 'review-test-inputs'
    folder.mkdir(exist_ok=True)
    artifacts = []
    colors = ('blue', 'red', 'green', 'yellow', 'purple', 'white')
    for scene in context['scenes']:
        position = scene['position']
        source = folder / f'{position}.mp4'
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-y', '-f', 'lavfi', '-i',
                        f'color=c={colors[(position-1) % len(colors)]}:s=480x854:r=24:d=8',
                        '-c:v', 'libx264', '-preset', 'ultrafast', str(source)], check=True)
        artifacts.append(dict(key=f'scene_{position}', kind='SOURCE', media_type=context['media_type'],
                              storage_path=source.relative_to(root).as_posix(), checksum_sha256=checksum(source)))
    return dict(artifacts=artifacts)


if __name__ == '__main__':
    production_stages.execute_stage = review_fixture
    production_stages.main()
