"""CPU-only FFmpeg composition of approved sources, audio and Remotion overlays."""

from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID

from app.graphics import build_plan, inspect_overlay
from app.media import checksum, ffprobe_path, media_root, write_json
from app.production_stages import EncodingManifest, StageArtifact, StageFailure, StageResult
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
        if graphics.graphics and graphics.graphics.template_version != 'v2':
            raise StageFailure('GRAPHICS_STYLE_OUTDATED', 'Gespeicherte Grafiken verwenden noch die alte Gestaltung mit Szenennummern. Neue Skriptversion speichern und freigeben, um das Video ohne diese Einblendungen zu erzeugen.')
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


def runtime_environment():
    return {k:v for k,v in os.environ.items() if k.upper() in {
        'PATH', 'HOME', 'USERPROFILE', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LD_LIBRARY_PATH'}}


def probe_video(path, executable, count=False):
    command = [executable, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_streams', '-show_format', '-of', 'json']
    if count:
        command.append('-count_frames')
    return json.loads(subprocess.check_output(command+[str(path)], env=runtime_environment(), stderr=subprocess.DEVNULL, timeout=120))


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
    try:
        with (folder/'ffmpeg.log').open('ab') as log:
            # The isolated production watchdog bounds and kills this entire tree.
            subprocess.run([executable, '-v', 'error', '-nostdin', '-y', '-xerror', *arguments], cwd=folder,
                           env=runtime_environment(), stdout=subprocess.DEVNULL, stderr=log, check=True, **flags)
    except (OSError, subprocess.SubprocessError) as exc:
        raise StageFailure('ENCODING_FAILED', 'FFmpeg konnte das Video nicht zusammensetzen. Quelldateien und libx264-/AAC-Installation prüfen; keine finale Datei freigegeben.') from exc


def inspect_master(path, frames, probe, encoder, with_audio=True):
    try:
        data = probe_video(path, probe, count=True)
        videos = [s for s in data['streams'] if s['codec_type'] == 'video']
        audios = [s for s in data['streams'] if s['codec_type'] == 'audio']
        if len(data['streams']) != (2 if with_audio else 1) or len(videos) != 1 or len(audios) != (1 if with_audio else 0):
            raise ValueError('incorrect stream count')
        video = videos[0]
        if ('mp4' not in data['format']['format_name'] or video['codec_name'] != 'h264'
                or (video['width'], video['height'], video['pix_fmt'], video['sample_aspect_ratio']) != (720,1280,'yuv420p','1:1')
                or Fraction(video['avg_frame_rate']) != 24 or int(video['nb_read_frames']) != frames
                or abs(float(video['duration'])-frames/24) > 1/24000
                or abs(float(data['format']['duration'])-frames/24) > .05):
            raise ValueError('incorrect master profile or timing')
        if with_audio:
            audio = audios[0]
            if (audio['codec_name'] != 'aac' or int(audio['sample_rate']) != 48000 or audio['channels'] != 1
                    or abs(float(audio['duration'])-frames/24) > .05):
                raise ValueError('incorrect audio profile or timing')
        subprocess.run([encoder, '-v', 'error', '-xerror', '-nostdin', '-protocol_whitelist','file,pipe',
                        '-threads','2','-i',str(path),'-map','0:v:0', *(['-map','0:a:0'] if with_audio else []),'-f','null','-'],
                       env=runtime_environment(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=True)
        return {'duration_seconds': frames/24, 'size_bytes': path.stat().st_size}
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        raise StageFailure('ENCODING_OUTPUT_INVALID', 'MP4 ist beschädigt oder entspricht nicht dem Profil 720 × 1280 / 24 fps / H.264 / AAC. Ablage wurde blockiert.') from exc


def encode_video(context):
    root, probe, encoder = media_root(), ffprobe_path(), ffmpeg_path()
    plan, artifacts, paths = prepare_inputs(context, root, probe)
    from app.media import run_folder
    folder = run_folder(root, context, 'encoding')
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(('ffmpeg-v2-captions-only-h264-crf20-veryfast-aac128-mono48k\n'+plan.model_dump_json()
                                 + ''.join(a.model_dump_json() for a in artifacts.values())).encode()).hexdigest()
    target, manifest = folder/'master.mp4', folder/'manifest.json'
    try:
        saved = json.loads(manifest.read_text(encoding='utf-8'))
        result = StageResult.model_validate(saved['result'])
        if (saved['fingerprint'] != fingerprint or result.encoding is None or len(result.artifacts) != 1
                or result.encoding.duration_frames != plan.duration_frames):
            raise ValueError('changed encoding')
        artifact = result.artifacts[0]
        if (artifact.key != 'encoded_master' or artifact.kind != 'INTERMEDIATE' or artifact.media_type != 'FINAL_VIDEO'
                or artifact.storage_path != target.relative_to(root).as_posix() or checksum(target) != artifact.checksum_sha256
                or EncodingManifest(duration_frames=plan.duration_frames,
                                    **inspect_master(target, plan.duration_frames, probe, encoder)) != result.encoding):
            raise ValueError('changed master')
        return result.model_dump()
    except (OSError, ValueError, KeyError, TypeError, StageFailure):
        pass
    for scene in plan.scenes:
        clip = folder/f'scene_{scene.scene_position}.mp4'
        checkpoint = clip.with_suffix('.json')
        scene_fingerprint = fingerprint+f':{scene.scene_position}'
        try:
            saved = json.loads(checkpoint.read_text(encoding='utf-8'))
            if saved['fingerprint'] != scene_fingerprint or saved['checksum'] != checksum(clip):
                raise ValueError('changed scene')
            inspect_master(clip, scene.duration_frames, probe, encoder, with_audio=False)
            continue
        except (OSError, ValueError, KeyError, TypeError, StageFailure):
            pass
        arguments = ['-protocol_whitelist','file,pipe','-threads','2','-i',str(paths[f'scene_{scene.scene_position}']),
                     '-loop','1','-framerate','24','-i',str(paths[scene.artifact_key])]
        filters = (f'[0:v:0]setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,'
                   f'crop=720:1280,setsar=1,fps=24,trim=end_frame={scene.duration_frames},setpts=PTS-STARTPTS[base];'
                   f"[base][1:v]overlay=0:0:enable='lt(t,{scene.caption_frames}/24)'[video]")
        # The project title stays in saved metadata/intermediate graphics for
        # compatibility. The final video contains only the approved captions.
        part = clip.with_suffix('.part.mp4')
        try:
            run_ffmpeg(encoder, arguments+['-filter_complex_threads','1','-filter_complex',filters,'-map','[video]',
                '-an','-frames:v',str(scene.duration_frames),'-c:v','libx264','-preset','veryfast','-crf','20',
                '-pix_fmt','yuv420p','-threads','2','-video_track_timescale','24000','-map_metadata','-1',str(part)], folder)
            inspect_master(part, scene.duration_frames, probe, encoder, with_audio=False)
            part.replace(clip)
            write_json(checkpoint, {'fingerprint':scene_fingerprint, 'checksum':checksum(clip)})
        finally:
            part.unlink(missing_ok=True)
    concat = folder/'scenes.ffconcat'
    concat.write_text('ffconcat version 1.0\n'+''.join(f"file scene_{s.scene_position}.mp4\nduration {s.duration_frames/24:.9f}\n" for s in plan.scenes), encoding='ascii')
    arguments = ['-protocol_whitelist','file,pipe','-f','concat','-safe','1','-i',str(concat)]
    audio_filters, labels = [], []
    for index, scene in enumerate(plan.scenes, 1):
        arguments += ['-protocol_whitelist','file,pipe','-i',str(paths[f'speech_{scene.scene_position}'])]
        audio_filters.append(f'[{index}:a:0]aresample=48000,apad=whole_len={scene.duration_frames*2000},'
                             f'atrim=end_sample={scene.duration_frames*2000},asetpts=PTS-STARTPTS[a{index}]')
        labels.append(f'[a{index}]')
    audio_filters.append(''.join(labels)+f'concat=n={len(labels)}:v=0:a=1[audio]')
    part = target.with_suffix('.part.mp4')
    try:
        # One continuous AAC encode avoids per-scene encoder-delay gaps/drift.
        run_ffmpeg(encoder, arguments+['-filter_complex_threads','1','-filter_complex',';'.join(audio_filters),
            '-map','0:v:0','-map','[audio]','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-ac','1',
            '-t',str(plan.duration_frames/24),'-movflags','+faststart','-map_metadata','-1',str(part)], folder)
        profile = inspect_master(part, plan.duration_frames, probe, encoder)
        part.replace(target)
        result = StageResult(artifacts=[StageArtifact(key='encoded_master',kind='INTERMEDIATE',media_type='FINAL_VIDEO',
            storage_path=target.relative_to(root).as_posix(),checksum_sha256=checksum(target))],
            encoding=EncodingManifest(duration_frames=plan.duration_frames, **profile)).model_dump()
        write_json(manifest, {'fingerprint':fingerprint, 'result':result})
        return result
    finally:
        part.unlink(missing_ok=True)
