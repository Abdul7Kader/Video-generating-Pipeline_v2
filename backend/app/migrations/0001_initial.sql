CREATE TABLE schema_migrations (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    idea text NOT NULL CHECK (length(btrim(idea)) > 0),
    mode text NOT NULL CHECK (mode IN ('LOKAL', 'CLOUD')),
    media_type text NOT NULL CHECK (
        (mode = 'LOKAL' AND media_type = 'STOCK_VIDEO') OR
        (mode = 'CLOUD' AND media_type = 'AI_GENERATED_VIDEO')
    ),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION protect_project_mode() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.mode <> OLD.mode OR NEW.media_type <> OLD.media_type THEN
        RAISE EXCEPTION 'project mode and media type are immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER project_mode_immutable BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION protect_project_mode();

CREATE TABLE script_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    version integer NOT NULL CHECK (version > 0),
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    narration text NOT NULL CHECK (length(btrim(narration)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, version),
    UNIQUE (project_id, id)
);

CREATE FUNCTION protect_script_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'script versions are immutable; create a new version';
END $$;
CREATE TRIGGER script_version_immutable BEFORE UPDATE OR DELETE ON script_versions
    FOR EACH ROW EXECUTE FUNCTION protect_script_version();

CREATE TABLE scenes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    script_version_id uuid NOT NULL,
    position integer NOT NULL CHECK (position > 0),
    narration text NOT NULL CHECK (length(btrim(narration)) > 0),
    visual_description text NOT NULL CHECK (length(btrim(visual_description)) > 0),
    media_type text NOT NULL CHECK (media_type IN ('STOCK_VIDEO', 'AI_GENERATED_VIDEO')),
    pexels_query text,
    wan_prompt text,
    UNIQUE (script_version_id, position),
    FOREIGN KEY (project_id, script_version_id)
        REFERENCES script_versions(project_id, id)
);

CREATE TABLE production_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    script_version_id uuid NOT NULL,
    script_approval_id uuid NOT NULL,
    state text NOT NULL DEFAULT 'QUEUED'
        CHECK (state IN ('QUEUED', 'RUNNING', 'FAILED', 'COMPLETED')),
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, script_version_id),
    UNIQUE (project_id, id),
    FOREIGN KEY (project_id, script_version_id)
        REFERENCES script_versions(project_id, id)
);

CREATE TABLE artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    production_run_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('SOURCE', 'INTERMEDIATE', 'FINAL')),
    media_type text NOT NULL CHECK (media_type IN ('STOCK_VIDEO', 'AI_GENERATED_VIDEO', 'FINAL_VIDEO')),
    storage_path text NOT NULL CHECK (length(btrim(storage_path)) > 0),
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, id),
    FOREIGN KEY (project_id, production_run_id)
        REFERENCES production_runs(project_id, id)
);
CREATE UNIQUE INDEX one_final_artifact_per_run ON artifacts(production_run_id)
    WHERE kind = 'FINAL';

CREATE TABLE approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    kind text NOT NULL CHECK (kind IN ('SCRIPT', 'VIDEO')),
    script_version_id uuid,
    artifact_id uuid,
    checksum_sha256 text,
    approved_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (kind = 'SCRIPT' AND script_version_id IS NOT NULL AND artifact_id IS NULL AND checksum_sha256 IS NULL) OR
        (kind = 'VIDEO' AND script_version_id IS NULL AND artifact_id IS NOT NULL AND checksum_sha256 IS NOT NULL)
    ),
    UNIQUE (project_id, id),
    FOREIGN KEY (project_id, script_version_id)
        REFERENCES script_versions(project_id, id),
    FOREIGN KEY (project_id, artifact_id)
        REFERENCES artifacts(project_id, id)
);
CREATE UNIQUE INDEX one_script_approval_per_version ON approvals(script_version_id)
    WHERE kind = 'SCRIPT';
CREATE UNIQUE INDEX one_video_approval_per_artifact ON approvals(artifact_id)
    WHERE kind = 'VIDEO';
ALTER TABLE production_runs ADD CONSTRAINT production_script_approval_fk
    FOREIGN KEY (project_id, script_approval_id) REFERENCES approvals(project_id, id);

CREATE TABLE platform_publications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    video_approval_id uuid NOT NULL,
    platform text NOT NULL CHECK (platform IN ('YOUTUBE', 'TIKTOK', 'INSTAGRAM', 'FACEBOOK', 'X')),
    state text NOT NULL DEFAULT 'QUEUED'
        CHECK (state IN ('QUEUED', 'UPLOADING', 'FAILED', 'PUBLISHED')),
    external_id text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (artifact_id, platform),
    FOREIGN KEY (project_id, artifact_id) REFERENCES artifacts(project_id, id),
    FOREIGN KEY (project_id, video_approval_id) REFERENCES approvals(project_id, id),
    CHECK ((state = 'PUBLISHED' AND external_id IS NOT NULL) OR state <> 'PUBLISHED')
);

CREATE FUNCTION guard_scene() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_type text;
BEGIN
    SELECT media_type INTO expected_type FROM projects WHERE id = NEW.project_id;
    IF NEW.media_type <> expected_type OR
       (expected_type = 'STOCK_VIDEO' AND (nullif(btrim(NEW.pexels_query), '') IS NULL OR NEW.wan_prompt IS NOT NULL)) OR
       (expected_type = 'AI_GENERATED_VIDEO' AND (nullif(btrim(NEW.wan_prompt), '') IS NULL OR NEW.pexels_query IS NOT NULL)) THEN
        RAISE EXCEPTION 'scene media and prompt must match project mode';
    END IF;
    IF EXISTS (SELECT 1 FROM approvals WHERE script_version_id = NEW.script_version_id AND kind = 'SCRIPT') THEN
        RAISE EXCEPTION 'approved script cannot gain scenes';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER scene_insert_guard BEFORE INSERT ON scenes
    FOR EACH ROW EXECUTE FUNCTION guard_scene();
