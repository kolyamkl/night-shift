"""Fuzzy near-duplicate detection with MinHash over word 3-shingles of the *skeleton*
(entities replaced by their type, digits zeroed, case and whitespace folded).

* 64 hash functions, LSH with 16 bands x 4 rows.
* Two texts are near-duplicates when their estimated Jaccard similarity is >= 0.8
  (roughly: they differ in at most one or two words apart from personal values and numbers).
"""
from __future__ import annotations

import zlib

import numpy as np

from .build import skeleton

N_PERM = 64
BANDS = 16
ROWS = N_PERM // BANDS
_PRIME = np.uint64(4294967311)  # > 2^32
_rs = np.random.RandomState(1234567)
_A = _rs.randint(1, 2**32 - 1, size=N_PERM, dtype=np.uint64)
_B = _rs.randint(0, 2**32 - 1, size=N_PERM, dtype=np.uint64)


def shingles(skel: str, k: int = 3) -> list[str]:
    toks = skel.split()
    if len(toks) <= k:
        return [" ".join(toks)] if toks else [""]
    return [" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)]


def signature_of_skeleton(skel: str) -> bytes:
    h = np.fromiter((zlib.crc32(s.encode()) for s in set(shingles(skel))), dtype=np.uint64)
    sig = ((_A[:, None] * h[None, :] + _B[:, None]) % _PRIME).min(axis=1).astype(np.uint32)
    return sig.tobytes()


def signature(text: str, entities: list[dict]) -> bytes:
    return signature_of_skeleton(skeleton(text, entities))


def band_keys(sig: bytes) -> list[int]:
    step = ROWS * 4
    return [(b << 128) | int.from_bytes(sig[b * step:(b + 1) * step], "little") for b in range(BANDS)]


def jaccard_est(a: bytes, b: bytes) -> float:
    return float(np.mean(np.frombuffer(a, dtype=np.uint32) == np.frombuffer(b, dtype=np.uint32)))


class NearDupIndex:
    """Streaming index: ``check(sig)`` returns (best_jaccard, idx_of_match) against everything added."""

    def __init__(self, max_per_key: int = 16):
        self.buckets: dict[int, list[int]] = {}
        self.sigs: list[bytes] = []
        self.max_per_key = max_per_key

    def check(self, sig: bytes) -> tuple[float, int]:
        best, best_i = 0.0, -1
        seen = set()
        for k in band_keys(sig):
            for i in self.buckets.get(k, ()):
                if i in seen:
                    continue
                seen.add(i)
                j = jaccard_est(sig, self.sigs[i])
                if j > best:
                    best, best_i = j, i
        return best, best_i

    def add(self, sig: bytes) -> int:
        i = len(self.sigs)
        self.sigs.append(sig)
        for k in band_keys(sig):
            lst = self.buckets.setdefault(k, [])
            if len(lst) < self.max_per_key:
                lst.append(i)
        return i
