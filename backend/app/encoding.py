"""CPU-only FFmpeg composition of approved sources, audio and Remotion overlays."""

from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

from app.graphics import build_plan, inspect_overlay
from app.media import checksum, ffprobe_path, media_root
from app.production_stages import StageFailure, StageResult
from app.speech import inspect_audio


def encoding_plan(context):
    expected_type = {'LOKAL': 'STOCK_VIDEO', 'CLOUD': 'AI_GENERATED_VIDEO'}.get(context.get('mode'))
    if not expected_type or context.get('media_type') != expected_type:
        raise StageFailure('MODE_MISMATCH', 'Der Quellenvertrag passt nicht zum freigegebenen Videomodus.')
    try:
        previous = context['previous_results']
        source = StageResult.model_validate(previous['SCENES'])
        speech = StageResult.model_validate(previous['SPEECH'])
        graphics = StageResult.model_validate(previous['GRAPHICS'])
        plan = build_plan(context)
        if graphics.graphics != plan:
            raise ValueError('changed graphics timeline')
        groups = (
            (source.artifacts, {f'scene_{s.scene_position}' for s in plan.scenes}, 'SOURCE', expected_type),
            (speech.artifacts, {f'speech_{s.scene_position}' for s in plan.scenes}, 'INTERMEDIATE', 'SPEECH_AUDIO'),
            (graphics.artifacts, {plan.title_artifact_key, *(s.artifact_key for s in plan.scenes)}, 'INTERMEDIATE', 'GRAPHICS_OVERLAY'),
        )
        if any(a.media_type != expected_type for a in source.artifacts):
            raise StageFailure('MODE_MISMATCH', 'Gemischte Szenenquellen wurden abgewiesen. Kein Quellenwechsel beim Videoschnitt.')
        if {s.artifact_key for s in speech.speech} != groups[1][1]:
            raise ValueError('speech key mismatch')
        inputs = {}
        for artifacts, keys, kind, media in groups:
            if (len(artifacts) != len(keys) or {a.key for a in artifacts} != keys
                    or any(a.kind != kind or a.media_type != media for a in artifacts)):
                raise ValueError('incomplete input artifacts')
            inputs.update({a.key: a for a in artifacts})
        return plan, inputs
    except (KeyError, ValueError, TypeError) as exc:
        raise StageFailure('ENCODING_INPUT_INVALID', 'Clips, Sprache oder Grafikzeitdaten fehlen oder passen nicht zur Freigabe. Videoschnitt wurde blockiert.') from exc


def ffmpeg_path():
    executable = os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')
    if not executable or not Path(executable).is_file():
        raise StageFailure('FFMPEG_REQUIRED', 'FFmpeg fehlt. FFmpeg mit libx264/AAC installieren und im Worker-PATH oder als FFMPEG_PATH einrichten.')
    return executable


