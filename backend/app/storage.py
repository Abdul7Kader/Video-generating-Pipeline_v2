"""Publish an immutable, validated master and auditable version manifest."""
import json
import os
import shutil
from uuid import UUID

from app.encoding import encoding_plan, ffmpeg_path, inspect_master
from app.media import checksum, ffprobe_path, media_root, run_folder, safe_path, write_json
from app.production_stages import StageArtifact, StageFailure, StageResult, StorageManifest


def store_video(context):
    root = media_root()
    try:
        previous = {name: StageResult.model_validate(context['previous_results'][name])
                    for name in ('SCENES', 'SPEECH', 'GRAPHICS', 'ENCODING')}
        plan, _ = encoding_plan(context)
        if previous['GRAPHICS'].graphics != plan:
            raise ValueError('changed graphics')
        expected_type = {'LOKAL':'STOCK_VIDEO', 'CLOUD':'AI_GENERATED_VIDEO'}[context['mode']]
        if context['media_type'] != expected_type or any(a.media_type != expected_type or a.kind != 'SOURCE'
                                                       for a in previous['SCENES'].artifacts):
            raise StageFailure('MODE_MISMATCH', 'Die gespeicherten Szenen passen nicht zum freigegebenen Modus.')
        encoded = previous['ENCODING']
        if (encoded.encoding is None or encoded.encoding.duration_frames != plan.duration_frames
                or len(encoded.artifacts) != 1 or encoded.artifacts[0].key != 'encoded_master'
                or encoded.artifacts[0].kind != 'INTERMEDIATE' or encoded.artifacts[0].media_type != 'FINAL_VIDEO'):
            raise ValueError('missing master')
        inputs = [a for stage in previous.values() for a in stage.artifacts]
        for artifact in inputs:
            if checksum(safe_path(root, artifact.storage_path)) != artifact.checksum_sha256:
                raise ValueError('changed input')
        source = safe_path(root, encoded.artifacts[0].storage_path)
        probe, encoder = ffprobe_path(), ffmpeg_path()
        profile = inspect_master(source, plan.duration_frames, probe, encoder)
        if profile != {'duration_seconds':encoded.encoding.duration_seconds, 'size_bytes':encoded.encoding.size_bytes}:
            raise ValueError('changed profile')
        folder = run_folder(root, context, 'storage')
        target, manifest = folder/'master.mp4', folder/'manifest.json'
        safe_path(root,target.relative_to(root).as_posix())
        safe_path(root,manifest.relative_to(root).as_posix())
        final = StageArtifact(key='master_video', kind='FINAL', media_type='FINAL_VIDEO',
                              storage_path=target.relative_to(root).as_posix(), checksum_sha256=checksum(source))
        project, run, version = str(UUID(context['project_id'])), str(UUID(str(context['run_id']))), context['script']['version']
        payload = dict(schema_version=1, project_id=project, run_id=run, script_version=version,
                       mode=context['mode'], media_type=expected_type,
                       script={k:context['script'][k] for k in ('title','narration','language')},
                       scenes=[{k:s.get(k) for k in ('position','narration','visual_description','duration_seconds',
                                                  'pexels_queries','wan_prompt')} for s in context['scenes']],
                       inputs=[a.model_dump() for a in inputs], sources=[s.model_dump() for s in previous['SCENES'].sources],
                       speech=[s.model_dump() for s in previous['SPEECH'].speech], graphics=plan.model_dump(),
                       encoding=encoded.encoding.model_dump(), final=final.model_dump())
        cached = False
        try:
            cached = (json.loads(manifest.read_text(encoding='utf-8')) == payload
                      and checksum(target) == final.checksum_sha256)
            if cached:
                inspect_master(target, plan.duration_frames, probe, encoder)
        except (OSError, ValueError, StageFailure):
            cached = False
        if not cached:
            part = target.with_suffix('.mp4.part')
            safe_path(root,part.relative_to(root).as_posix())
            try:
                with source.open('rb') as incoming, part.open('wb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024*1024)
                    outgoing.flush(); os.fsync(outgoing.fileno())
                if checksum(part) != final.checksum_sha256:
                    raise ValueError('copy changed')
                inspect_master(part, plan.duration_frames, probe, encoder)
                part.replace(target)
                write_json(manifest, payload)
            finally:
                part.unlink(missing_ok=True)
        return StageResult(artifacts=[final], storage=StorageManifest(project_id=project, run_id=run,
            script_version=version, manifest_path=manifest.relative_to(root).as_posix(), manifest_sha256=checksum(manifest))).model_dump()
    except StageFailure:
        raise
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise StageFailure('STORAGE_INVALID', 'Geprüfte Videodatei oder Eingangsmanifest fehlen, sind verändert oder konnten nicht gespeichert werden. Keine finale Datei freigegeben.') from exc
