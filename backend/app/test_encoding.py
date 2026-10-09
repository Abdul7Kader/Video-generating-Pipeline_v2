"""Encoding must preserve approved timing and reject mixed/incomplete inputs."""

import copy
from array import array
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import wave
import zlib

from app.graphics import build_plan
from app.production_stages import StageFailure
from app.test_graphics import graphics_context
from app.encoding import encoding_plan
from app.media import checksum


def encoding_context(mode='LOKAL'):
    context = graphics_context(mode)
    context['media_type'] = 'STOCK_VIDEO' if mode == 'LOKAL' else 'AI_GENERATED_VIDEO'
    previous = context['previous_results']
    def artifact(key, kind, media, extension):
        return dict(key=key, kind=kind, media_type=media, storage_path=f'inputs/{key}.{extension}', checksum_sha256='a'*64)
    previous['SCENES'] = {'artifacts': [artifact(f'scene_{i}', 'SOURCE', context['media_type'], 'mp4') for i in range(1, 7)]}
    previous['SPEECH']['artifacts'] = [artifact(f'speech_{i}', 'INTERMEDIATE', 'SPEECH_AUDIO', 'wav') for i in range(1, 7)]
    plan = build_plan(context)
    previous['GRAPHICS'] = {'graphics': plan.model_dump(), 'artifacts':
        [artifact('graphics_title', 'INTERMEDIATE', 'GRAPHICS_OVERLAY', 'png')]
        + [artifact(f'caption_{i}', 'INTERMEDIATE', 'GRAPHICS_OVERLAY', 'png') for i in range(1, 7)]}
    return context


class EncodingPlanTest(unittest.TestCase):
    def test_opposite_provenance_is_rejected_before_rendering(self):
        from app.wan import plan_requests
        from app.test_wan import context as wan_context
        cloud = encoding_context('CLOUD')
        cloud['previous_results']['SCENES']['sources'] = [dict(
            scene_position=1, artifact_key='scene_1', video_id=123, file_id=456,
            query='test only', video_page='https://www.pexels.com/video/123/',
            creator='Controlled fixture', creator_page='https://www.pexels.com/@fixture/',
            scene_duration_seconds=7.5, duration_seconds=8, width=720, height=1280, fps=24)]
        local = encoding_context('LOKAL')
        planned = plan_requests(wan_context())[0][2]
        local['previous_results']['SCENES']['wan_sources'] = [dict(scene_position=1,
            artifact_key='scene_1', scene_duration_seconds=6, duration_seconds=6,
            clips=[dict(request=r.model_dump(mode='json'), execution='CONTROLLED_TEST',
                result_path=f'wan/{r.job_id}/clip.mp4', size_bytes=100, checksum_sha256='a'*64,
                duration_seconds=81/16) for r in planned])]
        for body in (cloud, local):
            with self.subTest(mode=body['mode']):
                with self.assertRaises(StageFailure) as caught: encoding_plan(body)
                self.assertEqual(caught.exception.code, 'MODE_MISMATCH')

    def test_legacy_graphics_cannot_reintroduce_scene_counters_on_resume(self):
        context = encoding_context()
        context['previous_results']['GRAPHICS']['graphics']['template_version'] = 'v1'
        with self.assertRaises(StageFailure) as caught:
            encoding_plan(context)
        self.assertEqual(caught.exception.code, 'GRAPHICS_STYLE_OUTDATED')

    def test_both_modes_preserve_graphics_and_speech_timeline(self):
        for mode in ('LOKAL', 'CLOUD'):
            context = encoding_context(mode)
            plan, inputs = encoding_plan(context)
            self.assertEqual(plan, build_plan(context))
            self.assertEqual(plan.duration_frames, 1080)
            self.assertEqual(len(inputs), 19)

    def test_mixed_sources_and_wrong_context_type_are_rejected(self):
        for mode in ('LOKAL', 'CLOUD'):
            for change in ('source', 'context'):
                context = encoding_context(mode)
                wrong = 'AI_GENERATED_VIDEO' if mode == 'LOKAL' else 'STOCK_VIDEO'
                if change == 'source': context['previous_results']['SCENES']['artifacts'][0]['media_type'] = wrong
                else: context['media_type'] = wrong
                with self.assertRaises(StageFailure) as caught:
                    encoding_plan(context)
                self.assertEqual(caught.exception.code, 'MODE_MISMATCH')

    def test_missing_duplicate_or_changed_timing_blocks_encoding(self):
        original = encoding_context()
        for change in ('missing', 'duplicate', 'timing', 'text', 'audio-key', 'graphic-kind'):
            context = copy.deepcopy(original)
            previous = context['previous_results']
            if change == 'missing': previous['SCENES']['artifacts'].pop()
            if change == 'duplicate': previous['SCENES']['artifacts'][1] = previous['SCENES']['artifacts'][0]
            if change == 'timing': previous['GRAPHICS']['graphics']['scenes'][0]['caption_frames'] += 1
            if change == 'text': previous['SPEECH']['speech'][0]['text'] = 'Nicht freigegeben'
            if change == 'audio-key': previous['SPEECH']['speech'][0]['artifact_key'] = 'speech_9'
            if change == 'graphic-kind': previous['GRAPHICS']['artifacts'][0]['kind'] = 'SOURCE'
            with self.assertRaises(StageFailure):
                encoding_plan(context)


