"""Frame timing and verified speech prerequisites for graphic overlays."""

import copy
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.production_stages import StageFailure
from app.graphics import build_plan, inspect_overlay, render_graphics
from app.speech import synthesize_scenes
from app import test_speech


def graphics_context(mode='LOKAL'):
    scenes = [{'position': i, 'duration_seconds': 7.5, 'narration': f'Über blühende Wiesen, Szene {i}.'} for i in range(1, 7)]
    segments = [dict(scene_position=s['position'], artifact_key=f"speech_{s['position']}", text=s['narration'],
                     voice='de_DE-thorsten-high', model_sha256='a'*64, config_sha256='b'*64, engine_version='1.8.0',
                     length_scale=1.15, duration_seconds=2.123, frames=46812, sample_rate=22050, channels=1)
                for s in scenes]
    for s in segments:
        s['duration_seconds'] = s['frames'] / s['sample_rate']
    return {'mode': mode, 'script': {'title': 'Bienen, Blüten & Grüße', 'language': 'de-DE', 'target_duration_seconds': 45},
            'scenes': scenes, 'previous_results': {'SPEECH': {'artifacts': [], 'speech': segments}}}


class GraphicsPlanTest(unittest.TestCase):
    def test_both_modes_use_audio_frames_and_preserve_planned_scene_holds(self):
        for mode in ('LOKAL', 'CLOUD'):
            result = build_plan(graphics_context(mode))
            self.assertEqual((result.width, result.height, result.fps, result.duration_frames), (720, 1280, 24, 1080))
            self.assertEqual([s.start_frame for s in result.scenes], [0, 180, 360, 540, 720, 900])
            self.assertTrue(all(s.caption_frames == 51 and s.duration_frames == 180 for s in result.scenes))
            self.assertEqual(result.title_frames, 96)

    def test_missing_changed_duplicate_and_inconsistent_speech_block_render(self):
        original = graphics_context()
        for change in ('missing', 'changed', 'duplicate', 'duration'):
            body = copy.deepcopy(original)
            speech = body['previous_results']['SPEECH']['speech']
            if change == 'missing': speech.pop()
            if change == 'changed': speech[0]['text'] = 'Unfreigegebener Text'
            if change == 'duplicate': speech[1]['scene_position'] = 1
            if change == 'duration': speech[0]['duration_seconds'] = 5
            with self.assertRaises(StageFailure) as caught:
                build_plan(body)
            self.assertEqual(caught.exception.code, 'GRAPHICS_SPEECH_REQUIRED')

    def test_long_speech_extends_scene_and_invalid_total_is_visible(self):
        body = graphics_context()
        segment = body['previous_results']['SPEECH']['speech'][0]
        segment['frames'] = 9*22050; segment['duration_seconds'] = 9
        self.assertEqual(build_plan(body).scenes[0].duration_frames, 216)
        self.assertEqual(build_plan(body).scenes[1].start_frame, 216)
        for s in body['previous_results']['SPEECH']['speech']:
            s['frames'] = 11*22050; s['duration_seconds'] = 11
        with self.assertRaises(StageFailure) as caught:
            build_plan(body)
        self.assertEqual(caught.exception.code, 'GRAPHICS_TIMELINE_INVALID')


@unittest.skipUnless(shutil.which('node') and shutil.which('ffprobe'), 'Node.js, installed Remotion and ffprobe required')
class GraphicsRenderTest(unittest.TestCase):
    setUp = test_speech.SpeechTest.setUp

    def test_actual_rgba_render_cache_corruption_repair_and_audio_blockade(self):
        for mode in ('LOKAL', 'CLOUD'):
            context = graphics_context(mode)
            context['run_id'] = str(uuid4())
            for scene in context['scenes']:
                scene['id'] = str(uuid4())
            context['previous_results']['SPEECH'] = synthesize_scenes(context)
            result = render_graphics(context)
            self.assertEqual(len(result['artifacts']), 7)
            self.assertEqual(result['graphics']['title'], context['script']['title'])
            self.assertEqual([s['caption_frames'] for s in result['graphics']['scenes']], [24]*6)
            files = [self.root/'media'/a['storage_path'] for a in result['artifacts']]
            before = {p: p.stat().st_mtime_ns for p in files}
            with patch.dict(os.environ, {'REMOTION_NODE_PATH': str(self.root/'missing-node')}):
                self.assertEqual(render_graphics(context), result)  # cached files require no Node process
            self.assertEqual(before, {p: p.stat().st_mtime_ns for p in files})
            # Truncated PNG must fail inspection and cannot pass a cached checkpoint.
            files[1].write_bytes(files[1].read_bytes()[:-10])
            with self.assertRaises(StageFailure) as caught:
                inspect_overlay(files[1], shutil.which('ffprobe'))
            self.assertEqual(caught.exception.code, 'GRAPHICS_OUTPUT_INVALID')
            with patch.dict(os.environ, {'REMOTION_NODE_PATH': str(self.root/'missing-node')}), self.assertRaises(StageFailure) as caught:
                render_graphics(context)
            self.assertEqual(caught.exception.code, 'REMOTION_REQUIRED')
            repaired = render_graphics(context)
            self.assertEqual(repaired, result)
            self.assertFalse(list(self.root.rglob('*.part')))
            audio = self.root/'media'/context['previous_results']['SPEECH']['artifacts'][0]['storage_path']
            audio.write_bytes(b'corrupt audio')
            with self.assertRaises(StageFailure) as caught:
                render_graphics(context)
            self.assertEqual(caught.exception.code, 'GRAPHICS_SPEECH_REQUIRED')
