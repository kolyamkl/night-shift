-- Review status, an encrypted list summary, and chat turns. Additive only: existing rows keep working.
ALTER TABLE veil_documents ADD COLUMN status text NOT NULL DEFAULT 'new'
    CHECK (status IN ('new', 'review', 'approved', 'declined'));
-- Encrypted {filename, kind, pages, changes} for the document list, so listing does not decrypt
-- whole documents with their PDF bytes. NULL on rows saved before this migration until first listed.
ALTER TABLE veil_documents ADD COLUMN meta bytea;
-- Documents scanned before review status existed open for review again, as they did before.
UPDATE veil_documents SET status = 'review' WHERE doc_id IN (SELECT doc_id FROM veil_redactions);
CREATE INDEX veil_documents_owner_updated_idx ON veil_documents (owner_id, updated_at DESC);

CREATE TABLE veil_chat_turns (
    turn_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id text NOT NULL REFERENCES veil_documents(doc_id) ON DELETE CASCADE,
    owner_id text NOT NULL REFERENCES veil_users(user_id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    payload bytea NOT NULL
);
CREATE INDEX veil_chat_turns_doc_idx ON veil_chat_turns (doc_id, turn_id);
