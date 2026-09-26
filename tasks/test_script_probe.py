import json
import unittest

from script_probe import make_prompt, validate_script


def example(mode="LOKAL"):
    scenes = []
    for index in range(1, 7):
        scene = {
            "index": index,
            "duration_seconds": 7,
            "narration": f"Das ist der deutsche Sprechertext für Szene {index}.",
            "visual_description": f"Eine eindeutige Bildbeschreibung für Szene {index}.",
            "media_type": "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO",
        }
        if mode == "LOKAL":
            scene["pexels_queries"] = ["bienenfreundlicher Balkon", "bee on flower balcony"]
        else:
            scene["wan_prompt"] = "Vertical cinematic shot of a rainy city, realistic motion."
        scenes.append(scene)
    return {
        "title": "Ein kurzes Beispielvideo",
        "language": "de-DE",
        "mode": mode,
        "target_duration_seconds": 42,
        "scenes": scenes,
    }


class ScriptProbeTests(unittest.TestCase):
    def test_valid_local_and_cloud_scripts(self):
        for mode in ("LOKAL", "CLOUD"):
            with self.subTest(mode=mode):
                self.assertEqual(validate_script(json.dumps(example(mode)), mode)["mode"], mode)

    def test_prompt_contains_idea_and_mode(self):
        prompt = make_prompt("Ein Stadtbalkon mit Bienen", "LOKAL")
        self.assertIn("Ein Stadtbalkon mit Bienen", prompt)
        self.assertIn("LOKAL", prompt)
        self.assertIn("pexels_queries", prompt)

    def test_rejects_malformed_and_partial_answers(self):
        with self.assertRaisesRegex(ValueError, "JSON"):
            validate_script("Hier ist dein Skript", "LOKAL")
        partial = example()
        del partial["scenes"][0]["visual_description"]
        with self.assertRaisesRegex(ValueError, "visual_description"):
            validate_script(json.dumps(partial), "LOKAL")

    def test_rejects_mixed_sources_and_wrong_mode(self):
        mixed = example()
        mixed["scenes"][2]["media_type"] = "AI_GENERATED_VIDEO"
        with self.assertRaisesRegex(ValueError, "media_type"):
            validate_script(json.dumps(mixed), "LOKAL")
        with self.assertRaisesRegex(ValueError, "mode"):
            validate_script(json.dumps(example("CLOUD")), "LOKAL")

    def test_rejects_bad_scene_count_order_and_duration(self):
        too_short = example()
        too_short["scenes"].pop()
        with self.assertRaisesRegex(ValueError, "scenes"):
            validate_script(json.dumps(too_short), "LOKAL")
        unordered = example()
        unordered["scenes"][1]["index"] = 1
        with self.assertRaisesRegex(ValueError, "index"):
            validate_script(json.dumps(unordered), "LOKAL")
        mistimed = example()
        mistimed["target_duration_seconds"] = 45
        with self.assertRaisesRegex(ValueError, "duration"):
            validate_script(json.dumps(mistimed), "LOKAL")


if __name__ == "__main__":
    unittest.main()
