ALTER TABLE script_versions
    ADD COLUMN language text NOT NULL DEFAULT 'de-DE',
    ADD COLUMN target_duration_seconds integer CHECK (target_duration_seconds BETWEEN 30 AND 60);

ALTER TABLE scenes
    ADD COLUMN duration_seconds integer CHECK (duration_seconds BETWEEN 3 AND 12),
    ADD COLUMN pexels_queries jsonb;

CREATE TABLE script_generation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    state text NOT NULL DEFAULT 'QUEUED'
        CHECK (state IN ('QUEUED', 'RUNNING', 'FAILED', 'COMPLETED')),
    error_code text,
    error_message text,
    script_version integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((state = 'COMPLETED') = (script_version IS NOT NULL))
);
CREATE UNIQUE INDEX one_active_script_generation_per_project
    ON script_generation_jobs(project_id) WHERE state IN ('QUEUED', 'RUNNING');
CREATE INDEX script_generation_jobs_project_created
    ON script_generation_jobs(project_id, created_at DESC);

INSERT INTO schema_migrations(version) VALUES (2);
