DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM publication_drafts) OR EXISTS(SELECT 1 FROM publication_releases) THEN
        RAISE EXCEPTION 'Publication drafts/releases must be preserved before rollback';
    END IF;
END $$;
DROP TRIGGER publication_release_guard ON platform_publications;
DROP FUNCTION guard_publication_release();
ALTER TABLE platform_publications DROP COLUMN snapshot;
ALTER TABLE platform_publications DROP COLUMN release_id;
DROP TABLE publication_releases;
DROP TABLE publication_drafts;
DELETE FROM schema_migrations WHERE version=8;
