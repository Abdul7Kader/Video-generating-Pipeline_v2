"""HTTP/OpenAPI contract checks against an isolated PostgreSQL schema."""

import os
import copy
import unittest
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql

from app.main import app
from app.migrate import migrate


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL required")
class ApiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_url = os.environ["DATABASE_URL"]
        cls.schema = "api_test_" + uuid4().hex
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        separator = "&" if "?" in cls.original_url else "?"
        os.environ["DATABASE_URL"] = (
            cls.original_url + separator + "options=-csearch_path%3D" + cls.schema
        )
        migrate()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        os.environ["DATABASE_URL"] = cls.original_url
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def project(self, mode="LOKAL"):
        response = self.client.post("/api/projects", json={"idea": "Ein Testvideo", "mode": mode})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    @staticmethod
    def script_payload(mode="LOKAL", expected_version=0):
        scenes = []
        for position in range(6):
            scene = {
                "narration": f"Satz {position + 1}",
                "visual_description": f"Bild {position + 1}",
            }
            scene["pexels_query" if mode == "LOKAL" else "wan_prompt"] = "garden flowers"
            scenes.append(scene)
        return {
            "expected_version": expected_version,
            "title": "Testtitel",
            "narration": "Gesamter Sprechertext",
            "scenes": scenes,
        }

    def test_openapi_and_project_validation(self):
        spec = self.client.get("/api/openapi.json")
        self.assertEqual(spec.status_code, 200)
        for path in (
            "/api/projects", "/api/projects/{project_id}",
            "/api/projects/{project_id}/scripts",
            "/api/projects/{project_id}/scripts/{version}/approval",
            "/api/projects/{project_id}/videos/{artifact_id}/approval",
            "/api/projects/{project_id}/status",
            "/api/artifacts/{artifact_id}/content",
        ):
            self.assertIn(path, spec.json()["paths"])
        self.assertIn("409", spec.json()["paths"]["/api/projects/{project_id}/scripts"]["post"]["responses"])
        self.assertIn(
            "200", spec.json()["paths"]["/api/projects/{project_id}/scripts/{version}/approval"]["post"]["responses"],
        )
        bad = self.client.post("/api/projects", json={"idea": " ", "mode": "LOKAL"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()["error"]["code"], "VALIDATION_ERROR")
        extra = self.client.post("/api/projects", json={"idea": "x", "mode": "CLOUD", "secret": "x"})
        self.assertEqual(extra.status_code, 422)
        missing = self.client.get(f"/api/projects/{uuid4()}")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "PROJECT_NOT_FOUND")

    def test_versioned_script_approval_and_status(self):
        project = self.project()
        project_id = project["id"]
        self.assertEqual(project["media_type"], "STOCK_VIDEO")
        self.assertEqual(self.client.get(f"/api/projects/{project_id}").json()["idea"], project["idea"])
        status = self.client.get(f"/api/projects/{project_id}/status").json()
        self.assertIsNone(status["latest_script_version"])
        url = f"/api/projects/{project_id}/scripts"
        payload = self.script_payload()
        invalid = self.script_payload()
        invalid["scenes"][0]["wan_prompt"] = "wrong source"
        response = self.client.post(url, json=invalid)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "MODE_MISMATCH")
        first = self.client.post(url, json=payload)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["version"], 1)
        self.assertEqual(len(first.json()["scenes"]), 6)
        self.assertEqual(self.client.get(url).json()[0]["version"], 1)
        self.assertEqual(self.client.get(url + "/1").json()["scenes"][0]["position"], 1)
        conflict = self.client.post(url, json=payload)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error"]["code"], "VERSION_CONFLICT")
        next_payload = self.script_payload(expected_version=1)
        second = self.client.post(url, json=next_payload)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["version"], 2)
        stale = self.client.post(url + "/1/approval")
        self.assertEqual(stale.status_code, 409)
        approve = self.client.post(url + "/2/approval")
        self.assertEqual(approve.status_code, 201, approve.text)
        repeat = self.client.post(url + "/2/approval")
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(repeat.json()["production_run_id"], approve.json()["production_run_id"])
        status = self.client.get(f"/api/projects/{project_id}/status").json()
        self.assertEqual(status["latest_script_version"], 2)
        self.assertTrue(status["script_approved"])
        self.assertEqual(status["production_state"], "QUEUED")
        self.assertEqual(status["production_run_id"], approve.json()["production_run_id"])

    def test_cloud_mode_and_media_contract(self):
        project = self.project("CLOUD")
        project_id = project["id"]
        self.assertEqual(project["media_type"], "AI_GENERATED_VIDEO")
        script = self.client.post(
            f"/api/projects/{project_id}/scripts", json=self.script_payload("CLOUD"),
        )
        self.assertEqual(script.status_code, 201, script.text)
        self.assertEqual(script.json()["scenes"][0]["media_type"], "AI_GENERATED_VIDEO")
        missing = self.client.get(f"/api/artifacts/{uuid4()}")
        self.assertEqual(missing.status_code, 404)
        approve = self.client.post(f"/api/projects/{project_id}/scripts/1/approval").json()
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            conn.execute("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (approve["production_run_id"],))
            conn.execute("UPDATE production_runs SET state = 'COMPLETED' WHERE id = %s", (approve["production_run_id"],))
            artifact_id = conn.execute(
                "INSERT INTO artifacts (project_id, production_run_id, kind, media_type, "
                "storage_path, checksum_sha256) VALUES (%s, %s, 'FINAL', 'FINAL_VIDEO', "
                "'future/video.mp4', %s) RETURNING id",
                (project_id, approve["production_run_id"], "a" * 64),
            ).fetchone()[0]
        metadata = self.client.get(f"/api/artifacts/{artifact_id}")
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(metadata.json()["kind"], "FINAL")
        self.assertNotIn("storage_path", metadata.json())
        self.assertFalse(metadata.json()["content_available"])
        content = self.client.get(f"/api/artifacts/{artifact_id}/content")
        self.assertEqual(content.status_code, 401)
        self.assertEqual(content.json()["error"]["code"], "MEDIA_AUTH_REQUIRED")
        approval_url = f"/api/projects/{project_id}/videos/{artifact_id}/approval"
        wrong = self.client.post(approval_url, json={"checksum_sha256": "b" * 64})
        self.assertEqual(wrong.status_code, 409)
        self.assertEqual(wrong.json()["error"]["code"], "ARTIFACT_CONFLICT")
        approved = self.client.post(approval_url, json={"checksum_sha256": "a" * 64})
        self.assertEqual(approved.status_code, 201, approved.text)
        repeated = self.client.post(approval_url, json={"checksum_sha256": "a" * 64})
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.json()["id"], approved.json()["id"])
        status = self.client.get(f"/api/projects/{project_id}/status").json()
        self.assertTrue(status["video_approved"])
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            publications = conn.execute("SELECT count(*) FROM platform_publications").fetchone()[0]
        self.assertEqual(publications, 0)

    def test_complete_edits_preserve_metadata_and_old_versions(self):
        source = self.script_payload()
        source["target_duration_seconds"] = 36
        for mode in ("LOKAL", "CLOUD"):
            with self.subTest(mode=mode):
                project_id = self.project(mode)["id"]
                url = f"/api/projects/{project_id}/scripts"
                scenes = []
                for original in source["scenes"]:
                    scene = {key: original[key] for key in ("narration", "visual_description")}
                    scene["duration_seconds"] = 6
                    scene.update({"pexels_queries": [original["pexels_query"], "urban balcony"]} if mode == "LOKAL" else {"wan_prompt": "A peaceful urban balcony with flowers, natural light, slow camera movement."})
                    scenes.append(scene)
                payload = {"expected_version": 0, "title": source["title"], "language": "de-DE",
                           "narration": " ".join(scene["narration"] for scene in scenes),
                           "target_duration_seconds": source["target_duration_seconds"], "scenes": scenes}
                first = self.client.post(url, json=payload)
                self.assertEqual(first.status_code, 201, first.text)
                edited = copy.deepcopy(payload)
                edited.update(expected_version=1, title="Geprüfte neue Version")
                edited["scenes"][0]["narration"] = "Unser Balkon wird zum Lebensraum für Bienen."
                edited["narration"] = " ".join(scene["narration"] for scene in edited["scenes"])
                second = self.client.post(url, json=edited)
                self.assertEqual(second.status_code, 201, second.text)
                stored = self.client.get(url + "/2").json()
                self.assertEqual(stored["target_duration_seconds"], source["target_duration_seconds"])
                self.assertEqual(stored["scenes"][0]["duration_seconds"], scenes[0]["duration_seconds"])
                self.assertEqual(stored["narration"], edited["narration"])
                field = "pexels_queries" if mode == "LOKAL" else "wan_prompt"
                self.assertEqual(stored["scenes"][0][field], scenes[0][field])
                self.assertEqual(self.client.get(url + "/1").json(), first.json())
                self.assertEqual(self.client.post(url, json=edited).status_code, 409)
                invalid = copy.deepcopy(edited)
                invalid["expected_version"] = 2
                invalid["target_duration_seconds"] += 1
                self.assertEqual(self.client.post(url, json=invalid).status_code, 422)
                invalid["target_duration_seconds"] = None
                self.assertEqual(self.client.post(url, json=invalid).status_code, 422)
                invalid = copy.deepcopy(edited)
                invalid["expected_version"] = 2
                invalid["narration"] = "Unvollständiger Gesamttext"
                self.assertEqual(self.client.post(url, json=invalid).status_code, 422)
                if mode == "LOKAL":
                    invalid = copy.deepcopy(edited)
                    invalid["expected_version"] = 2
                    invalid["scenes"][0]["pexels_queries"] = ["flowers", "flowers"]
                    self.assertEqual(self.client.post(url, json=invalid).status_code, 422)
                self.assertEqual(len(self.client.get(url).json()), 2)


if __name__ == "__main__":
    unittest.main()