CREATE TRIGGER scene_immutable BEFORE UPDATE OR DELETE ON scenes
    FOR EACH ROW EXECUTE FUNCTION protect_script_version();

CREATE FUNCTION guard_artifact() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected_type text;
BEGIN
    IF TG_OP = 'UPDATE' AND EXISTS (
        SELECT 1 FROM approvals WHERE artifact_id = OLD.id AND kind = 'VIDEO'
    ) THEN
        RAISE EXCEPTION 'approved artifact is immutable';
    END IF;
    SELECT media_type INTO expected_type FROM projects WHERE id = NEW.project_id;
    IF (NEW.kind = 'FINAL' AND NEW.media_type <> 'FINAL_VIDEO') OR
       (NEW.kind = 'SOURCE' AND NEW.media_type <> expected_type) OR
       (NEW.kind = 'INTERMEDIATE' AND NEW.media_type NOT IN (expected_type, 'FINAL_VIDEO')) THEN
        RAISE EXCEPTION 'artifact media type conflicts with project mode or kind';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER artifact_guard BEFORE INSERT OR UPDATE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION guard_artifact();

CREATE FUNCTION guard_approval() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target artifacts%ROWTYPE;
BEGIN
    IF NEW.kind = 'SCRIPT' THEN
        IF NEW.script_version_id <> (
            SELECT id FROM script_versions WHERE project_id = NEW.project_id ORDER BY version DESC LIMIT 1
        ) OR NOT EXISTS (
            SELECT 1 FROM scenes WHERE script_version_id = NEW.script_version_id
            GROUP BY script_version_id
            HAVING count(*) BETWEEN 6 AND 10 AND min(position) = 1 AND max(position) = count(*)
        ) THEN
            RAISE EXCEPTION 'only a complete current script version can be approved';
        END IF;
    ELSE
        SELECT * INTO target FROM artifacts WHERE id = NEW.artifact_id;
        IF target.kind <> 'FINAL' OR target.checksum_sha256 <> NEW.checksum_sha256 OR
           NOT EXISTS (SELECT 1 FROM production_runs WHERE id = target.production_run_id AND state = 'COMPLETED') THEN
            RAISE EXCEPTION 'video approval requires completed final artifact and matching checksum';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER approval_insert_guard BEFORE INSERT ON approvals
    FOR EACH ROW EXECUTE FUNCTION guard_approval();
CREATE FUNCTION protect_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'approvals are immutable';
END $$;
CREATE TRIGGER approval_immutable BEFORE UPDATE OR DELETE ON approvals
    FOR EACH ROW EXECUTE FUNCTION protect_approval();

CREATE FUNCTION guard_production() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.project_id, NEW.script_version_id, NEW.script_approval_id) IS DISTINCT FROM
           (OLD.project_id, OLD.script_version_id, OLD.script_approval_id) OR
           NOT ((OLD.state = 'QUEUED' AND NEW.state IN ('RUNNING', 'FAILED')) OR
                (OLD.state = 'RUNNING' AND NEW.state IN ('COMPLETED', 'FAILED')) OR
                (OLD.state = 'FAILED' AND NEW.state = 'QUEUED')) THEN
            RAISE EXCEPTION 'invalid production state transition';
        END IF;
    ELSIF NEW.state <> 'QUEUED' THEN
        RAISE EXCEPTION 'production must start queued';
    END IF;
    IF NOT (TG_OP = 'UPDATE' AND NEW.state = 'FAILED') AND NOT EXISTS (
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
CREATE TRIGGER production_guard BEFORE INSERT OR UPDATE ON production_runs
    FOR EACH ROW EXECUTE FUNCTION guard_production();

CREATE FUNCTION guard_publication() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target artifacts%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.project_id, NEW.artifact_id, NEW.video_approval_id, NEW.platform) IS DISTINCT FROM
           (OLD.project_id, OLD.artifact_id, OLD.video_approval_id, OLD.platform) OR
           NOT ((OLD.state = 'QUEUED' AND NEW.state IN ('UPLOADING', 'FAILED')) OR
                (OLD.state = 'UPLOADING' AND NEW.state IN ('PUBLISHED', 'FAILED')) OR
                (OLD.state = 'FAILED' AND NEW.state = 'QUEUED')) THEN
            RAISE EXCEPTION 'invalid publication state transition';
        END IF;
    ELSIF NEW.state <> 'QUEUED' THEN
        RAISE EXCEPTION 'publication must start queued';
    END IF;
    SELECT * INTO target FROM artifacts WHERE id = NEW.artifact_id;
    IF target.kind <> 'FINAL' OR NOT EXISTS (
        SELECT 1 FROM approvals WHERE id = NEW.video_approval_id AND kind = 'VIDEO'
          AND project_id = NEW.project_id AND artifact_id = NEW.artifact_id
          AND checksum_sha256 = target.checksum_sha256
    ) THEN
        RAISE EXCEPTION 'publication requires approval of this final artifact';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END $$;
CREATE TRIGGER publication_guard BEFORE INSERT OR UPDATE ON platform_publications
    FOR EACH ROW EXECUTE FUNCTION guard_publication();

INSERT INTO schema_migrations(version) VALUES (1);
