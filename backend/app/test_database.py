"""Real PostgreSQL checks for migration and approval/state guards."""

import os
import unittest

import psycopg


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL required")
class DatabaseRulesTest(unittest.TestCase):
    def setUp(self):
        self.db = psycopg.connect(os.environ["DATABASE_URL"])

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def insert(self, statement, values=()):
        return self.db.execute(statement + " RETURNING id", values).fetchone()[0]

    def rejected(self, statement, values=()):
        with self.assertRaises(psycopg.Error), self.db.transaction():
            self.db.execute(statement, values)

    def project(self, mode="LOKAL"):
        media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
        return self.insert(
            "INSERT INTO projects (idea, mode, media_type) VALUES (%s, %s, %s)",
            ("Testidee", mode, media),
        )

    def version(self, project, number=1):
        return self.insert(
            "INSERT INTO script_versions (project_id, version, title, narration) "
            "VALUES (%s, %s, 'Titel', 'Sprechertext')", (project, number),
        )

    def scene(self, project, version, mode="LOKAL", position=1):
        media = "STOCK_VIDEO" if mode == "LOKAL" else "AI_GENERATED_VIDEO"
        pexels = "Blumen" if mode == "LOKAL" else None
        wan = "Rainy city" if mode == "CLOUD" else None
        return self.insert(
            "INSERT INTO scenes (project_id, script_version_id, position, narration, "
            "visual_description, media_type, pexels_query, wan_prompt) "
            "VALUES (%s, %s, %s, 'Text', 'Bild', %s, %s, %s)",
            (project, version, position, media, pexels, wan),
        )

    def complete_script(self, project, version, mode="LOKAL"):
        for position in range(1, 7):
            self.scene(project, version, mode, position)

    def script_approval(self, project, version):
        return self.insert(
            "INSERT INTO approvals (project_id, kind, script_version_id) VALUES (%s, 'SCRIPT', %s)",
            (project, version),
        )

    def production_run(self, project, version, approval):
        return self.insert(
            "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
            "VALUES (%s, %s, %s)", (project, version, approval),
        )

    def test_mode_and_scene_media_are_enforced(self):
        self.rejected(
            "INSERT INTO projects (idea, mode, media_type) VALUES ('x', 'LOKAL', 'AI_GENERATED_VIDEO')"
        )
        for mode in ("LOKAL", "CLOUD"):
            project = self.project(mode)
            version = self.version(project)
            self.scene(project, version, mode)
            opposite = "CLOUD" if mode == "LOKAL" else "LOKAL"
            self.rejected(
                "INSERT INTO scenes (project_id, script_version_id, position, narration, "
                "visual_description, media_type, pexels_query, wan_prompt) "
                "VALUES (%s, %s, 2, 'Text', 'Bild', %s, %s, %s)",
                (project, version, "AI_GENERATED_VIDEO" if opposite == "CLOUD" else "STOCK_VIDEO",
                 "wrong" if opposite == "LOKAL" else None,
                 "wrong" if opposite == "CLOUD" else None),
            )
            self.rejected("UPDATE projects SET mode = %s WHERE id = %s", (opposite, project))

    def test_production_requires_current_approved_immutable_version(self):
        project = self.project()
        first = self.version(project)
        self.scene(project, first)
        self.rejected(
            "INSERT INTO approvals (project_id, kind, script_version_id) VALUES (%s, 'SCRIPT', %s)",
            (project, first),
        )
        for position in range(2, 7):
            self.scene(project, first, position=position)
        self.rejected(
            "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
            "VALUES (%s, %s, gen_random_uuid())", (project, first),
        )
        approval = self.script_approval(project, first)
        self.rejected("UPDATE script_versions SET title = 'changed' WHERE id = %s", (first,))
        self.rejected("UPDATE scenes SET narration = 'changed' WHERE script_version_id = %s", (first,))
        self.rejected(
            "INSERT INTO scenes (project_id, script_version_id, position, narration, "
            "visual_description, media_type, pexels_query) "
            "VALUES (%s, %s, 7, 'Text', 'Bild', 'STOCK_VIDEO', 'query')", (project, first),
        )
        second = self.version(project, 2)
        self.complete_script(project, second)
        self.rejected(
            "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
            "VALUES (%s, %s, %s)", (project, first, approval),
        )
        self.rejected(
            "INSERT INTO approvals (project_id, kind, script_version_id) VALUES (%s, 'SCRIPT', %s)",
            (project, first),
        )
        current = self.script_approval(project, second)
        run = self.production_run(project, second, current)
        self.rejected(
            "INSERT INTO production_runs (project_id, script_version_id, script_approval_id) "
            "VALUES (%s, %s, %s)", (project, second, current),
        )
        self.db.execute("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (run,))
        self.rejected("UPDATE production_runs SET state = 'QUEUED' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'FAILED' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'QUEUED' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'COMPLETED' WHERE id = %s", (run,))
        self.rejected("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (run,))

    def test_superseded_queued_run_can_fail_but_not_start(self):
        project = self.project()
        first = self.version(project)
        self.complete_script(project, first)
        approval = self.script_approval(project, first)
        run = self.production_run(project, first, approval)
        self.version(project, 2)
        self.rejected("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'FAILED' WHERE id = %s", (run,))

    def test_publication_requires_approved_exact_final_checksum(self):
        project = self.project()
        version = self.version(project)
        self.complete_script(project, version)
        approval = self.script_approval(project, version)
        run = self.production_run(project, version, approval)
        checksum = "a" * 64
        self.rejected(
            "INSERT INTO artifacts (project_id, production_run_id, kind, media_type, "
            "storage_path, checksum_sha256) VALUES (%s, %s, 'SOURCE', 'AI_GENERATED_VIDEO', 'x', %s)",
            (project, run, checksum),
        )
        final = self.insert(
            "INSERT INTO artifacts (project_id, production_run_id, kind, media_type, "
            "storage_path, checksum_sha256) VALUES (%s, %s, 'FINAL', 'FINAL_VIDEO', 'video.mp4', %s)",
            (project, run, checksum),
        )
        self.rejected(
            "INSERT INTO approvals (project_id, kind, artifact_id, checksum_sha256) "
            "VALUES (%s, 'VIDEO', %s, %s)", (project, final, checksum),
        )
        self.db.execute("UPDATE production_runs SET state = 'RUNNING' WHERE id = %s", (run,))
        self.db.execute("UPDATE production_runs SET state = 'COMPLETED' WHERE id = %s", (run,))
        self.rejected(
            "INSERT INTO approvals (project_id, kind, artifact_id, checksum_sha256) "
            "VALUES (%s, 'VIDEO', %s, %s)", (project, final, "b" * 64),
        )
        self.rejected(
            "INSERT INTO platform_publications (project_id, artifact_id, video_approval_id, platform) "
            "VALUES (%s, %s, %s, 'YOUTUBE')", (project, final, approval),
        )
        video_approval = self.insert(
            "INSERT INTO approvals (project_id, kind, artifact_id, checksum_sha256) "
            "VALUES (%s, 'VIDEO', %s, %s)", (project, final, checksum),
        )
        self.rejected("UPDATE artifacts SET checksum_sha256 = %s WHERE id = %s", ("b" * 64, final))
        publication = self.insert(
            "INSERT INTO platform_publications (project_id, artifact_id, video_approval_id, platform) "
            "VALUES (%s, %s, %s, 'YOUTUBE')", (project, final, video_approval),
        )
        self.rejected(
            "INSERT INTO platform_publications (project_id, artifact_id, video_approval_id, platform) "
            "VALUES (%s, %s, %s, 'YOUTUBE')", (project, final, video_approval),
        )
        self.db.execute("UPDATE platform_publications SET state = 'UPLOADING' WHERE id = %s", (publication,))
        self.rejected("UPDATE platform_publications SET state = 'QUEUED' WHERE id = %s", (publication,))
        self.db.execute(
            "UPDATE platform_publications SET state = 'PUBLISHED', external_id = 'remote-id' WHERE id = %s",
            (publication,),
        )
        self.rejected("UPDATE platform_publications SET state = 'UPLOADING' WHERE id = %s", (publication,))


if __name__ == "__main__":
    unittest.main()
