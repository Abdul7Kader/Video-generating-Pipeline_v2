CREATE TABLE media_access (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    password_salt text NOT NULL,
    password_hash text NOT NULL,
    session_secret text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE storage_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    old_path text NOT NULL,
    new_path text NOT NULL,
    state text NOT NULL DEFAULT 'QUEUED' CHECK (state IN ('QUEUED','RUNNING','COMPLETED','FAILED')),
    total_bytes bigint NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
    verified_bytes bigint NOT NULL DEFAULT 0 CHECK (verified_bytes >= 0 AND verified_bytes <= total_bytes),
    attempts int NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    dispatch_number int NOT NULL DEFAULT 0,
    error_code text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_storage_change ON storage_changes ((true)) WHERE state IN ('QUEUED','RUNNING');
INSERT INTO schema_migrations (version) VALUES (6);