def png_fixture(path, color, top, bottom):
    def chunk(tag, data):
        return struct.pack('>I', len(data))+tag+data+struct.pack('>I', zlib.crc32(tag+data))
    clear = b'\0' + b'\0'*720*4
    filled = b'\0' + bytes(color)*720
    rows = b''.join(filled if top <= y < bottom else clear for y in range(1280))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', 720, 1280, 8, 6, 0, 0, 0))
                     +chunk(b'IDAT', zlib.compress(rows))+chunk(b'IEND', b''))


def media_fixture(root, mode='LOKAL'):
    """Explicit colored video/tone/overlay fixtures; no provider call."""
    context = encoding_context(mode)
    context['run_id'] = str(uuid4())
    inputs = root/'inputs'; inputs.mkdir(exist_ok=True)
    source = inputs/'source.mp4'
    if not source.exists():
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-y',
                        '-f', 'lavfi', '-i', 'color=c=blue:s=480x854:r=30:d=5',
                        '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=5',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', str(source)], check=True)
    for scene, segment in zip(context['scenes'], context['previous_results']['SPEECH']['speech']):
        scene['duration_seconds'] = 5
        segment.update(duration_seconds=1, frames=22050)
        path = inputs/f"speech_{scene['position']}.wav"
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((1, 2, 22050, 0, 'NONE', 'not compressed'))
            pcm = array('h', (int(2400*math.sin(2*math.pi*440*i/22050)) for i in range(22050)))
            wav.writeframes(pcm.tobytes())
    context['previous_results']['GRAPHICS']['graphics'] = build_plan(context).model_dump()
    for group in context['previous_results'].values():
        for artifact in group['artifacts']:
            path = root/artifact['storage_path']
            if artifact['kind'] == 'SOURCE':
                artifact['storage_path'] = 'inputs/source.mp4'; path = source
            elif artifact['media_type'] == 'GRAPHICS_OVERLAY':
                title = artifact['key'] == 'graphics_title'
                png_fixture(path, (0,255,0,255) if title else (255,0,0,255), 96 if title else 450, 200 if title else 550)
            artifact['checksum_sha256'] = checksum(path)
    return context


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/ffprobe required')
class EncodingRenderTest(unittest.TestCase):
    def setUp(self):
        self.files = tempfile.TemporaryDirectory(prefix='encoding test umlaut-ü-')
        self.addCleanup(self.files.cleanup)
        self.root = Path(self.files.name)
        environment = patch.dict(os.environ, {'MEDIA_ROOT': str(self.root)})
        environment.start(); self.addCleanup(environment.stop)
        self.context = media_fixture(self.root)

    def test_input_hash_path_short_source_and_overlay_damage_stop_before_ffmpeg(self):
        from app.encoding import encode_video
        for case in ('hash', 'escape', 'short', 'png', 'audio', 'mixed'):
            context = copy.deepcopy(self.context)
            source = context['previous_results']['SCENES']['artifacts'][0]
            if case == 'hash': source['checksum_sha256'] = 'b'*64
            if case == 'mixed': source['media_type'] = 'AI_GENERATED_VIDEO'
            if case == 'escape': source['storage_path'] = '../outside.mp4'
            if case == 'short':
                context['scenes'][0]['duration_seconds'] = 6
                context['previous_results']['GRAPHICS']['graphics'] = build_plan(context).model_dump()
            if case in ('png', 'audio'):
                name = 'GRAPHICS' if case == 'png' else 'SPEECH'
                artifact = context['previous_results'][name]['artifacts'][0]
                bad = self.root/'inputs'/f'{case}.bad'; bad.write_bytes(b'broken')
                artifact.update(storage_path=f'inputs/{case}.bad', checksum_sha256=checksum(bad))
            with patch('app.encoding.run_ffmpeg') as launch, self.assertRaises(StageFailure):
                encode_video(context)
            launch.assert_not_called()

    def test_actual_master_has_exact_frames_audio_overlays_and_verified_cache(self):
        from app.encoding import encode_video, inspect_master
        for mode in ('LOKAL', 'CLOUD'):
            context = copy.deepcopy(self.context)
            context['mode'] = mode
            context['media_type'] = 'STOCK_VIDEO' if mode == 'LOKAL' else 'AI_GENERATED_VIDEO'
            for artifact in context['previous_results']['SCENES']['artifacts']:
                artifact['media_type'] = context['media_type']
            context['run_id'] = str(uuid4())
            result = encode_video(context)
            self.assertEqual(len(result['artifacts']), 1)
            artifact = result['artifacts'][0]
            self.assertEqual((artifact['kind'], artifact['media_type']), ('INTERMEDIATE', 'FINAL_VIDEO'))
            target = self.root/artifact['storage_path']
            self.assertEqual(result['encoding']['duration_frames'], 720)
            inspect_master(target, 720, shutil.which('ffprobe'), shutil.which('ffmpeg'))
            if mode == 'LOKAL':
                # Captions end with speech; the stored project-title graphic
                # must never cover the source, including at the beginning.
                for time, y, wanted in [('0.5',500,'red'), ('1.5',500,'blue'), ('0.5',120,'blue'), ('4.5',120,'blue')]:
                    pixel = subprocess.check_output([shutil.which('ffmpeg'), '-v','error','-ss',time,'-i',str(target),
                        '-vf',f'crop=2:2:100:{y},format=rgb24','-frames:v','1','-f','rawvideo','-'])[:3]
                    self.assertGreater(pixel[{'red':0,'green':1,'blue':2}[wanted]], 180)
                pcm = subprocess.check_output([shutil.which('ffmpeg'),'-v','error','-i',str(target),'-vn','-f','s16le','-ac','1','-ar','48000','-'])
                samples = array('h'); samples.frombytes(pcm)
                self.assertGreater(max(abs(x) for x in samples[2400:36000]), 1000)
                self.assertLess(max(abs(x) for x in samples[96000:144000]), 32)
            before = {p:p.stat().st_mtime_ns for p in target.parent.glob('*.mp4')}
            with patch('app.encoding.run_ffmpeg', wraps=__import__('app.encoding',fromlist=['run_ffmpeg']).run_ffmpeg) as launch:
                self.assertEqual(encode_video(context), result)
                launch.assert_not_called()
            target.write_bytes(b'broken cache')
            repaired = encode_video(context)
            self.assertEqual(repaired['encoding'], result['encoding'])
            self.assertEqual({p:v for p,v in before.items() if p!=target}, {p:p.stat().st_mtime_ns for p in target.parent.glob('scene_*.mp4')})
            self.assertFalse(list(target.parent.glob('*.part*')))
