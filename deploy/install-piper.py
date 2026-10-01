"""Install the pinned German Piper voice into an ignored local model directory."""

import argparse
import hashlib
from pathlib import Path
import time
from urllib.request import urlopen

REVISION = 'c10ece1aade47bb51c153c893d14e5bf8e5b7117'
BASE = f'https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}/de/de_DE/thorsten/high/'
FILES = {
    'de_DE-thorsten-high.onnx': '9df1c43c61149ef9b39e618e2b861fbe41e1fcea9390b2dac62e8761573ea4f1',
    'de_DE-thorsten-high.onnx.json': '6de734444e4c3f9e33b7ebe2746dbc19b71e85f613e79c65acf623200b99a76a',
    'MODEL_CARD': 'a49334fc36286c9d67f007605969a33f416cc4e35eb770c9c7f716d44711fc3a',
}


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = directory / name
        if target.is_file() and checksum(target) == expected:
            print(f'Geprüft: {name}', flush=True)
            continue
        pending = target.with_suffix(target.suffix + '.part')
        start = time.monotonic()
        size = 0
        try:
            with urlopen(BASE + name, timeout=45) as response, pending.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 128 * 1024 * 1024 or time.monotonic() - start > 180:
                        raise RuntimeError('Modelldownload überschreitet Größen-/Zeitgrenze')
                    output.write(chunk)
            if checksum(pending) != expected:
                raise RuntimeError('Modellprüfsumme stimmt nicht mit der festgelegten Quelle überein')
            pending.replace(target)
            print(f'Installiert und SHA-256 geprüft: {name}', flush=True)
        finally:
            pending.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, default=Path(__file__).resolve().parents[1] / '.data' / 'models')
    args = parser.parse_args()
    install(args.model_dir.expanduser().resolve())
