"""Offline, scene-based Piper audio with measured, resumable WAV segments."""

from array import array
from importlib.metadata import PackageNotFoundError, version
import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import UUID
import wave

from app.media import ROOT, checksum, ffprobe_path, media_root, write_json
from app.production_stages import SpeechSegment, StageArtifact, StageFailure, StageResult

LENGTH_SCALE = 1.15


def model_settings():
    model = Path(os.environ.get('PIPER_MODEL_PATH') or ROOT / '.data' / 'models' / 'de_DE-thorsten-high.onnx').expanduser()
    config = Path(str(model) + '.json')
    if not model.is_absolute() or not model.is_file() or not config.is_file():
        raise StageFailure('PIPER_MODEL_REQUIRED', 'Piper-Stimmenmodell fehlt. Modell und .onnx.json installieren oder PIPER_MODEL_PATH als absoluten Pfad setzen.')
    try:
        settings = json.loads(config.read_text(encoding='utf-8'))
        rate = settings['audio']['sample_rate']
        if settings['espeak']['voice'] != 'de' or not isinstance(rate, int) or not 8000 <= rate <= 48000:
            raise ValueError('unsupported model')
        engine = version('piper-tts')
        return model, rate, {'voice': model.stem, 'model_sha256': checksum(model),
                             'config_sha256': checksum(config), 'engine_version': engine, 'length_scale': LENGTH_SCALE}
    except PackageNotFoundError as exc:
        raise StageFailure('PIPER_REQUIRED', 'Piper fehlt in der Hostworker-Umgebung. requirements-worker.txt installieren.') from exc
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StageFailure('PIPER_MODEL_INVALID', 'Piper-Modellkonfiguration ist ungültig oder keine unterstützte deutsche Stimme.') from exc


def load_voice(model):
    try:
        from piper import PiperVoice
        voice = PiperVoice.load(str(model), use_cuda=False)
        voice.config.length_scale = LENGTH_SCALE
        return voice
    except ImportError as exc:
        raise StageFailure('PIPER_REQUIRED', 'Piper-Laufzeit fehlt oder kann nicht geladen werden. Hostworker-Installation prüfen.') from exc
    except Exception as exc:
        raise StageFailure('PIPER_MODEL_INVALID', 'Piper konnte das lokale Stimmenmodell nicht laden. Modell und Installation prüfen.') from exc


def inspect_audio(path, rate, executable):
    try:
        with wave.open(str(path), 'rb') as wav:
            frames = wav.getnframes()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != rate
                    or wav.getcomptype() != 'NONE' or not 0 < frames <= rate * 120):
                raise ValueError('invalid PCM audio')
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError('truncated audio')
            samples = array('h'); samples.frombytes(pcm)
            if max(abs(sample) for sample in samples) < 32:
                raise ValueError('silent audio')
        output = subprocess.run([executable, '-v', 'error', '-show_entries',
                                 'format=duration:stream=codec_type,codec_name,sample_rate,channels',
                                 '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=15)
        data = json.loads(output.stdout)
        streams = data['streams']
        duration = frames / rate
        if (len(streams) != 1 or streams[0]['codec_type'] != 'audio' or streams[0]['codec_name'] != 'pcm_s16le'
                or int(streams[0]['sample_rate']) != rate or streams[0]['channels'] != 1
                or abs(float(data['format']['duration']) - duration) > 1 / rate):
            raise ValueError('ffprobe/audio duration mismatch')
        return {'duration_seconds': duration, 'frames': frames, 'sample_rate': rate, 'channels': 1}
    except (OSError, wave.Error, EOFError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        raise StageFailure('SPEECH_OUTPUT_INVALID', 'Sprachausgabe ist leer, still, beschädigt oder hat ungültige Zeitdaten. Rendering wurde blockiert.') from exc


def synthesize_scenes(context):
    if context['script'].get('language') != 'de-DE':
        raise StageFailure('SPEECH_LANGUAGE_UNSUPPORTED', 'Die Sprachsynthese unterstützt derzeit deutsche Skripte (de-DE).')
    scenes = context['scenes']
    if not scenes:
        raise StageFailure('SPEECH_TEXT_REQUIRED', 'Keine Sprechersegmente vorhanden. Skript bearbeiten und neu freigeben.')
    for scene in scenes:
        if not isinstance(scene.get('narration'), str) or not scene['narration'].strip():
            raise StageFailure('SPEECH_TEXT_REQUIRED', f"Szene {scene['position']}: Sprechertext fehlt. Skript bearbeiten und neu freigeben.")
    model, rate, settings = model_settings()
    executable = ffprobe_path()
    voice = None
    try:
        root = media_root()
        folder = root / 'speech' / str(UUID(context['run_id']))
        folder.mkdir(parents=True, exist_ok=True)
        artifacts, speech = [], []
        for scene in scenes:
            position, text = scene['position'], scene['narration'].strip()
            clip, checkpoint = folder / f'scene-{position}.wav', folder / f'scene-{position}.json'
            fingerprint = hashlib.sha256(json.dumps({'scene': str(scene['id']), 'text': text, **settings}, sort_keys=True).encode()).hexdigest()
            try:
                saved = json.loads(checkpoint.read_text(encoding='utf-8'))
                artifact = StageArtifact.model_validate(saved['artifact'])
                segment = SpeechSegment.model_validate(saved['segment'])
                if (saved['fingerprint'] != fingerprint or artifact.storage_path != clip.relative_to(root).as_posix()
                        or artifact.key != f'speech_{position}' or artifact.kind != 'INTERMEDIATE' or artifact.media_type != 'SPEECH_AUDIO'
                        or segment.artifact_key != artifact.key or segment.scene_position != position or segment.text != text
                        or artifact.checksum_sha256 != checksum(clip)
                        or any(getattr(segment, k) != v for k, v in settings.items())
                        or any(getattr(segment, k) != v for k, v in inspect_audio(clip, rate, executable).items())):
                    raise ValueError('audio checkpoint mismatch')
            except (OSError, ValueError, KeyError, TypeError, StageFailure):
                if voice is None:
                    voice = load_voice(model)
                part = clip.with_suffix('.wav.part')
                try:
                    try:
                        with wave.open(str(part), 'wb') as output:
                            voice.synthesize_wav(text, output)
                    except Exception as exc:
                        raise StageFailure('SPEECH_SYNTHESIS_FAILED', f'Szene {position}: Piper-Sprachsynthese fehlgeschlagen. Rendering wurde blockiert.') from exc
                    measured = inspect_audio(part, rate, executable)
                    segment = SpeechSegment(scene_position=position, artifact_key=f'speech_{position}', text=text, **settings, **measured)
                    artifact = StageArtifact(key=segment.artifact_key, kind='INTERMEDIATE', media_type='SPEECH_AUDIO',
                                             storage_path=clip.relative_to(root).as_posix(), checksum_sha256=checksum(part))
                    part.replace(clip)
                    write_json(checkpoint, {'fingerprint': fingerprint, 'artifact': artifact.model_dump(), 'segment': segment.model_dump()})
                finally:
                    part.unlink(missing_ok=True)
            artifacts.append(artifact); speech.append(segment)
        result = StageResult(artifacts=artifacts, speech=speech)
        write_json(folder / 'manifest.json', result.model_dump())
        return result.model_dump()
    except OSError as exc:
        raise StageFailure('MEDIA_STORAGE_FAILED', 'Sprachsegmente konnten nicht gespeichert werden. Medienordner und freien Speicher prüfen.') from exc
