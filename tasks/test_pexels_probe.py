"""Lokale Prüfung der Dateiauswahl; der echte API-Test braucht einen Key."""

import unittest

from pexels_probe import candidate, slug_match_score, suitable_files


class PexelsProbeTests(unittest.TestCase):
    def test_selects_sufficient_portrait_mp4(self):
        video = {
            "duration": 8,
            "video_files": [
                {"id": 1, "file_type": "video/mp4", "width": 640, "height": 1138,
                 "link": "https://videos.pexels.com/low.mp4"},
                {"id": 2, "file_type": "video/mp4", "width": 720, "height": 1280,
                 "link": "https://videos.pexels.com/fit.mp4"},
                {"id": 3, "file_type": "video/webm", "width": 1080, "height": 1920,
                 "link": "https://videos.pexels.com/other.webm"},
            ],
        }
        self.assertEqual([item["id"] for item in suitable_files(video, 7)], [2])
        self.assertEqual(suitable_files(video, 9), [])

    def test_keeps_source_and_contributor(self):
        video = {
            "id": 123, "url": "https://www.pexels.com/video/123/", "duration": 8,
            "user": {"name": "Example", "url": "https://www.pexels.com/@example"},
        }
        file = {"id": 456, "width": 720, "height": 1280, "fps": 24}
        result = candidate(video, file, "bee", 1)
        self.assertEqual(result["video_id"], 123)
        self.assertEqual(result["file_id"], 456)
        self.assertEqual(result["videographer"], "Example")

    def test_slug_hint_rejects_off_topic_train(self):
        train = {"url": "https://www.pexels.com/video/a-train-passes-a-building-27495247/"}
        balcony = {"url": "https://www.pexels.com/video/vibrant-balcony-flowers-34157136/"}
        self.assertEqual(slug_match_score(train, "flower box balcony"), 0)
        self.assertEqual(slug_match_score(balcony, "flower box balcony"), 2)


if __name__ == "__main__":
    unittest.main()
