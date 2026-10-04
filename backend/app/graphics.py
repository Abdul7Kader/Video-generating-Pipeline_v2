"""Remotion overlay planning and local rendering from approved scene data."""

import math
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
from uuid import UUID
import zlib

from app.media import ROOT, checksum, ffprobe_path, media_root, write_json
from app.production_stages import GraphicsManifest, GraphicsScene, StageArtifact, StageFailure, StageResult
from app.speech import inspect_audio


def build_plan(context):
    try:
        speech = StageResult.model_validate(context['previous_results']['SPEECH']).speech
        by_position = {s.scene_position: s for s in speech}
        scenes = context['scenes']
        if (len(speech) != len(scenes) or len(by_position) != len(speech)
                or [s['position'] for s in scenes] != list(range(1, len(scenes)+1))):
            raise ValueError('incomplete speech')
        output, start = [], 0
        for scene in scenes:
            segment = by_position[scene['position']]
            if (segment.text != scene['narration'].strip()
                    or abs(segment.duration_seconds - segment.frames/segment.sample_rate) > 1/segment.sample_rate):
                raise ValueError('inconsistent speech')
            spoken_frames = math.ceil(segment.duration_seconds * 24)
            planned = scene.get('duration_seconds') or (context['script'].get('target_duration_seconds') or 45)/len(scenes)
            duration = max(math.ceil(planned * 24), spoken_frames)
            output.append(GraphicsScene(scene_position=scene['position'], artifact_key=f"caption_{scene['position']}",
                                        text=segment.text, start_frame=start, duration_frames=duration,
                                        caption_frames=spoken_frames, audio_duration_seconds=segment.duration_seconds))
            start += duration
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise StageFailure('GRAPHICS_SPEECH_REQUIRED', 'Geprüfte Sprachsegmente fehlen oder passen nicht zum freigegebenen Szenentext. Grafik wurde blockiert.') from exc
    try:
        if context['script'].get('language') != 'de-DE':
            raise ValueError('unsupported language')
        return GraphicsManifest(title=context['script']['title'].strip(), title_frames=min(96, output[0].duration_frames),
                                duration_frames=start, scenes=output)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise StageFailure('GRAPHICS_TIMELINE_INVALID', 'Grafikzeitdaten oder Titel sind ungültig. Gesamtdauer muss 30–60 Sekunden betragen; Sprechertext und Szenendauer prüfen.') from exc


