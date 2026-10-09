CREATE TABLE publication_drafts (
    artifact_id uuid PRIMARY KEY REFERENCES artifacts(id),
    revision integer NOT NULL CHECK (revision>0),
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[a-f0-9]{64}$'),
    provenance_hash text NOT NULL,
    metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata)='object'),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE publication_releases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id uuid NOT NULL REFERENCES publication_drafts(artifact_id),
    revision integer NOT NULL,
    checksum_sha256 text NOT NULL,
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
    invalidated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (artifact_id,revision)
);
ALTER TABLE platform_publications ADD COLUMN release_id uuid REFERENCES publication_releases(id);
ALTER TABLE platform_publications ADD COLUMN snapshot jsonb;
CREATE FUNCTION guard_publication_release() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE release publication_releases%ROWTYPE;
BEGIN
    IF TG_OP='UPDATE' AND (NEW.release_id,NEW.snapshot) IS DISTINCT FROM (OLD.release_id,OLD.snapshot) THEN
        RAISE EXCEPTION 'publication snapshot is immutable';
    END IF;
    -- Existing historical records lack release metadata. Future adapters must
    -- reject these records; migration does not invent retrospective consent.
    IF NEW.release_id IS NULL THEN RETURN NEW; END IF;
    SELECT * INTO release FROM publication_releases WHERE id=NEW.release_id;
    IF release.artifact_id<>NEW.artifact_id OR NEW.snapshot IS DISTINCT FROM release.snapshot->'targets'->lower(NEW.platform) THEN
        RAISE EXCEPTION 'publication does not match release';
    END IF;
    IF NEW.state IN ('QUEUED','UPLOADING') AND (
        release.invalidated_at IS NOT NULL OR NOT EXISTS (
            SELECT 1 FROM social_connections c WHERE c.provider=lower(NEW.platform)
              AND c.state='CONNECTED' AND c.expires_at>now()
              AND c.id::text=NEW.snapshot->>'connection_id'
              AND c.account_id=NEW.snapshot->>'account_id'
              AND c.config_fingerprint=NEW.snapshot->>'config_fingerprint'
        ) OR NOT EXISTS (
            SELECT 1 FROM publication_drafts d JOIN artifacts a ON a.id=d.artifact_id
            JOIN production_runs r ON r.id=a.production_run_id
            JOIN script_versions s ON s.id=r.script_version_id
            WHERE d.artifact_id=NEW.artifact_id AND d.revision=release.revision
              AND d.checksum_sha256=release.checksum_sha256 AND a.checksum_sha256=release.checksum_sha256
              AND s.version=(SELECT max(version) FROM script_versions WHERE project_id=NEW.project_id)
        )) THEN RAISE EXCEPTION 'publication release is outdated';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER publication_release_guard BEFORE INSERT OR UPDATE ON platform_publications
    FOR EACH ROW EXECUTE FUNCTION guard_publication_release();
INSERT INTO schema_migrations(version) VALUES (8);
