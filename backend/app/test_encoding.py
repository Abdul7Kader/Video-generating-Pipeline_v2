"""Encoding must preserve approved timing and reject mixed/incomplete inputs."""

import copy
import unittest

from app.graphics import build_plan
from app.production_stages import StageFailure
from app.test_graphics import graphics_context
from app.encoding import encoding_plan


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
