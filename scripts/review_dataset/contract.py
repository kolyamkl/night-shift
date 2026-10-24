"""Offline reference contract. No network, UI, authentication or persistent vault.

Only a trusted backend UI handler may invoke approve(). Model responses cannot
authorize sending. Integration must enforce redactor routing BEFORE raw input is sent.
Offsets are Python Unicode code points, not UTF-8 bytes or JavaScript UTF-16 units.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import re
import secrets

SOURCES = ("document", "question")
ENTITY_TYPES = (
    "PERSON", "ADDRESS", "POSTCODE", "EMAIL", "PHONE", "BANK_ACCOUNT",
    "SORT_CODE", "IBAN", "CARD", "NI_NUMBER", "DOB", "ID_DOC", "CUSTOM",
    "SECRET", "HEALTH",
)
DESTINATIONS = ("openai", "anthropic")
RESERVED = re.compile(r"\[VEIL_[A-Z_]+_\d+\]")


def check_input(bundle: dict) -> None:
    if not isinstance(bundle, dict) or set(bundle) != set(SOURCES):
        raise ValueError("Input must contain exactly document and question")
    if any(not isinstance(bundle[s], str) for s in SOURCES):
        raise ValueError("Input fields must be strings")
    if any(RESERVED.search(bundle[s]) for s in SOURCES):
        raise ValueError("Input contains a reserved placeholder; manual resolution required")


def detector_payload(bundle: dict, *, synthetic: bool = False,
                     trusted_redactor: bool = False, provider_fallback: bool = True) -> dict:
    """A routing precondition, not discovery or enforcement of any remote route.

The trusted backend supplies these facts from verified route configuration, never
from user input or model output. All generated examples are synthetic.
"""
    check_input(bundle)
    if synthetic is not True and not (trusted_redactor is True and provider_fallback is False):
        raise PermissionError("Raw real data requires trusted redaction without provider fallback")
    return deepcopy(bundle)


def redact(bundle: dict, detection: dict) -> tuple[dict, dict]:
    """Ground every span, then replace locally. Missing spans still require review."""
    check_input(bundle)
    if not isinstance(detection, dict) or set(detection) != {"entities"}:
        raise ValueError("Detection must contain only entities, never approval instructions")
    if not isinstance(detection["entities"], list):
        raise ValueError("entities must be a list")
    spans = deepcopy(detection["entities"])
    by_source = {source: [] for source in SOURCES}
    id_types = {}
    fields = {"source", "start", "end", "text", "type", "entity_id"}
    for ent in spans:
        if not isinstance(ent, dict) or set(ent) != fields:
            raise ValueError("Unexpected entity fields")
        source, kind, eid = ent["source"], ent["type"], ent["entity_id"]
        if not isinstance(source, str) or source not in SOURCES:
            raise ValueError("Unknown source")
        if not isinstance(kind, str) or kind not in ENTITY_TYPES:
            raise ValueError("Unknown entity type")
        if not isinstance(eid, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", eid):
            raise ValueError("Invalid entity identity")
        start, end = ent["start"], ent["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(bundle[source]):
            raise ValueError("Invalid offsets")
        if not isinstance(ent["text"], str) or bundle[source][start:end] != ent["text"]:
            raise ValueError("Span text does not match input")
        if not ent["text"].strip():
            raise ValueError("Whitespace is not an entity")
        if eid in id_types and id_types[eid] != kind:
            raise ValueError("One identity cannot have different types")
        id_types[eid] = kind
        by_source[source].append(ent)

    counters = defaultdict(int)
    placeholders, vault, output = {}, {}, {}
    for source in SOURCES:
        ordered = sorted(by_source[source], key=lambda e: (e["start"], e["end"]))
        cursor, parts = 0, []
        for ent in ordered:
            if ent["start"] < cursor:
                raise ValueError("Duplicate or overlapping spans")
            eid = ent["entity_id"]
            if eid not in placeholders:
                counters[ent["type"]] += 1
                token = f"[VEIL_{ent['type']}_{counters[ent['type']]}]"
                placeholders[eid] = token
                vault[token] = []
            token = placeholders[eid]
            if ent["text"] not in vault[token]:
                vault[token].append(ent["text"])
            parts.append(bundle[source][cursor:ent["start"]])
            # Preserve every original line separator, including CRLF.
            parts.append(re.sub(r"[^\r\n]+", lambda _: token, ent["text"]))
            cursor = ent["end"]
        parts.append(bundle[source][cursor:])
        output[source] = "".join(parts)
    return output, vault


class ReviewSession:
    """Reference state machine; approve() is a trusted human-UI action only.

    An application must bind the instance to an authenticated user/conversation,
    enforce route guarantees and forward exactly outbound(), with no extra history,
    attachments or raw metadata. This class has no transport and is not a deployed
    privacy boundary.
    """

    def __init__(self, bundle: dict, detection: dict, destination: str):
        self._nonce = secrets.token_hex(16)
        self._revision = 0
        self._approved = None
        self._payload = None
        self._vault = {}
        self.update(bundle, detection, destination)

    def update(self, bundle: dict, detection: dict, destination: str) -> None:
        # A failed edit must not leave the old approval usable.
        self._approved = None
        self._payload = None
        self._vault = {}
        self._revision += 1
        if destination not in DESTINATIONS:
            raise ValueError("Unsupported destination")
        output, vault = redact(bundle, detection)
        self._payload = {"destination": destination, **output}
        self._vault = vault

    def _review_id(self) -> str:
        if self._payload is None:
            raise PermissionError("A valid review is required")
        encoded = json.dumps([self._nonce, self._revision, self._payload], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def preview(self) -> dict:
        return {"review_id": self._review_id(), "payload": deepcopy(self._payload)}

    def approve(self, review_id: str, *, confirmed: bool) -> None:
        self._approved = None
        if confirmed is not True or review_id != self._review_id():
            raise PermissionError("Explicit confirmation of the current preview is required")
        self._approved = review_id

    def reject(self) -> None:
        self._approved = None

    def outbound(self) -> dict:
        if self._approved is None or self._approved != self._review_id():
            raise PermissionError("Sending is blocked until the current preview is approved")
        return deepcopy(self._payload)
