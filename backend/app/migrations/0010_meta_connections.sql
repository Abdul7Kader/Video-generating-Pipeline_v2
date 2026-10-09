ALTER TABLE social_connections DROP CONSTRAINT social_connections_provider_check;
ALTER TABLE social_connections ADD CONSTRAINT social_connections_provider_check CHECK (provider IN ('youtube','tiktok','instagram','facebook'));
ALTER TABLE social_oauth_attempts DROP CONSTRAINT social_oauth_attempts_provider_check;
ALTER TABLE social_oauth_attempts ADD CONSTRAINT social_oauth_attempts_provider_check CHECK (provider IN ('youtube','tiktok','instagram','facebook'));
INSERT INTO schema_migrations(version) VALUES(10);
