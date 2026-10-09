CREATE TABLE social_connections (
    provider text PRIMARY KEY CHECK (provider IN ('youtube','tiktok')),
    id uuid NOT NULL UNIQUE,
    config_fingerprint text NOT NULL,
    account_id text CHECK (length(account_id) BETWEEN 1 AND 300),
    account_title text CHECK (length(account_title) BETWEEN 1 AND 300),
    scopes jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(scopes)='array'),
    tokens_encrypted bytea,
    expires_at timestamptz,
    refresh_expires_at timestamptz,
    state text NOT NULL CHECK (state IN ('CONNECTED','LIMITED','REAUTH_REQUIRED','REVOKE_FAILED','DISCONNECTED')),
    error_code text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((state='DISCONNECTED' AND tokens_encrypted IS NULL) OR (state!='DISCONNECTED' AND tokens_encrypted IS NOT NULL)),
    CHECK (state NOT IN ('CONNECTED','LIMITED') OR (account_id IS NOT NULL AND account_title IS NOT NULL))
);
CREATE TABLE social_oauth_attempts (
    provider text PRIMARY KEY CHECK (provider IN ('youtube','tiktok')),
    state_hash text NOT NULL UNIQUE,
    binding_hash text NOT NULL,
    session_hash text NOT NULL,
    config_fingerprint text NOT NULL,
    connection_id uuid NOT NULL,
    verifier_encrypted bytea NOT NULL,
    consumed boolean NOT NULL DEFAULT false,
    expires_at timestamptz NOT NULL
);
INSERT INTO schema_migrations (version) VALUES (7);
