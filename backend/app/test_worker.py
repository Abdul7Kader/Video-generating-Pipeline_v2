"""Installation checks reject missing prerequisites before consuming jobs."""

import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.antigravity import GenerationFailure
from app.worker import check_installation, main


class WorkerInstallationTest(unittest.TestCase):
    def test_missing_cli_and_unsafe_credits_fail_before_service_access(self):
        with patch("app.worker.shutil.which", return_value=None), \
             patch("app.worker.psycopg.connect") as database:
            with self.assertRaises(GenerationFailure) as caught:
                check_installation()
            self.assertEqual(caught.exception.code, "AGY_UNAVAILABLE")
            database.assert_not_called()

        with patch("app.worker.shutil.which", return_value="agy"), \
             patch("app.worker._safe_settings", side_effect=GenerationFailure("CREDIT_GUARD_UNVERIFIED", "Gesperrt")), \
             patch("app.worker.psycopg.connect") as database:
            with self.assertRaises(GenerationFailure) as caught:
                check_installation()
            self.assertEqual(caught.exception.code, "CREDIT_GUARD_UNVERIFIED")
            database.assert_not_called()

    def test_check_mode_reads_private_config_without_starting_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "worker.json"
            config.write_text(json.dumps({
                "DATABASE_URL": "postgresql://user:test-only@localhost/test",
                "REDIS_URL": "redis://localhost:6380/0",
            }), encoding="utf-8")
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), \
                 patch("app.worker.Path.home", return_value=Path(directory)), \
                 patch("sys.argv", ["worker", "--check", "--config", str(config)]), \
                 patch("sys.stdout", output), \
                 patch("app.worker.check_installation") as check, \
                 patch("app.worker.host_worker_class") as worker:
                main()
                self.assertIn("test-only", os.environ["DATABASE_URL"])
            check.assert_called_once()
            worker.assert_not_called()
            self.assertNotIn("test-only", output.getvalue())
            self.assertIn("Anmeldung", output.getvalue())


if __name__ == "__main__":
    unittest.main()
