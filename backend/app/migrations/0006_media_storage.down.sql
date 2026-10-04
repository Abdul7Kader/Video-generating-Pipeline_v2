DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM media_access) OR EXISTS (SELECT 1 FROM storage_changes) THEN
        RAISE EXCEPTION 'Media settings/access exist; a rollback would discard them';
    END IF;
END $$;
DROP TABLE storage_changes;
DROP TABLE media_access;
DELETE FROM schema_migrations WHERE version = 6;
