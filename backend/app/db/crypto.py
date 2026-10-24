"""Fernet envelopes for everything stored about a document. No pickle and no plaintext at rest."""

import json

from cryptography.fernet import Fernet

VERSION = 1


class Envelope:
    def __init__(self, key: str):
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise RuntimeError("VEIL_STORAGE_KEY must be a Fernet key. See docs/DATABASE.md.") from None

    def seal(self, doc_id: str, kind: str, data: dict) -> bytes:
        # Bound to its row and kind, so ciphertext swapped between rows or columns is detected.
        return self._fernet.encrypt(json.dumps({"version": VERSION, "doc_id": doc_id, "kind": kind, "data": data},
                                               ensure_ascii=False).encode())

    def open(self, doc_id: str, kind: str, payload: bytes) -> dict:
        data = json.loads(self._fernet.decrypt(bytes(payload)))
        if (data["version"], data["doc_id"], data["kind"]) != (VERSION, doc_id, kind):
            raise ValueError("Stored payload identity/version mismatch")
        return data["data"]

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._fernet.decrypt(bytes(data))
