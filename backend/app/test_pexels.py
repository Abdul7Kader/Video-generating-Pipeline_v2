"""Real MP4/ffprobe checks and controlled HTTP; no key or paid service required."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.pexels import collect_scenes, candidates, probe, MAX_DOWNLOAD
from app.production_stages import StageFailure


def context(count=2):
    return {"mode": "LOKAL", "media_type": "STOCK_VIDEO", "run_id": str(uuid4()),
            "scenes": [{"id": str(uuid4()), "position": i, "media_type": "STOCK_VIDEO",
                        "duration_seconds": 7, "pexels_queries": ["bee on lavender", "lavender flower"]}
                       for i in range(1, count + 1)]}


def video():
    return {"id": 123, "duration": 8, "url": "https://www.pexels.com/video/bee-on-lavender-123/",
            "user": {"name": "Test Creator", "url": "https://www.pexels.com/@test/"},
            "video_files": [{"id": 456, "file_type": "video/mp4", "width": 720, "height": 1280,
                             "link": "https://videos.pexels.com/video-files/123/456.mp4"}]}


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and ffprobe required')
class PexelsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = tempfile.TemporaryDirectory()
        clip = Path(cls.media.name) / 'sample.mp4'
        subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:s=720x1280:r=12:d=8', '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-pix_fmt', 'yuv420p', str(clip)], check=True, timeout=30)
        cls.clip = clip.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.media.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {'PEXELS_API_KEY': 'controlled-private-key', 'MEDIA_ROOT': str(self.root),
                                           'FFPROBE_PATH': shutil.which('ffprobe')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.requests = []
        self.status = 200
        self.videos = [video()]
        self.downloads = self.clip
        self.client = httpx.Client(transport=httpx.MockTransport(self.http), follow_redirects=False)
        self.addCleanup(self.client.close)

    def http(self, request):
        self.requests.append(request)
        if request.url.host == 'api.pexels.com':
            self.assertEqual(request.headers['Authorization'], 'controlled-private-key')
            return httpx.Response(self.status, json={'videos': self.videos})
        self.assertEqual(request.url.host, 'videos.pexels.com')
        self.assertNotIn('Authorization', request.headers)
        return httpx.Response(200, content=self.downloads, headers={'Content-Type': 'video/mp4'})

    def test_verified_manifest_and_resume_without_network(self):
        body = context()
        result = collect_scenes(body, self.client)
        self.assertEqual(len(result['artifacts']), 2)
        self.assertEqual(len(result['sources']), 2)
        self.assertTrue(all(a['media_type'] == 'STOCK_VIDEO' for a in result['artifacts']))
        self.assertEqual(result['sources'][0]['video_id'], 123)
        self.assertEqual(result['sources'][0]['file_id'], 456)
        self.assertEqual(result['sources'][0]['height'], 1280)
        self.assertEqual(sum(r.url.host == 'api.pexels.com' for r in self.requests), 1)
        self.requests.clear()
        self.assertEqual(collect_scenes(body, self.client), result)
        self.assertFalse(self.requests)
        manifest = self.root / 'sources' / body['run_id'] / 'manifest.json'
        self.assertEqual(json.loads(manifest.read_text()), result)
        self.assertNotIn('controlled-private-key', manifest.read_text())

    def test_partial_resume_and_corrupt_clip_repair(self):
        body = context()
        body['scenes'][1]['pexels_queries'] = ['train rain', 'tram rain']
        with self.assertRaises(StageFailure) as caught:
            collect_scenes(body, self.client)
        self.assertEqual(caught.exception.code, 'PEXELS_NO_MATCH')
        self.assertIn('Szene 2', str(caught.exception))
        directory = self.root / 'sources' / body['run_id']
        self.assertTrue((directory / 'scene-1.mp4').exists())
        self.assertFalse((directory / 'manifest.json').exists())
        # A later quota/cache window can bring new matching results.
        for cache in (self.root / 'pexels-search').glob('*.json'):
            cache.unlink()
        self.videos[0]['url'] = 'https://www.pexels.com/video/train-in-rain-123/'
        self.requests.clear()
        collect_scenes(body, self.client)
        self.assertEqual(sum(r.url.host == 'videos.pexels.com' for r in self.requests), 1)
        (directory / 'scene-1.mp4').write_bytes(b'corrupt')
        self.videos = [video()]
        self.requests.clear()
        collect_scenes(body, self.client)
        self.assertEqual(sum(r.url.host == 'videos.pexels.com' for r in self.requests), 1)
        self.assertFalse(list(directory.glob('*.part')))

    def test_missing_and_invalid_media_never_make_manifest(self):
        for payload in ([], [video()]):
            with self.subTest(payload=bool(payload)):
                self.videos = payload
                self.downloads = b'not a video'
                body = context(1)
                for path in (self.root / 'pexels-search').glob('*.json'):
                    path.unlink()
                with self.assertRaises(StageFailure) as caught:
                    collect_scenes(body, self.client)
                self.assertEqual(caught.exception.code, 'PEXELS_NO_MATCH')
                self.assertFalse(list((self.root / 'sources' / body['run_id']).glob('*.mp4')))
                self.assertFalse(list(self.root.rglob('*.part')))

    def test_rate_limit_auth_and_transient_errors_are_safe(self):
        for status, code, retry in ((401, 'PEXELS_AUTH_FAILED', False), (403, 'PEXELS_AUTH_FAILED', False),
                                    (429, 'PEXELS_QUOTA_EXHAUSTED', False), (503, 'PEXELS_UNAVAILABLE', True)):
            self.status = status
            self.requests.clear()
            with self.assertRaises(StageFailure) as caught:
                collect_scenes(context(1), self.client)
            self.assertEqual((caught.exception.code, caught.exception.retryable), (code, retry))
            self.assertEqual(len(self.requests), 1)
            self.assertNotIn('controlled-private-key', str(caught.exception))

    def test_mode_guard_before_credentials_or_network(self):
        body = context(1)
        body['mode'] = 'CLOUD'
        with patch('app.pexels.api_key', side_effect=AssertionError('must not read credentials')):
            with self.assertRaises(StageFailure) as caught:
                collect_scenes(body, self.client)
        self.assertEqual(caught.exception.code, 'MODE_MISMATCH')
        self.assertFalse(self.requests)

    def test_missing_key_and_ffprobe_are_actionable(self):
        with patch.dict(os.environ, {'PEXELS_API_KEY': ''}), patch('app.pexels.ROOT', self.root):
            with self.assertRaises(StageFailure) as caught:
                collect_scenes(context(1), self.client)
        self.assertEqual(caught.exception.code, 'PEXELS_KEY_REQUIRED')
        with patch.dict(os.environ, {'FFPROBE_PATH': str(self.root / 'missing')}):
            with self.assertRaises(StageFailure) as caught:
                collect_scenes(context(1), self.client)
        self.assertEqual(caught.exception.code, 'FFPROBE_REQUIRED')
        self.assertFalse(self.requests)

    def test_disconnect_preserves_partial_work_and_is_retryable(self):
        def fail(request):
            raise httpx.ReadTimeout('secret provider error', request=request)
        with httpx.Client(transport=httpx.MockTransport(fail)) as client:
            with self.assertRaises(StageFailure) as caught:
                collect_scenes(context(1), client)
        self.assertEqual(caught.exception.code, 'PEXELS_UNAVAILABLE')
        self.assertTrue(caught.exception.retryable)
        self.assertNotIn('secret', str(caught.exception))

    def test_cache_expiry_and_empty_results(self):
        self.videos = []
        body = context(1)
        for _ in range(2):
            with self.assertRaises(StageFailure):
                collect_scenes(body, self.client)
        self.assertEqual(len(self.requests), 2)  # two queries, then cache only
        for path in (self.root / 'pexels-search').glob('*.json'):
            data = json.loads(path.read_text()); data['saved_at'] = 0
            path.write_text(json.dumps(data))
        self.videos = [video()]
        collect_scenes(body, self.client)
        self.assertEqual(len(self.requests), 4)  # one new search, one clip

    def test_geometry_duration_relevance_and_host_allowlist(self):
        for changes in ({'duration': 6}, {'url': 'https://www.pexels.com/video/city-train-123/'},
                        {'video_files': [{**video()['video_files'][0], 'link': 'http://127.0.0.1/secret'}]},
                        {'video_files': [{**video()['video_files'][0], 'link': 'https://videos.pexels.com.attacker.test/a'}]},
                        {'video_files': [{**video()['video_files'][0], 'height': 720}]}):
            self.assertEqual(candidates([{**video(), **changes}], 'bee on lavender', 7), [])
        clip = self.root / 'short.mp4'
        clip.write_bytes(self.clip)
        with self.assertRaises(StageFailure):
            probe(clip, 9, shutil.which('ffprobe'))

    def test_oversize_and_redirect_are_not_downloaded(self):
        for response in (httpx.Response(200, headers={'content-length': str(MAX_DOWNLOAD + 1)}),
                         httpx.Response(302, headers={'location': 'http://127.0.0.1/private'})):
            requests = []
            def handler(request):
                requests.append(request)
                if request.url.host == 'api.pexels.com':
                    return httpx.Response(200, json={'videos': [video()]})
                return response
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(StageFailure):
                    collect_scenes(context(1), client)
            self.assertTrue(all(r.url.host in ('api.pexels.com', 'videos.pexels.com') for r in requests))
        self.assertFalse(list(self.root.rglob('*.part')))


if __name__ == '__main__':
    unittest.main()
