CREATE TABLE script_generation_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    state text NOT NULL DEFAULT 'QUEUED'
        CHECK (state IN ('QUEUED', 'RUNNING', 'FAILED', 'COMPLETED')),
    rq_job_id text UNIQUE,
    error_code text,
    error_message text,
    script_version_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, script_version_id)
        REFERENCES script_versions(project_id, id),
    CHECK ((state = 'FAILED') = (error_code IS NOT NULL AND error_message IS NOT NULL)),
    CHECK ((state = 'COMPLETED') = (script_version_id IS NOT NULL))
);

CREATE UNIQUE INDEX one_active_script_generation_per_project
    ON script_generation_jobs(project_id) WHERE state IN ('QUEUED', 'RUNNING');

INSERT INTO schema_migrations (version) VALUES (2);
