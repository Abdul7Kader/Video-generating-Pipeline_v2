import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.script_generation import GenerationError, invoke_antigravity, validate_script


def response(mode="LOKAL"):
    scenes = []
    for index in range(1, 7):
        scene = {
            "index": index, "duration_seconds": 7, "narration": f"Satz {index}",
            "visual_description": f"Bild {index}",
            "media_type": "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO",
        }
        scene["pexels_queries" if mode == "LOKAL" else "wan_prompt"] = (
            [f"query {index}", f"Suche {index}"] if mode == "LOKAL" else f"Cinematic scene {index}"
        )
        scenes.append(scene)
    return json.dumps({"title": "Titel", "language": "de-DE", "mode": mode,
                       "target_duration_seconds": 42, "scenes": scenes})


class ScriptGenerationTest(unittest.TestCase):
    def test_accepts_both_modes_and_rejects_arbitrary_text(self):
        self.assertEqual(len(validate_script(response(), "LOKAL")["scenes"]), 6)
        self.assertEqual(validate_script(response("CLOUD"), "CLOUD")["mode"], "CLOUD")
        with self.assertRaisesRegex(GenerationError, "kein gültiges Skript"):
            validate_script("Hier ist dein Skript!", "LOKAL")

    def test_rejects_wrong_source_and_duration(self):
        payload = json.loads(response())
        payload["scenes"][0]["media_type"] = "AI_GENERATED_VIDEO"
        with self.assertRaisesRegex(GenerationError, "falsche Medienquelle"):
            validate_script(json.dumps(payload), "LOKAL")
        payload = json.loads(response())
        payload["target_duration_seconds"] = 41
        with self.assertRaisesRegex(GenerationError, "Zieldauer"):
            validate_script(json.dumps(payload), "LOKAL")

    def test_requires_cost_guard_and_removes_api_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            settings.write_text('{"useG1Credits": true}', encoding="utf-8")
            with patch.dict(os.environ, {"ANTIGRAVITY_SETTINGS_PATH": str(settings)}):
                with self.assertRaisesRegex(GenerationError, "Credit-Überziehung"):
                    invoke_antigravity("prompt")
            settings.write_text('{"useG1Credits": false}', encoding="utf-8")
            completed = type("Result", (), {"returncode": 0, "stdout": json.dumps({"status": "SUCCESS", "response": response()}), "stderr": ""})()
            with patch.dict(os.environ, {"ANTIGRAVITY_SETTINGS_PATH": str(settings), "GEMINI_API_KEY": "secret"}), \
                    patch("app.script_generation.subprocess.run", return_value=completed) as run:
                self.assertEqual(invoke_antigravity("prompt"), response())
                self.assertNotIn("GEMINI_API_KEY", run.call_args.kwargs["env"])

    def test_maps_quota_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "settings.json"
            settings.write_text('{"useG1Credits": false}', encoding="utf-8")
            completed = type("Result", (), {"returncode": 1, "stdout": "", "stderr": "quota limit reached"})()
            with patch.dict(os.environ, {"ANTIGRAVITY_SETTINGS_PATH": str(settings)}), \
                    patch("app.script_generation.subprocess.run", return_value=completed):
                with self.assertRaises(GenerationError) as caught:
                    invoke_antigravity("prompt")
                self.assertEqual(caught.exception.code, "QUOTA_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
