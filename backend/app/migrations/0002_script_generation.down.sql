DROP TABLE script_generation_jobs;
ALTER TABLE scenes DROP COLUMN pexels_queries, DROP COLUMN duration_seconds;
ALTER TABLE script_versions DROP COLUMN target_duration_seconds, DROP COLUMN language;
DELETE FROM schema_migrations WHERE version = 2;
