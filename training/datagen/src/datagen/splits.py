"""Document-level splits. A document's split depends only on (seed, doc_id), so every chunk of a
document lands in the same split and splits are stable when more documents are generated."""
from __future__ import annotations

import hashlib

SPLITS = (("eval", 0.05), ("corrections", 0.02), ("fresh", 0.10), ("train", 0.83))


def split_for(doc_id: str, seed: int) -> str:
    h = int(hashlib.sha256(f"split:{seed}:{doc_id}".encode()).hexdigest()[:12], 16)
    u = h / float(1 << 48)
    acc = 0.0
    for name, share in SPLITS:
        acc += share
        if u < acc:
            return name
    return "train"
