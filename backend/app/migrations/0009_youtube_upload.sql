CREATE TABLE youtube_uploads (
    publication_id uuid PRIMARY KEY REFERENCES platform_publications(id) ON DELETE RESTRICT,
    phase text NOT NULL DEFAULT 'READY' CHECK (phase IN ('READY','INITIATING','ACTIVE','PROCESSING','COMPLETE','UNKNOWN')),
    session_encrypted bytea,
    size_bytes bigint NOT NULL CHECK (size_bytes>0 AND size_bytes<=274877906944),
    confirmed_bytes bigint NOT NULL DEFAULT 0 CHECK (confirmed_bytes>=0 AND confirmed_bytes<=size_bytes),
    actual_visibility text CHECK (actual_visibility IN ('private','unlisted','public')),
    error_code text,
    retries integer NOT NULL DEFAULT 0 CHECK (retries>=0 AND retries<=5),
    poll_count integer NOT NULL DEFAULT 0 CHECK (poll_count>=0 AND poll_count<=120),
    dispatch_number integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (phase<>'ACTIVE' OR session_encrypted IS NOT NULL)
);
CREATE FUNCTION guard_youtube_upload() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM platform_publications WHERE id=NEW.publication_id AND platform='YOUTUBE' AND release_id IS NOT NULL) THEN
        RAISE EXCEPTION 'YouTube upload needs immutable publication consent';
    END IF;
    IF TG_OP='UPDATE' AND (NEW.publication_id,NEW.size_bytes,NEW.started_at) IS DISTINCT FROM (OLD.publication_id,OLD.size_bytes,OLD.started_at) THEN
        RAISE EXCEPTION 'YouTube upload binding is immutable';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER youtube_upload_guard BEFORE INSERT OR UPDATE ON youtube_uploads FOR EACH ROW EXECUTE FUNCTION guard_youtube_upload();
CREATE OR REPLACE FUNCTION guard_publication() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target artifacts%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.project_id, NEW.artifact_id, NEW.video_approval_id, NEW.platform) IS DISTINCT FROM
           (OLD.project_id, OLD.artifact_id, OLD.video_approval_id, OLD.platform) OR
           (OLD.external_id IS NOT NULL AND NEW.external_id IS DISTINCT FROM OLD.external_id) OR
           NOT ((OLD.state = 'QUEUED' AND NEW.state IN ('UPLOADING', 'FAILED')) OR
                (OLD.state = 'UPLOADING' AND NEW.state IN ('PUBLISHED', 'FAILED')) OR
                (OLD.state = 'FAILED' AND NEW.state = 'QUEUED') OR
                (OLD.platform='YOUTUBE' AND EXISTS (SELECT 1 FROM youtube_uploads WHERE publication_id=OLD.id) AND
                  ((OLD.state=NEW.state AND OLD.state IN ('UPLOADING','FAILED')) OR
                   (OLD.state='FAILED' AND NEW.state='UPLOADING' AND EXISTS (
                     SELECT 1 FROM youtube_uploads WHERE publication_id=OLD.id AND phase IN ('READY','ACTIVE','PROCESSING')))))) THEN
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
INSERT INTO schema_migrations(version) VALUES (9);
