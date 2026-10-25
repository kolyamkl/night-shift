"""Encryption of stored payloads (Fernet: AES-128-CBC with an HMAC-SHA256 tag).

Every payload is bound to its row and kind, so ciphertext copied into another row or column fails
to open instead of showing the wrong document.
"""

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

KEY_PROBE = b"veil-storage-v1"  # stored encrypted once, so a wrong key is caught at startup


class PayloadCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise RuntimeError("VEIL_STORAGE_KEY must be a Fernet key. See docs/DATABASE.md.") from None

    def seal(self, doc_id: str, kind: str, data: Any) -> bytes:
        return self._fernet.encrypt(
            json.dumps({"version": 1, "doc_id": doc_id, "kind": kind, "data": data}, ensure_ascii=False).encode()
        )

    def open(self, doc_id: str, kind: str, payload: bytes | memoryview) -> Any:
        data = json.loads(self._fernet.decrypt(bytes(payload)))
        if (data["version"], data["doc_id"], data["kind"]) != (1, doc_id, kind):
            raise ValueError("Stored payload identity/version mismatch")
        return data["data"]

    def probe(self) -> bytes:
        return self._fernet.encrypt(KEY_PROBE)

    def matches(self, probe: bytes | memoryview) -> bool:
        """Whether a stored probe was written with this key."""
        try:
            return self._fernet.decrypt(bytes(probe)) == KEY_PROBE
        except InvalidToken:
            return False