def probe_video(path, executable, count=False):
    command = [executable, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_streams', '-show_format', '-of', 'json']
    if count:
        command.append('-count_frames')
    return json.loads(subprocess.check_output(command+[str(path)], stderr=subprocess.DEVNULL, timeout=120))


def prepare_inputs(context, root, executable):
    plan, artifacts = encoding_plan(context)
    paths = {}
    try:
        for key, artifact in artifacts.items():
            path = (root/artifact.storage_path).resolve()
            if not path.is_relative_to(root) or not path.is_file() or checksum(path) != artifact.checksum_sha256:
                raise ValueError('changed or escaped file')
            paths[key] = path
        speech = StageResult.model_validate(context['previous_results']['SPEECH']).speech
        for scene, segment in zip(plan.scenes, sorted(speech, key=lambda s:s.scene_position)):
            data = probe_video(paths[f'scene_{scene.scene_position}'], executable)
            videos = [s for s in data['streams'] if s['codec_type'] == 'video']
            if len(videos) != 1 or 'mp4' not in data['format']['format_name']:
                raise ValueError('invalid video container')
            video = videos[0]
            duration = float(video.get('duration') or data['format']['duration'])
            fps = float(Fraction(video['avg_frame_rate']))
            if (not math.isfinite(duration) or duration < scene.duration_frames/24
                    or not 0 < fps <= 240 or not 0 < int(video['width']) <= 8192
                    or not 0 < int(video['height']) <= 8192):
                raise StageFailure('ENCODING_SOURCE_INVALID', f'Clip für Szene {scene.scene_position} ist beschädigt, zu kurz oder hat ungültige Bilddaten. Quelle und Szenendauer prüfen.')
            audio = inspect_audio(paths[segment.artifact_key], segment.sample_rate, executable)
            if audio['frames'] != segment.frames:
                raise ValueError('audio duration mismatch')
            inspect_overlay(paths[scene.artifact_key], executable)
        inspect_overlay(paths[plan.title_artifact_key], executable)
        return plan, artifacts, paths
    except StageFailure:
        raise
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        raise StageFailure('ENCODING_INPUT_INVALID', 'Gespeicherte Eingangsdateien fehlen, sind beschädigt oder stimmen nicht mit ihren Prüfsummen überein. Videoschnitt wurde blockiert.') from exc


def run_ffmpeg(executable, arguments, folder):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    environment = {k:v for k,v in os.environ.items() if k.upper() in {
        'PATH', 'HOME', 'USERPROFILE', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LD_LIBRARY_PATH'}}
    try:
        with (folder/'ffmpeg.log').open('ab') as log:
            # The isolated production watchdog bounds and kills this entire tree.
            subprocess.run([executable, '-v', 'error', '-nostdin', '-y', '-xerror', *arguments], cwd=folder,
                           env=environment, stdout=subprocess.DEVNULL, stderr=log, check=True, **flags)
    except (OSError, subprocess.SubprocessError) as exc:
        raise StageFailure('ENCODING_FAILED', 'FFmpeg konnte das Video nicht zusammensetzen. Quelldateien und libx264-/AAC-Installation prüfen; keine finale Datei freigegeben.') from exc


def inspect_master(path, frames, probe, encoder):
    try:
        data = probe_video(path, probe, count=True)
        videos = [s for s in data['streams'] if s['codec_type'] == 'video']
        audios = [s for s in data['streams'] if s['codec_type'] == 'audio']
        if len(data['streams']) != 2 or len(videos) != 1 or len(audios) != 1:
            raise ValueError('incorrect stream count')
        video, audio = videos[0], audios[0]
        if ('mp4' not in data['format']['format_name'] or video['codec_name'] != 'h264'
                or (video['width'], video['height'], video['pix_fmt'], video['sample_aspect_ratio']) != (720,1280,'yuv420p','1:1')
                or Fraction(video['avg_frame_rate']) != 24 or int(video['nb_read_frames']) != frames
                or abs(float(video['duration'])-frames/24) > 1/24000
                or audio['codec_name'] != 'aac' or int(audio['sample_rate']) != 48000 or audio['channels'] != 1
                or abs(float(audio['duration'])-frames/24) > .05
                or abs(float(data['format']['duration'])-frames/24) > .05):
            raise ValueError('incorrect master profile or timing')
        subprocess.run([encoder, '-v', 'error', '-xerror', '-nostdin', '-protocol_whitelist','file,pipe',
                        '-threads','2','-i',str(path),'-map','0:v:0','-map','0:a:0','-f','null','-'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=True)
        return {'duration_seconds': frames/24, 'size_bytes': path.stat().st_size}
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        raise StageFailure('ENCODING_OUTPUT_INVALID', 'MP4 ist beschädigt oder entspricht nicht dem Profil 720 × 1280 / 24 fps / H.264 / AAC. Ablage wurde blockiert.') from exc


def encode_video(context):
    prepare_inputs(context, media_root(), ffprobe_path())
    raise StageFailure('STAGE_UNAVAILABLE', 'Encoding-Renderer wird noch implementiert.')
