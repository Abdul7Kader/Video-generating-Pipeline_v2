"""Pinned model installer checks against controlled downloads only."""

import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('piper_installer', Path(__file__).resolve().parents[1] / 'deploy/install-piper.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PiperInstallerTest(unittest.TestCase):
    def test_verified_file_is_atomic_and_second_install_is_offline(self):
        content = b'controlled voice bytes'
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(installer, 'FILES', {'voice.onnx': hashlib.sha256(content).hexdigest()}), \
                patch.object(installer, 'urlopen', return_value=io.BytesIO(content)) as download:
            root = Path(directory)
            installer.install(root)
            self.assertEqual((root / 'voice.onnx').read_bytes(), content)
            installer.install(root)
            download.assert_called_once()
            self.assertFalse(list(root.glob('*.part')))

    def test_bad_hash_preserves_existing_file_and_removes_partial(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(installer, 'FILES', {'voice.onnx': 'a'*64}), \
                patch.object(installer, 'urlopen', return_value=io.BytesIO(b'tampered')):
            root = Path(directory)
            (root / 'voice.onnx').write_bytes(b'existing')
            with self.assertRaisesRegex(RuntimeError, 'Modellprüfsumme'):
                installer.install(root)
            self.assertEqual((root / 'voice.onnx').read_bytes(), b'existing')
            self.assertFalse(list(root.glob('*.part')))
