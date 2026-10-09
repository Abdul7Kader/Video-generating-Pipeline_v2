"""Verified CLOUD return path. No Modal client or inference entry point."""
from fractions import Fraction
import hashlib
import json
import math
import os
import subprocess
import time
from uuid import UUID, uuid5

from app.media import ROOT, checksum, ffprobe_path, media_root, run_folder, safe_path, write_json
from app.encoding import ffmpeg_path, probe_video, runtime_environment
from app.production_stages import StageArtifact, StageFailure, StageResult
from app.wan_contract import (COMFY_COMMIT, WORKFLOW, RAW_FRAMES, RAW_FPS,
                              MAX_CLIP_BYTES, WanRequest, WanResponse, WanSceneSource)


def plan_requests(context):
    if (context.get('mode') != 'CLOUD' or context.get('media_type') != 'AI_GENERATED_VIDEO'
            or any(s.get('media_type') != 'AI_GENERATED_VIDEO' for s in context['scenes'])):
        raise StageFailure('MODE_MISMATCH', 'Wan akzeptiert ausschließlich CLOUD-Szenen mit AI_GENERATED_VIDEO.')
    try:
        bundle = ROOT / 'cloud'
        lock = json.loads((bundle/'bundle.lock.json').read_text(encoding='utf-8'))
        if lock['workflow_version'] != WORKFLOW or lock['comfy_commit'] != COMFY_COMMIT:
            raise ValueError('wrong bundle')
        for name, digest in lock['files_sha256'].items():
            if '/' in name or '\\' in name or checksum(bundle/name) != digest:
                raise ValueError('changed bundle')
        scenes, output = context['scenes'], []
        if not scenes or [s['position'] for s in scenes] != list(range(1, len(scenes)+1)):
            raise ValueError('scene order')
        for scene in scenes:
            duration = scene.get('duration_seconds') or (context['script'].get('target_duration_seconds') or 45)/len(scenes)
            if not math.isfinite(duration) or not 0 < duration <= 60:
                raise ValueError('duration')
            clips = []
            for index in range(1, math.ceil(duration/(RAW_FRAMES/RAW_FPS))+1):
                identity = uuid5(UUID(str(context['run_id'])), f"wan:v1:{UUID(str(scene['id']))}:{index}")
                clips.append(WanRequest(job_id=identity, scene_position=scene['position'], clip_index=index,
                    models_lock_sha256=lock['files_sha256']['models.lock.json'], prompt=scene['wan_prompt'].strip(),
                    seed=int.from_bytes(identity.bytes[:8], 'big')))
            output.append((scene['position'], duration, clips))
        return output
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StageFailure('WAN_PLAN_INVALID', 'Wan-Workflow, Szenenprompt oder Szenendauer ist ungültig. Skript und Cloud-Bundle prüfen.') from exc


def inspect_video(path, frames, executable, encoder, remaining=lambda: 30):
    try:
        data = probe_video(path, executable, count=True, timeout_seconds=min(30, remaining()))
        streams = data['streams']
        if len(streams) != 1 or 'mp4' not in data['format']['format_name']:
            raise ValueError('container or additional streams')
        video = streams[0]
        duration = float(video.get('duration') or data['format']['duration'])
        if (video['codec_name'] != 'h264' or video['codec_type'] != 'video'
                or (video['width'],video['height']) != (720,1280)
                or Fraction(video['avg_frame_rate']) != RAW_FPS
                or int(video['nb_read_frames']) != frames or not math.isfinite(duration)
                or abs(duration-frames/RAW_FPS) > 1/RAW_FPS):
            raise ValueError('profile')
        subprocess.run([encoder, '-v','error','-xerror','-protocol_whitelist','file,pipe',
                        '-i',str(path),'-map','0:v:0','-f','null','-'], check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=runtime_environment(),timeout=min(30, remaining()))
        remaining()
        return duration
    except subprocess.TimeoutExpired as exc:
        remaining()
        raise StageFailure('WAN_MEDIA_TIMEOUT', 'Zeitlimit bei der Wan-Dateiprüfung erreicht.', True) from exc
    except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError) as exc:
        raise StageFailure('WAN_MEDIA_INVALID', 'Wan-Clip ist beschädigt oder entspricht nicht dem festgelegten Videoformat.') from exc


