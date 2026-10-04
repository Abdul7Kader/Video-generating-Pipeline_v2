"""Portable project paths must reject traversal and invalid identities."""
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from app.media import run_folder, safe_path
from app.production_stages import StageFailure


class MediaPathTest(unittest.TestCase):
    def setUp(self):
        self.files = tempfile.TemporaryDirectory(prefix='Speicher Grüße ')
        self.addCleanup(self.files.cleanup)
        self.root = Path(self.files.name).resolve()

    def test_project_version_paths_and_legacy_relative_files(self):
        context = dict(project_id=str(uuid4()), run_id=str(uuid4()), script={'version':2})
        folder = run_folder(self.root, context, 'encoding')
        self.assertEqual(folder, self.root/'projects'/context['project_id']/'versions/2/runs'/context['run_id']/'encoding')
        self.assertTrue(folder.is_dir())
        self.assertEqual(safe_path(self.root, 'speech/previous/file.wav'), self.root/'speech/previous/file.wav')
        context['script']['version'] = '../other'
        with self.assertRaises(StageFailure):
            run_folder(self.root, context, 'encoding')

    def test_absolute_traversal_windows_streams_and_symlinks_are_rejected(self):
        for value in ('../secret', '/etc/passwd', 'C:/secret', 'file.mp4:stream', 'a\\b', '.', ''):
            with self.subTest(value=value), self.assertRaises(StageFailure):
                safe_path(self.root, value)
        outside = self.root.parent/'outside-media-test'
        link = self.root/'link'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            return  # Windows installations without symlink rights still test all lexical guards.
        with self.assertRaises(StageFailure):
            safe_path(self.root, 'link/file.mp4')
