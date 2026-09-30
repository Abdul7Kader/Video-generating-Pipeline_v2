DROP INDEX one_artifact_per_step_key;
ALTER TABLE artifacts DROP CONSTRAINT artifact_step_fk, DROP CONSTRAINT artifact_step_key_pair,
    DROP COLUMN production_step_id, DROP COLUMN artifact_key;
DROP TABLE production_attempts;
DROP TABLE production_steps;
ALTER TABLE production_runs DROP COLUMN error_code, DROP COLUMN dispatch_number,
    DROP COLUMN available_at, DROP COLUMN started_at, DROP COLUMN deadline_at, DROP COLUMN cancel_requested;
-- migrate down removes all versions, including the original guard function.
DELETE FROM schema_migrations WHERE version = 3;