def receive_clip(provider, request, directory, root, probe, encoder, check_cancelled, timeout, remaining=lambda: 30):
    target = safe_path(root, (directory/f'clip-{request.clip_index}.mp4').relative_to(root).as_posix())
    checkpoint = safe_path(root, target.relative_to(root).with_suffix('.json').as_posix())
    intent = safe_path(root, target.relative_to(root).with_suffix('.request.json').as_posix())
    expected = request.model_dump(mode='json')
    if intent.exists() and json.loads(intent.read_text(encoding='utf-8')) != expected:
        raise StageFailure('WAN_JOB_CONFLICT', 'Gespeicherter Wan-Auftrag passt nicht mehr zur freigegebenen Szene.')
    write_json(intent, expected)  # durable intent before any provider operation
    try:
        saved = WanResponse.model_validate_json(checkpoint.read_text(encoding='utf-8'))
        validate_response(saved, request)
        if target.stat().st_size != saved.size_bytes or checksum(target) != saved.checksum_sha256:
            raise ValueError('changed cache')
        inspect_video(target, RAW_FRAMES, probe, encoder, remaining)
        return saved
    except (OSError, ValueError, StageFailure):
        checkpoint.unlink(missing_ok=True)
    check_cancelled()
    started = time.monotonic()
    response = WanResponse.model_validate(provider.ensure_clip(request, timeout_seconds=min(timeout, remaining())))
    check_cancelled()
    transfer_remaining = min(timeout-(time.monotonic()-started), remaining())
    if transfer_remaining <= 0:
        raise TimeoutError('clip deadline')
    validate_response(response, request)
    part = safe_path(root, target.relative_to(root).as_posix()+'.part')
    size, digest = 0, hashlib.sha256()
    try:
        with part.open('wb') as output:
            for block in provider.read_clip(response, timeout_seconds=transfer_remaining):
                check_cancelled()
                if time.monotonic()-started > timeout:
                    raise TimeoutError('transfer deadline')
                if not isinstance(block, bytes):
                    raise ValueError('invalid chunk')
                size += len(block)
                if size > response.size_bytes or size > MAX_CLIP_BYTES:
                    raise ValueError('oversized clip')
                output.write(block); digest.update(block)
            output.flush(); os.fsync(output.fileno())
        check_cancelled()
        if time.monotonic()-started > timeout:
            raise TimeoutError('clip deadline')
        if size != response.size_bytes or digest.hexdigest() != response.checksum_sha256:
            raise StageFailure('WAN_CHECKSUM_MISMATCH', 'Wan-Transfer ist unvollständig oder die Prüfsumme stimmt nicht.')
        inspect_video(part, RAW_FRAMES, probe, encoder, remaining)
        check_cancelled()
        part.replace(target)
        write_json(checkpoint, response.model_dump(mode='json'))
        return response
    finally:
        part.unlink(missing_ok=True)


def validate_response(response, request):
    if (response.request != request or response.execution != 'CONTROLLED_TEST'
            or response.result_path != f'wan/{request.job_id}/clip.mp4'
            or abs(response.duration_seconds-RAW_FRAMES/RAW_FPS) > 1/RAW_FPS):
        raise StageFailure('WAN_RESPONSE_INVALID', 'Wan-Antwort passt nicht zu Auftrag, Herkunft oder Rohclipprofil.')


def validate_scene_manifest(context, result):
    planned = plan_requests(context)
    if (result.sources or len(result.wan_sources) != len(planned)
            or len(result.artifacts) != len(planned)):
        raise ValueError('incomplete or mixed Wan manifest')
    for (position,duration,requests),source,artifact in zip(planned,result.wan_sources,result.artifacts):
        if (source.scene_position != position or source.scene_duration_seconds != duration
                or source.artifact_key != artifact.key or artifact.key != f'scene_{position}'
                or artifact.kind != 'SOURCE' or artifact.media_type != 'AI_GENERATED_VIDEO'
                or len(source.clips) != len(requests)
                or abs(source.duration_seconds-math.ceil(duration*RAW_FPS)/RAW_FPS) > 1/RAW_FPS):
            raise ValueError('Wan scene mismatch')
        for response,request in zip(source.clips,requests): validate_response(response,request)


