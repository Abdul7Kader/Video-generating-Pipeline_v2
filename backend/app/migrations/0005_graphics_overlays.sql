ALTER TABLE artifacts DROP CONSTRAINT artifacts_media_type_check;
ALTER TABLE artifacts ADD CONSTRAINT artifacts_media_type_check
    CHECK (media_type IN ('STOCK_VIDEO', 'AI_GENERATED_VIDEO', 'FINAL_VIDEO', 'SPEECH_AUDIO', 'GRAPHICS_OVERLAY'));

CREATE OR REPLACE FUNCTION guard_artifact() RETURNS trigger LANGUAGE plpgsql AS $$
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
       (NEW.kind = 'INTERMEDIATE' AND NEW.media_type NOT IN (expected_type, 'FINAL_VIDEO', 'SPEECH_AUDIO', 'GRAPHICS_OVERLAY')) THEN
        RAISE EXCEPTION 'artifact media type conflicts with project mode or kind';
    END IF;
    RETURN NEW;
END $$;
INSERT INTO schema_migrations (version) VALUES (5);