def inspect_overlay(path, executable):
    try:
        data = path.read_bytes()
        if not 100 < len(data) < 8*1024*1024 or data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('invalid PNG')
        offset, ended = 8, False
        while offset < len(data):
            length, = struct.unpack('>I', data[offset:offset+4])
            tag, payload = data[offset+4:offset+8], data[offset+8:offset+8+length]
            crc, = struct.unpack('>I', data[offset+8+length:offset+12+length])
            if zlib.crc32(tag+payload) != crc:
                raise ValueError('corrupt PNG chunk')
            offset += 12+length
            if tag == b'IEND':
                ended = offset == len(data)
                break
        if not ended:
            raise ValueError('incomplete PNG')
        result = subprocess.run([executable, '-v', 'error', '-show_entries', 'stream=codec_name,width,height,pix_fmt',
                                 '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=15)
        streams = json.loads(result.stdout)['streams']
        if len(streams) != 1 or streams[0] != {'codec_name': 'png', 'width': 720, 'height': 1280, 'pix_fmt': 'rgba'}:
            raise ValueError('incorrect overlay profile')
    except (OSError, ValueError, KeyError, TypeError, struct.error, subprocess.SubprocessError) as exc:
        raise StageFailure('GRAPHICS_OUTPUT_INVALID', 'Grafikdatei ist beschädigt, hat keine Transparenz oder entspricht nicht 720 × 1280. Encoding wurde blockiert.') from exc


def render_graphics(context):
    plan = build_plan(context)
    executable = ffprobe_path()
    root = media_root()
    speech = StageResult.model_validate(context['previous_results']['SPEECH'])
    try:
        artifacts = {a.key: a for a in speech.artifacts}
        if set(artifacts) != {s.artifact_key for s in speech.speech} or len(artifacts) != len(speech.speech):
            raise ValueError('missing audio files')
        for segment in speech.speech:
            artifact = artifacts[segment.artifact_key]
            path = root / artifact.storage_path
            if (artifact.kind != 'INTERMEDIATE' or artifact.media_type != 'SPEECH_AUDIO'
                    or checksum(path) != artifact.checksum_sha256
                    or inspect_audio(path, segment.sample_rate, executable)['frames'] != segment.frames):
                raise ValueError('changed audio')
    except (OSError, ValueError, StageFailure) as exc:
        raise StageFailure('GRAPHICS_SPEECH_REQUIRED', 'Gespeicherte Sprachdateien fehlen oder sind beschädigt. Grafik wurde blockiert.') from exc
    try:
        from app.media import run_folder
        folder = run_folder(root, context, 'graphics')
        folder.mkdir(parents=True, exist_ok=True)
        templates = ROOT / 'graphics'
        digest = hashlib.sha256()
        for relative in ('package-lock.json', 'render.mjs', 'src/index.jsx', 'src/overlay.css'):
            digest.update((templates / relative).read_bytes())
        fingerprint = hashlib.sha256((plan.model_dump_json()+digest.hexdigest()).encode()).hexdigest()
        items = [{'key': plan.title_artifact_key, 'kind': 'title', 'text': plan.title}]
        items += [{'key': s.artifact_key, 'kind': 'caption', 'text': s.text, 'position': s.scene_position} for s in plan.scenes]
        manifest = folder / 'manifest.json'
        try:
            saved = json.loads(manifest.read_text(encoding='utf-8'))
            result = StageResult.model_validate(saved['result'])
            if (saved['fingerprint'] != fingerprint or result.graphics != plan
                    or {a.key for a in result.artifacts} != {i['key'] for i in items}
                    or len(result.artifacts) != len(items)):
                raise ValueError('changed graphics')
            for artifact in result.artifacts:
                path = folder / (artifact.key+'.png')
                if (artifact.kind != 'INTERMEDIATE' or artifact.media_type != 'GRAPHICS_OVERLAY'
                        or artifact.storage_path != path.relative_to(root).as_posix()
                        or artifact.checksum_sha256 != checksum(path)):
                    raise ValueError('changed overlay')
                inspect_overlay(path, executable)
            return result.model_dump()
        except (OSError, ValueError, KeyError, TypeError, StageFailure):
            pass
        node = os.environ.get('REMOTION_NODE_PATH') or shutil.which('node')
        if not node or not Path(node).is_file() or not (templates / 'node_modules/@remotion/renderer/package.json').is_file():
            raise StageFailure('REMOTION_REQUIRED', 'Node.js oder Remotion fehlen. npm ci --prefix graphics und den lokalen Renderbrowser installieren.')
        write_json(folder / 'request.json', {'total': len(plan.scenes), 'items': items})
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        render_env = {name: value for name, value in os.environ.items() if name.upper() in {
            'PATH', 'HOME', 'USERPROFILE', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR',
            'LANG', 'LC_ALL', 'LD_LIBRARY_PATH', 'XDG_CACHE_HOME', 'REMOTION_BROWSER_EXECUTABLE'}}
        try:
            # The isolated stage watchdog owns the 900 s limit and kills the whole
            # process tree on timeout/cancellation, including Node and Chromium.
            subprocess.run([node, str(templates/'render.mjs'), str(folder/'request.json'), str(folder)], cwd=templates,
                           env=render_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, **flags)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise StageFailure('GRAPHICS_RENDER_FAILED', 'Remotion konnte die Grafikvorlagen nicht rendern. Installation, Renderbrowser und Textlänge prüfen; Encoding wurde blockiert.') from exc
        layouts = json.loads((folder/'layout.json').read_text(encoding='utf-8'))
        if len(layouts) != len(items) or {x['key']: x['text'] for x in layouts} != {x['key']: x['text'] for x in items}:
            raise StageFailure('GRAPHICS_OUTPUT_INVALID', 'Grafik-Layoutnachweis ist unvollständig.')
        for layout in layouts:
            if not (22 <= layout['fontSize'] <= 42 and layout['left'] >= 64 and layout['right'] <= 608
                    and layout['top'] >= 96 and layout['bottom'] <= 1040
                    and (layout['bottom'] <= 386 if layout['kind'] == 'title' else layout['top'] >= 410)):
                raise StageFailure('GRAPHICS_OUTPUT_INVALID', 'Grafik überschreitet sichere Ränder oder verdeckt den Titel.')
        output = []
        for item in items:
            path = folder/(item['key']+'.png')
            inspect_overlay(path, executable)
            output.append(StageArtifact(key=item['key'], kind='INTERMEDIATE', media_type='GRAPHICS_OVERLAY',
                                        storage_path=path.relative_to(root).as_posix(), checksum_sha256=checksum(path)))
        result = StageResult(artifacts=output, graphics=plan)
        write_json(manifest, {'fingerprint': fingerprint, 'result': result.model_dump()})
        return result.model_dump()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StageFailure('GRAPHICS_STORAGE_FAILED', 'Grafikdateien oder Layoutdaten konnten nicht zuverlässig gespeichert werden.') from exc
