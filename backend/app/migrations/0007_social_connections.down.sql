DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM social_connections WHERE tokens_encrypted IS NOT NULL)
       OR EXISTS (SELECT 1 FROM social_oauth_attempts) THEN
        RAISE EXCEPTION 'Disconnect accounts and finish OAuth attempts before rollback';
    END IF;
END $$;
DROP TABLE social_oauth_attempts;
DROP TABLE social_connections;
DELETE FROM schema_migrations WHERE version=7;
