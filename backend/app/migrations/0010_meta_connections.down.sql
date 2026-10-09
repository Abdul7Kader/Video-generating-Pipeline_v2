DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM social_connections WHERE provider IN ('facebook','instagram'))
        OR EXISTS (SELECT 1 FROM social_oauth_attempts WHERE provider IN ('facebook','instagram')) THEN
        RAISE EXCEPTION 'Meta connection records must not be discarded by rollback';
    END IF;
END $$;
ALTER TABLE social_connections DROP CONSTRAINT social_connections_provider_check;
ALTER TABLE social_connections ADD CONSTRAINT social_connections_provider_check CHECK (provider IN ('youtube','tiktok'));
ALTER TABLE social_oauth_attempts DROP CONSTRAINT social_oauth_attempts_provider_check;
ALTER TABLE social_oauth_attempts ADD CONSTRAINT social_oauth_attempts_provider_check CHECK (provider IN ('youtube','tiktok'));
DELETE FROM schema_migrations WHERE version=10;
