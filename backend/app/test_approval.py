"""Real database/Redis checks for immutable, single production approvals."""

from concurrent.futures import ThreadPoolExecutor
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import Queue

from app.main import app
from app.migrate import migrate
from app.test_script_generation import sample_script
from app.worker import host_worker_class
from app.production_stages import StageFailure


@unittest.skipUnless(os.getenv("DATABASE_URL") and os.getenv("REDIS_URL"), "PostgreSQL and Redis required")
class ApprovalIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_url = os.environ["DATABASE_URL"]
        cls.schema = "approval_test_" + uuid4().hex
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
        response = self.client.post("/api/projects", json={"idea": "Ein Freigabetest", "mode": mode})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def setUp(self):
        self.redis = Redis.from_url(os.environ["REDIS_URL"])
        self.queue = Queue("approval-test-" + uuid4().hex, connection=self.redis)
        self.queue_override = patch("app.api.Queue", return_value=self.queue)
        self.queue_override.start()
        self.addCleanup(self.queue_override.stop)
        self.addCleanup(self.queue.empty)

    def complete_project(self, mode="LOKAL"):
        project = self.project(mode)
        script = sample_script(mode)
        body = {"expected_version": 0, "title": script["title"], "language": script["language"],
                "target_duration_seconds": script["target_duration_seconds"],
                "narration": " ".join(scene["narration"] for scene in script["scenes"]),
                "scenes": [{key: value for key, value in scene.items() if key not in ("index", "media_type")}
                           for scene in script["scenes"]]}
        response = self.client.post(f"/api/projects/{project['id']}/scripts", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return project["id"], body

    def approve(self, project_id):
        return self.client.post(f"/api/projects/{project_id}/scripts/1/approval")

    def test_parallel_clicks_enqueue_one_job_and_one_run(self):
        project_id, _ = self.complete_project()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.approve(project_id), range(2)))
        self.assertEqual(sorted(response.status_code for response in results), [200, 201])
        run_ids = {response.json()["production_run_id"] for response in results}
        self.assertEqual(len(run_ids), 1)
        self.assertEqual(self.queue.count, 1)
        job = self.queue.fetch_job(str(next(iter(run_ids))))
        self.assertIsNotNone(job)
        self.assertEqual(job.func_name, "app.production_jobs.run_production")
        self.assertEqual(job.args, (str(next(iter(run_ids))),))
        self.assertEqual(self.approve(project_id).json()["production_run_id"], next(iter(run_ids)))
        self.assertEqual(self.queue.count, 1)

    def test_broker_failure_can_retry_same_committed_approval(self):
        project_id, _ = self.complete_project()
        with patch.object(self.queue, "enqueue", side_effect=RedisConnectionError("test-only")):
            response = self.approve(project_id)
        self.assertEqual(response.status_code, 503)
        status = self.client.get(f"/api/projects/{project_id}/status").json()
        self.assertTrue(status["script_approved"])
        retried = self.approve(project_id)
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["production_run_id"], status["production_run_id"])
        self.assertEqual(self.queue.count, 1)
        # Redis may accept the job even when its response is lost.
        other_id, _ = self.complete_project()
        enqueue = self.queue.enqueue
        def lost_response(*args, **kwargs):
            enqueue(*args, **kwargs)
            raise RedisConnectionError("response lost after enqueue")
        with patch.object(self.queue, "enqueue", side_effect=lost_response):
            self.assertEqual(self.approve(other_id).status_code, 503)
        self.assertEqual(self.queue.count, 2)
        self.assertEqual(self.approve(other_id).status_code, 200)
        self.assertEqual(self.queue.count, 2)

    def test_worker_blocks_unavailable_pipeline_without_fake_video(self):
        for mode in ("LOKAL", "CLOUD"):
            with self.subTest(mode=mode):
                project_id, _ = self.complete_project(mode)
                approved = self.approve(project_id)
                self.assertEqual(approved.status_code, 201, approved.text)
                # Approval is independent of installation secrets and live media services.
                with patch('app.production_jobs.run_stage', side_effect=StageFailure('STAGE_UNAVAILABLE', 'Medienadapter ist noch nicht verfügbar.')):
                    host_worker_class()([self.queue], connection=self.redis).work(burst=True)
                status = self.client.get(f"/api/projects/{project_id}/status").json()
                self.assertEqual(status["production_state"], "FAILED")
                self.assertIn("noch nicht", status["production_error"])
                self.assertIsNone(status["final_artifact_id"])
                self.assertEqual(self.approve(project_id).json()["production_run_id"], approved.json()["production_run_id"])
                self.assertEqual(self.queue.count, 0)

    def test_edited_version_requires_new_approval_and_old_job_cannot_start(self):
        project_id, body = self.complete_project()
        first = self.approve(project_id).json()
        body.update(expected_version=1, title="Neue Version")
        self.assertEqual(self.client.post(f"/api/projects/{project_id}/scripts", json=body).status_code, 201)
        self.assertEqual(self.approve(project_id).status_code, 409)
        current = self.client.get(f"/api/projects/{project_id}/status").json()
        self.assertFalse(current["script_approved"])
        self.assertIsNone(current["production_run_id"])
        host_worker_class()([self.queue], connection=self.redis).work(burst=True)
        from app.api import database
        with database() as connection:
            old = connection.execute("SELECT state, error_message FROM production_runs WHERE id = %s", (first["production_run_id"],)).fetchone()
        self.assertEqual(old["state"], "FAILED")
        self.assertIn("neuere", old["error_message"])
        second = self.client.post(f"/api/projects/{project_id}/scripts/2/approval")
        self.assertEqual(second.status_code, 201, second.text)
        self.assertNotEqual(second.json()["production_run_id"], first["production_run_id"])
