"""Actual final publication, manifest integrity and portable storage."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from app.encoding import encode_video
from app.media import checksum
from app.production_stages import StageFailure
from app.storage import store_video
from app.test_encoding import media_fixture


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class StorageTest(unittest.TestCase):
    def test_real_master_manifest_cache_repair_and_input_tampering(self):
        with tempfile.TemporaryDirectory(prefix='Videoablage Grüße ') as name, patch.dict(os.environ, {'MEDIA_ROOT':name}):
            root = Path(name).resolve()
            context = media_fixture(root)
            context.update(project_id=str(uuid4()))
            context['script'].update(version=2, narration=' '.join(s['narration'] for s in context['scenes']))
            context['previous_results']['ENCODING'] = encode_video(context)
            result = store_video(context)
            final = result['artifacts'][0]
            self.assertEqual((final['key'], final['kind'], final['media_type']), ('master_video','FINAL','FINAL_VIDEO'))
            self.assertTrue(final['storage_path'].startswith(f"projects/{context['project_id']}/versions/2/runs/"))
            target, manifest = root/final['storage_path'], root/result['storage']['manifest_path']
            self.assertEqual(checksum(manifest),result['storage']['manifest_sha256'])
            payload=json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(len(payload['inputs']),20)
            self.assertEqual(payload['script']['narration'],context['script']['narration'])
            times=(target.stat().st_mtime_ns,manifest.stat().st_mtime_ns)
            self.assertEqual(store_video(context),result)
            self.assertEqual(times,(target.stat().st_mtime_ns,manifest.stat().st_mtime_ns))
            target.write_bytes(b'broken final')
            self.assertEqual(store_video(context),result)
            changed=copy.deepcopy(context)
            changed['previous_results']['ENCODING']['artifacts'][0]['checksum_sha256']='b'*64
            with self.assertRaises(StageFailure):
                store_video(changed)
            self.assertFalse(list(target.parent.glob('*.part')))