def collect_scenes(context, provider=None, check_cancelled=lambda: None, timeout_seconds=30):
    # Test providers are explicitly injected by test code. No environment switch,
    # SDK import or live factory can accidentally allocate a GPU in step 21.
    if provider is None:
        raise StageFailure('STAGE_UNAVAILABLE', 'CLOUD-Generierung ist noch gesperrt. Rücktransfer mit Testdaten ist vorbereitet; Kostenprüfung und echte Wan-Anbindung folgen.')
    if getattr(provider, 'execution', None) != 'CONTROLLED_TEST':
        raise StageFailure('WAN_LIVE_DISABLED', 'Echte Wan-Aufträge bleiben bis zur Kostenprüfung gesperrt.')
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30:
        raise StageFailure('WAN_TIMEOUT_INVALID', 'Testtransfer-Zeitlimit muss zwischen 0 und 30 Sekunden liegen.')
    requests = plan_requests(context)
    from app.cloud_limits import load_limits, check_clip_count, cloud_slot
    limits = load_limits()
    check_clip_count(requests, limits)
    deadline = time.monotonic()+limits.max_run_seconds
    def remaining():
        seconds = deadline-time.monotonic()
        if seconds <= 0:
            raise StageFailure('WAN_RUNTIME_LIMIT', 'Cloud-Laufzeitgrenze erreicht. Geprüfte Clips bleiben gespeichert.')
        return seconds
    def check():
        check_cancelled()
        remaining()
    check()
    root = media_root()
    with cloud_slot(root, limits.max_parallel):
        return _collect_scenes(context, provider, requests, root, check,
                               min(timeout_seconds, limits.max_clip_seconds), remaining)


def _collect_scenes(context, provider, requests, root, check_cancelled, timeout_seconds, remaining):
    probe, encoder = ffprobe_path(), ffmpeg_path()
    folder = run_folder(root, context, 'wan')
    manifest = safe_path(root, (folder/'manifest.json').relative_to(root).as_posix())
    manifest.unlink(missing_ok=True)
    artifacts, sources = [], []
    try:
        for position, duration, clips in requests:
            check_cancelled()
            directory = safe_path(root, (folder/f'scene-{position}').relative_to(root).as_posix())
            directory.mkdir(exist_ok=True)
            responses = [receive_clip(provider, request, directory, root, probe, encoder,
                                      check_cancelled, timeout_seconds, remaining) for request in clips]
            target = safe_path(root, (directory/'scene.mp4').relative_to(root).as_posix())
            part = safe_path(root, target.relative_to(root).as_posix()+'.part')
            listing = directory/'concat.txt'
            listing.write_text(''.join(f"file 'clip-{r.clip_index}.mp4'\n" for r in clips), encoding='utf-8')
            frames = math.ceil(duration*RAW_FPS)
            try:
                subprocess.run([encoder,'-v','error','-y','-protocol_whitelist','file,pipe','-f','concat',
                    '-safe','1','-i',str(listing),'-map','0:v:0','-c','copy','-frames:v',str(frames),
                    '-f','mp4',str(part)], check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    env=runtime_environment(),timeout=min(30, remaining()))
                actual_duration = inspect_video(part, frames, probe, encoder, remaining)
                check_cancelled()
                artifact = StageArtifact(key=f'scene_{position}',kind='SOURCE',media_type='AI_GENERATED_VIDEO',
                    storage_path=target.relative_to(root).as_posix(), checksum_sha256=checksum(part))
                part.replace(target)
            finally:
                part.unlink(missing_ok=True)
                listing.unlink(missing_ok=True)
            artifacts.append(artifact)
            sources.append(WanSceneSource(scene_position=position,artifact_key=artifact.key,
                scene_duration_seconds=duration,duration_seconds=actual_duration,clips=responses))
        result = StageResult(artifacts=artifacts,wan_sources=sources).model_dump(mode='json')
        validate_scene_manifest(context, StageResult.model_validate(result))
        check_cancelled()
        write_json(manifest, result)
        return result
    except StageFailure:
        raise
    except (TimeoutError, subprocess.TimeoutExpired) as exc:
        remaining()
        raise StageFailure('WAN_TRANSFER_TIMEOUT', 'Wan-Testtransfer wurde unterbrochen. Geprüfte Clips bleiben wiederaufnehmbar.', True) from exc
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise StageFailure('WAN_RESPONSE_INVALID', 'Wan-Antwort oder Datei konnte nicht sicher übernommen werden.') from exc
