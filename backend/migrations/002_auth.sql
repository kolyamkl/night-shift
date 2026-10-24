CREATE TABLE veil_users (
    user_id text PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE veil_sessions (
    token_hash text PRIMARY KEY,
    user_id text NOT NULL REFERENCES veil_users(user_id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX veil_sessions_expiry_idx ON veil_sessions (expires_at);

CREATE TABLE veil_auth_limits (
    bucket text PRIMARY KEY,
    attempts integer NOT NULL,
    reset_at timestamptz NOT NULL
);

-- Preserve legacy documents without exposing them to any newly created account.
ALTER TABLE veil_documents ADD COLUMN owner_id text REFERENCES veil_users(user_id) ON DELETE CASCADE;
CREATE INDEX veil_documents_owner_idx ON veil_documents (owner_id);
