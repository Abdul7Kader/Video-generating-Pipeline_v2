"""Speech validation with actual WAVs and ffprobe; no online synthesis."""

import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import wave

from app.production_stages import StageFailure
from app.speech import synthesize_scenes, inspect_audio


def speech_context(mode='LOKAL', count=2):
    return {'run_id': str(uuid4()), 'mode': mode, 'script': {'language': 'de-DE'},
            'scenes': [{'id': str(uuid4()), 'position': i, 'narration': f'Äpfel und Bienen, Szene {i}.'}
                       for i in range(1, count + 1)]}


class ControlledVoice:
    def __init__(self):
        self.texts = []
        self.failure = False
        self.silent = False

    def synthesize_wav(self, text, output):
        self.texts.append(text)
        if self.failure:
            raise RuntimeError('private provider detail must not appear')
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050)
        output.writeframes(struct.pack('<h', 0 if self.silent else 700) * 22050)


@unittest.skipUnless(shutil.which('ffprobe'), 'ffprobe required')
class SpeechTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.model = self.root / 'de_DE-thorsten-high.onnx'
        self.model.write_bytes(b'controlled model')
        Path(str(self.model)+'.json').write_text(json.dumps({'audio': {'sample_rate': 22050}, 'espeak': {'voice': 'de'}, 'num_speakers': 1}))
        self.voice = ControlledVoice()
        env = patch.dict(os.environ, {'MEDIA_ROOT': str(self.root/'media'), 'PIPER_MODEL_PATH': str(self.model),
                                     'FFPROBE_PATH': shutil.which('ffprobe')})
        env.start(); self.addCleanup(env.stop)
        load = patch('app.speech.load_voice', return_value=self.voice)
        self.loader = load.start(); self.addCleanup(load.stop)

    def test_both_modes_have_exact_durations_and_atomic_resume(self):
        for mode in ('LOKAL', 'CLOUD'):
            body = speech_context(mode)
            result = synthesize_scenes(body)
            self.assertEqual(len(result['speech']), 2)
            self.assertTrue(all(a['kind'] == 'INTERMEDIATE' and a['media_type'] == 'SPEECH_AUDIO' for a in result['artifacts']))
            for segment, artifact in zip(result['speech'], result['artifacts']):
                self.assertEqual(segment['duration_seconds'], 1)
                self.assertEqual(segment['frames'], 22050)
                path = self.root/'media'/artifact['storage_path']
                self.assertEqual(inspect_audio(path, 22050, shutil.which('ffprobe'))['duration_seconds'], segment['duration_seconds'])
            calls = len(self.voice.texts)
            self.assertEqual(synthesize_scenes(body), result)
            self.assertEqual(len(self.voice.texts), calls)
            self.assertFalse(list(self.root.rglob('*.part')))

    def test_empty_text_blocks_before_synthesis(self):
        body = speech_context(); body['scenes'][1]['narration'] = '  '
        with self.assertRaises(StageFailure) as caught:
            synthesize_scenes(body)
        self.assertEqual(caught.exception.code, 'SPEECH_TEXT_REQUIRED')
        self.assertIn('Szene 2', str(caught.exception))
        self.assertFalse(self.voice.texts)

    def test_missing_model_and_wrong_language_are_visible(self):
        self.model.unlink()
        with self.assertRaises(StageFailure) as caught:
            synthesize_scenes(speech_context())
        self.assertEqual(caught.exception.code, 'PIPER_MODEL_REQUIRED')
        body = speech_context(); body['script']['language'] = 'en-US'
        with self.assertRaises(StageFailure) as caught:
            synthesize_scenes(body)
        self.assertEqual(caught.exception.code, 'SPEECH_LANGUAGE_UNSUPPORTED')

    def test_silence_and_failed_output_block_without_manifest(self):
        for silent in (True, False):
            self.voice.silent = silent; self.voice.failure = not silent
            body = speech_context()
            with self.assertRaises(StageFailure) as caught:
                synthesize_scenes(body)
            self.assertEqual(caught.exception.code, 'SPEECH_OUTPUT_INVALID' if silent else 'SPEECH_SYNTHESIS_FAILED')
            self.assertNotIn('private', str(caught.exception))
            folder = self.root/'media'/'speech'/body['run_id']
            self.assertFalse(list(folder.glob('*.wav')))
            self.assertFalse((folder/'manifest.json').exists())
            self.assertFalse(list(folder.glob('*.part')))

    def test_corrupt_partial_segment_is_regenerated(self):
        body = speech_context(); first = synthesize_scenes(body)
        path = self.root/'media'/first['artifacts'][0]['storage_path']
        path.write_bytes(b'corrupt')
        self.voice.texts.clear()
        self.assertEqual(synthesize_scenes(body), first)
        self.assertEqual(len(self.voice.texts), 1)


if __name__ == '__main__':
    unittest.main()
