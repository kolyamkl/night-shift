"""Documents and redaction results to and from the plain dicts that are encrypted at rest."""

import base64
from dataclasses import asdict

from evalkit.redact import Vault
from evalkit.spans import Span

from ..domain.extract import Document, Word
from ..domain.pipeline import Box, ChunkInfo, PipelineResult


def document_to_dict(doc: Document) -> dict:
    data = asdict(doc)
    data["source"] = base64.b64encode(doc.source).decode() if doc.source is not None else None
    return data


def document_from_dict(data: dict) -> Document:
    data = dict(data)
    data["words"] = [Word(**{**w, "bbox": tuple(w["bbox"]), "line": tuple(w["line"])}) for w in data["words"]]
    data["pages"] = [tuple(p) for p in data["pages"]]
    data["source"] = base64.b64decode(data["source"]) if data["source"] is not None else None
    return Document(**data)


def result_to_dict(result: PipelineResult) -> dict:
    data = asdict(result)
    data["unhidden"] = sorted(result.unhidden)
    return data


def result_from_dict(raw: dict) -> PipelineResult:
    return PipelineResult(
        spans=[Span(**s) for s in raw["spans"]], redacted_text=raw["redacted_text"],
        vault=Vault(**raw["vault"]), boxes=[Box(**b) for b in raw["boxes"]],
        chunks=[_chunk(c, i) for i, c in enumerate(raw["chunks"])], stats=raw["stats"],
        model_values=raw["model_values"], hidden=raw["hidden"], unhidden=set(raw["unhidden"]),
        chunk_values=raw.get("chunk_values", []), plan=raw.get("plan", ""),
    )


def _chunk(data: dict, index: int) -> ChunkInfo:
    # Snapshots saved before live scanning lack index/status/latency.
    legacy_status = ("off" if data.get("error") == "model off" else "error" if data.get("error")
                     else "ok" if data.get("mreq_id") or data.get("found") else "empty")
    return ChunkInfo(**{"index": index, "status": legacy_status, **data})
