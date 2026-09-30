ALTER TABLE production_runs
    ADD COLUMN error_code text,
    ADD COLUMN dispatch_number integer NOT NULL DEFAULT 0 CHECK (dispatch_number >= 0),
    ADD COLUMN available_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN started_at timestamptz,
    ADD COLUMN deadline_at timestamptz,
    ADD COLUMN cancel_requested boolean NOT NULL DEFAULT false;

CREATE TABLE production_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    production_run_id uuid NOT NULL REFERENCES production_runs(id),
    position integer NOT NULL CHECK (position BETWEEN 1 AND 5),
    name text NOT NULL CHECK (name IN ('SCENES', 'SPEECH', 'GRAPHICS', 'ENCODING', 'STORAGE')),
    state text NOT NULL DEFAULT 'PENDING' CHECK (state IN ('PENDING', 'RUNNING', 'FAILED', 'COMPLETED')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= max_attempts),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 3),
    timeout_seconds integer NOT NULL CHECK (timeout_seconds BETWEEN 1 AND 3600),
    error_code text,
    error_message text,
    result jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (production_run_id, position),
    UNIQUE (production_run_id, name),
    UNIQUE (production_run_id, id),
    CHECK ((state = 'COMPLETED') = (result IS NOT NULL)),
    CHECK ((position, name) IN ((1, 'SCENES'), (2, 'SPEECH'), (3, 'GRAPHICS'), (4, 'ENCODING'), (5, 'STORAGE')))
);

CREATE TABLE production_attempts (
    step_id uuid NOT NULL REFERENCES production_steps(id),
    number integer NOT NULL CHECK (number BETWEEN 1 AND 3),
    state text NOT NULL CHECK (state IN ('RUNNING', 'FAILED', 'COMPLETED')),
    error_code text,
    error_message text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    PRIMARY KEY (step_id, number)
);

ALTER TABLE artifacts ADD COLUMN production_step_id uuid, ADD COLUMN artifact_key text;
ALTER TABLE artifacts ADD CONSTRAINT artifact_step_fk
    FOREIGN KEY (production_run_id, production_step_id) REFERENCES production_steps(production_run_id, id);
ALTER TABLE artifacts ADD CONSTRAINT artifact_step_key_pair
    CHECK ((production_step_id IS NULL) = (artifact_key IS NULL));
CREATE UNIQUE INDEX one_artifact_per_step_key ON artifacts(production_step_id, artifact_key);

-- Permit metadata updates without changing the established state transitions.
CREATE OR REPLACE FUNCTION guard_production() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.project_id, NEW.script_version_id, NEW.script_approval_id) IS DISTINCT FROM
           (OLD.project_id, OLD.script_version_id, OLD.script_approval_id) OR
           NOT (NEW.state = OLD.state OR
                (OLD.state = 'QUEUED' AND NEW.state IN ('RUNNING', 'FAILED')) OR
                (OLD.state = 'RUNNING' AND NEW.state IN ('COMPLETED', 'FAILED')) OR
                (OLD.state = 'FAILED' AND NEW.state = 'QUEUED')) THEN
            RAISE EXCEPTION 'invalid production state transition';
        END IF;
    ELSIF NEW.state <> 'QUEUED' THEN
        RAISE EXCEPTION 'production must start queued';
    END IF;
    IF NOT (TG_OP = 'UPDATE' AND (NEW.state = 'FAILED' OR NEW.state = OLD.state)) AND NOT EXISTS (
        SELECT 1 FROM approvals a JOIN script_versions s ON s.id = a.script_version_id
        WHERE a.id = NEW.script_approval_id AND a.kind = 'SCRIPT'
          AND a.project_id = NEW.project_id AND s.id = NEW.script_version_id
          AND s.version = (SELECT max(version) FROM script_versions WHERE project_id = NEW.project_id)
    ) THEN
        RAISE EXCEPTION 'production requires approval of current script version';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END $$;

INSERT INTO schema_migrations(version) VALUES (3);
