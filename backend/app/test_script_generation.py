"""Script job API and worker checks against an isolated PostgreSQL schema."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from redis import Redis
from rq import Queue, SimpleWorker

from app.antigravity import GenerationFailure, generate
from app.main import app
from app.migrate import migrate
from app.script_contract import validate_script
from app.script_jobs import run_generation
from app.worker import host_worker_class


def sample_script(mode):
    media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
    scenes = []
    for index in range(1, 7):
        scene = {
            "index": index, "duration_seconds": 6, "narration": f"Satz {index}.",
            "visual_description": f"Bild {index}.", "media_type": media,
        }
        if mode == "LOKAL":
            scene["pexels_queries"] = [f"Suchwort {index}", f"search {index}"]
        else:
            scene["wan_prompt"] = f"A detailed scene {index}"
        scenes.append(scene)
    payload = {
        "title": "Testskript", "language": "de-DE", "mode": mode,
        "target_duration_seconds": 36, "scenes": scenes,
    }
    return validate_script(json.dumps(payload), mode)


def spawn_probe():
    return "spawn-worker-ok"


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL required")
class ScriptGenerationIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_url = os.environ["DATABASE_URL"]
        cls.schema = "generation_test_" + uuid4().hex
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
        separator = "&" if "?" in cls.original_url else "?"
        os.environ["DATABASE_URL"] = cls.original_url + separator + "options=-csearch_path%3D" + cls.schema
        migrate()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        os.environ["DATABASE_URL"] = cls.original_url
        with psycopg.connect(cls.original_url) as conn:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(cls.schema)))

    def project(self, mode):
        response = self.client.post("/api/projects", json={"idea": "Eine klare Videoidee", "mode": mode})
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def start(self, project_id):
        with patch("app.api.Queue.enqueue") as enqueue:
            response = self.client.post(f"/api/projects/{project_id}/script-generations")
            if response.status_code == 202:
                enqueue.assert_called_once()
                self.assertEqual(enqueue.call_args.args[0], "app.script_jobs.run_generation")
            return response

    def test_persisted_lokal_and_cloud_scripts(self):
        for mode in ("LOKAL", "CLOUD"):
            project_id = self.project(mode)
            first = self.start(project_id)
            self.assertEqual(first.status_code, 202, first.text)
            repeat = self.start(project_id)
            self.assertEqual(repeat.status_code, 200)
            self.assertEqual(repeat.json()["id"], first.json()["id"])
            with patch("app.script_jobs.generate", return_value=sample_script(mode)):
                run_generation(first.json()["id"])
            job = self.client.get(f"/api/projects/{project_id}/script-generations/{first.json()['id']}")
            self.assertEqual(job.json()["state"], "COMPLETED", job.text)
            script = self.client.get(f"/api/projects/{project_id}/scripts/1")
            self.assertEqual(script.status_code, 200, script.text)
            self.assertEqual(script.json()["target_duration_seconds"], 36)
            self.assertEqual([scene["position"] for scene in script.json()["scenes"]], list(range(1, 7)))
            if mode == "LOKAL":
                self.assertEqual(script.json()["scenes"][0]["pexels_queries"], ["Suchwort 1", "search 1"])
                self.assertIsNone(script.json()["scenes"][0]["wan_prompt"])
            else:
                self.assertEqual(script.json()["scenes"][0]["wan_prompt"], "A detailed scene 1")
                self.assertIsNone(script.json()["scenes"][0]["pexels_queries"])
            self.assertEqual(self.start(project_id).status_code, 409)

    def test_missing_auth_fails_and_explicit_retry_creates_new_job(self):
        project_id = self.project("LOKAL")
        first = self.start(project_id).json()
        with patch("app.script_jobs.generate", side_effect=GenerationFailure("AUTH_REQUIRED", "Worker nicht angemeldet")):
            run_generation(first["id"])
        failed = self.client.get(f"/api/projects/{project_id}/script-generations/{first['id']}").json()
        self.assertEqual(failed["state"], "FAILED")
        self.assertEqual(failed["error_code"], "AUTH_REQUIRED")
        retry = self.start(project_id)
        self.assertEqual(retry.status_code, 202)
        self.assertNotEqual(retry.json()["id"], first["id"])

    def test_real_redis_queue_runs_generation_and_persists_script(self):
        project_id = self.project("LOKAL")
        redis = Redis.from_url(os.environ["REDIS_URL"])
        queue = Queue("generation-test-" + uuid4().hex, connection=redis)
        with patch("app.api.Queue", side_effect=lambda name, connection: queue):
            response = self.client.post(f"/api/projects/{project_id}/script-generations")
        self.assertEqual(response.status_code, 202, response.text)
        with patch("app.script_jobs.generate", return_value=sample_script("LOKAL")):
            SimpleWorker([queue], connection=redis).work(burst=True)
        job = self.client.get(f"/api/projects/{project_id}/script-generations/{response.json()['id']}")
        self.assertEqual(job.json()["state"], "COMPLETED", job.text)
        self.assertEqual(self.client.get(f"/api/projects/{project_id}/scripts/1").status_code, 200)

    def test_host_worker_processes_a_real_redis_job(self):
        redis = Redis.from_url(os.environ["REDIS_URL"])
        queue = Queue("host-worker-test-" + uuid4().hex, connection=redis)
        job = queue.enqueue("app.test_script_generation.spawn_probe", result_ttl=60)
        host_worker_class()([queue], connection=redis).work(burst=True)
        job.refresh()
        self.assertEqual(job.return_value(), "spawn-worker-ok")


class AntigravityBoundaryTest(unittest.TestCase):
    def test_account_and_credit_guard_rejects_unsafe_settings(self):
        with tempfile.TemporaryDirectory() as home:
            settings_path = Path(home) / ".gemini" / "antigravity-cli" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            with patch("app.antigravity.Path.home", return_value=Path(home)):
                for settings in ({}, {"useG1Credits": True},
                                 {"useG1Credits": False, "modelProvider": "gemini"}):
                    settings_path.write_text(json.dumps(settings), encoding="utf-8")
                    with self.assertRaises(GenerationFailure):
                        generate("Idee", "LOKAL")

    def test_pins_supported_pro_model_and_removes_api_credentials(self):
        class Result:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"status": "SUCCESS", "response": json.dumps(sample_script("LOKAL"))})

        with patch("app.antigravity._safe_settings"), \
             patch("app.antigravity.subprocess.run", return_value=Result()) as run, \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test-only", "GOOGLE_API_KEY": "test-only"}):
            generate("Idee", "LOKAL")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--model") + 1], "gemini-3.1-pro-high")
        schema = json.loads(command[command.index("--json-schema") + 1])
        self.assertEqual(schema["properties"]["mode"]["enum"], ["LOKAL"])
        self.assertEqual(schema["properties"]["scenes"]["items"]["properties"]["media_type"]["enum"], ["STOCK_VIDEO"])
        self.assertIn("pexels_queries", schema["properties"]["scenes"]["items"]["required"])
        self.assertNotIn("wan_prompt", schema["properties"]["scenes"]["items"]["properties"])
        self.assertNotIn("GEMINI_API_KEY", run.call_args.kwargs["env"])
        self.assertNotIn("GOOGLE_API_KEY", run.call_args.kwargs["env"])

    def test_invalid_response_is_rejected(self):
        class Result:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"status": "SUCCESS", "response": "not a script"})

        with patch("app.antigravity._safe_settings"), patch("app.antigravity.subprocess.run", return_value=Result()):
            with self.assertRaises(GenerationFailure) as caught:
                generate("Idee", "LOKAL")
        self.assertEqual(caught.exception.code, "INVALID_SCRIPT")

    def test_cloud_schema_keeps_only_wan_source(self):
        class Result:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"status": "SUCCESS", "response": json.dumps(sample_script("CLOUD"))})

        with patch("app.antigravity._safe_settings"), \
             patch("app.antigravity.subprocess.run", return_value=Result()) as run:
            generate("Idee", "CLOUD")
        command = run.call_args.args[0]
        schema = json.loads(command[command.index("--json-schema") + 1])
        self.assertEqual(schema["properties"]["mode"]["enum"], ["CLOUD"])
        scene = schema["properties"]["scenes"]["items"]
        self.assertEqual(scene["properties"]["media_type"]["enum"], ["AI_GENERATED_VIDEO"])
        self.assertIn("wan_prompt", scene["required"])
        self.assertNotIn("pexels_queries", scene["properties"])

    def test_auth_and_quota_errors_are_actionable(self):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "authentication required"

        with patch("app.antigravity._safe_settings"), patch("app.antigravity.subprocess.run", return_value=Result()):
            with self.assertRaises(GenerationFailure) as caught:
                generate("Idee", "LOKAL")
        self.assertEqual(caught.exception.code, "AUTH_REQUIRED")
        Result.stderr = "quota exhausted"
        with patch("app.antigravity._safe_settings"), patch("app.antigravity.subprocess.run", return_value=Result()):
            with self.assertRaises(GenerationFailure) as caught:
                generate("Idee", "LOKAL")
        self.assertEqual(caught.exception.code, "QUOTA_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
