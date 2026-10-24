# What Veil saves in PostgreSQL

This describes Veil's PostgreSQL storage and email/password authentication as
implemented on 24 October 2026. See [DATABASE.md](DATABASE.md) for local setup,
configuration, and verification commands.

## Saved data

| Data | What is saved | Protection |
| --- | --- | --- |
| Accounts | User ID, normalized email, password hash, creation date | Passwords use Argon2id hashes; emails are not encrypted |
| Login sessions | Session-token hash, user ID, creation date, expiry | Only a SHA-256 hash of the random token is stored |
| Documents | Filename, original text, PDF bytes when available, extracted words and page layout | Encrypted before database storage |
| Document metadata | Document ID, owner ID, revision, creation and update dates | Stored as ordinary database fields; access is restricted to the owner |
| Redaction results | Detected entities and spans, redacted text, PDF boxes, statistics, chunk results and model request IDs | Encrypted |
| Placeholder vault | Mappings between placeholders and original sensitive values | Encrypted |
| Review corrections | Current hide/unhide choices and model-detected values used to rebuild redactions | Encrypted with the latest result; no separate edit history |
| Login rate limits | Hashed client-address bucket, attempt count, reset time | Short-lived counters |
| Database maintenance | Migration filenames, checksums, application dates, encrypted key-verification probe | The encryption key itself is not stored in PostgreSQL |

The tables are `veil_users`, `veil_sessions`, `veil_documents`,
`veil_redactions`, `veil_auth_limits`, `veil_schema_migrations`, and
`veil_storage_settings`.

PDFs with a text layer retain their original PDF bytes. Scans and photos currently
become extracted text; their original image/scanned-PDF bytes are not retained by
that ingestion path.

## Not saved in this database

- Plaintext passwords or raw login-session tokens.
- Chat questions, answers, or conversation history.
- Approval/decline decisions or a consent audit trail.
- Mubit API keys or the document encryption key.
- Model weights or training-job history.

Registration does not send a verification email or check ownership of the email
address. It creates the account and signs the user in immediately.

## Access and retention

Every saved document belongs to an account. Reading, scanning, correcting,
downloading, deleting, or asking about it requires that owner's login session.
Older documents without an owner remain inaccessible until an administrator
explicitly assigns them.

Documents and their latest redaction results survive backend restarts. They stay
until explicitly deleted; there is no automatic document expiry. Deleting a
document also deletes its stored redaction result. Database backups and write-ahead
logs may retain encrypted historical records until their own retention ends.

Login sessions expire after seven days. Logout immediately revokes the current
session. Expired session rows are cleaned up when a new session is created.
Rate-limit counters reset after one minute; counters more than a day past their
reset time are cleaned up on subsequent login or registration attempts.

Encryption protects stored document contents. The backend can decrypt them, and
this storage design does not itself guarantee that outbound model requests are
redacted or approved. Backend approval enforcement and question redaction remain
separate work.
