CREATE TABLE veil_documents (
    doc_id text PRIMARY KEY,
    payload bytea NOT NULL,
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE veil_redactions (
    doc_id text PRIMARY KEY REFERENCES veil_documents(doc_id) ON DELETE CASCADE,
    payload bytea NOT NULL
);

-- An encrypted probe detects a missing/wrong key before accepting uploads.
CREATE TABLE veil_storage_settings (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    key_probe bytea NOT NULL
);
