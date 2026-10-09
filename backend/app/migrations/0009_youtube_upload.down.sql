DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM youtube_uploads) THEN
        RAISE EXCEPTION 'Cannot discard YouTube upload checkpoints; keep migration 9 for reconciliation';
    END IF;
END $$;
CREATE OR REPLACE FUNCTION guard_publication() RETURNS trigger LANGUAGE plpgsql AS $$
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
DROP TABLE youtube_uploads;
DROP FUNCTION guard_youtube_upload();
DELETE FROM schema_migrations WHERE version=9;
