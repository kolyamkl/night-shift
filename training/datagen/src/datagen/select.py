"""Curated Mubit round files.

All selections work on a light index of chunks (no text) and are deterministic for a seed.

* round 1 (train) and round 2 (fresh): quota-constrained *stochastic greedy coverage*. At each
  step we draw S random candidates and add the one with the largest marginal gain:
  doc-type quota pressure (balanced across doc types, hard cap 1.3x the even share)
  + entity-type coverage (rare types such as IBAN or ID_DOC gain more while they are under-represented)
  + hard-case coverage + template-variant novelty + length-bucket novelty
  + a negative-chunk term that steers negatives to about 15%.
  At most one chunk per document (one Mubit session = one document, and it maximises diversity),
  no two chunks with the same skeleton hash, and no two chunks whose MinHash-estimated Jaccard
  similarity is >= 0.7 (near-duplicate guard, checked through the LSH band buckets). Documents
  flagged as near duplicates at generation time (Jaccard >= 0.8 with an earlier document) are excluded.
* corrections: same greedy loop with a score that rewards CUSTOM ids and many distinct hard cases,
  doc-type cap 1.5x the even share, positives only.
* eval: whole documents (every chunk of a document, so leak rate per document is measurable),
  doc types taken round-robin until the chunk budget is filled.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from .dedup import band_keys, jaccard_est

SELECT_MAX_J = 0.7  # no two selected chunks may have estimated Jaccard >= this

LEN_BUCKETS = (200, 600, 1500, 3000, 10**9)


def _bucket(n: int) -> int:
    for i, b in enumerate(LEN_BUCKETS):
        if n < b:
            return i
    return len(LEN_BUCKETS) - 1


def greedy(pool: list[dict], n: int, rng: random.Random, *, mode: str = "round", neg_share: float = 0.15,
           samples: int = 192, cap_factor: float = 1.3) -> list[dict]:
    pool = [c for c in pool if not c.get("doc_neardup")]
    if mode == "corrections":
        pool = [c for c in pool if not c["neg"]]
    rng.shuffle(pool)
    dts = sorted({c["doc_type"] for c in pool})
    if not dts:
        return []
    avail = Counter(c["doc_type"] for c in pool)
    quota = water_fill(avail, n)
    target = {t: max(1.0, q) for t, q in quota.items()}
    cap = {t: min(avail[t], math.ceil(q * cap_factor)) for t, q in quota.items()}
    neg_target = n * neg_share
    cnt_dt, cnt_t, cnt_h, cnt_v, cnt_len = Counter(), Counter(), Counter(), Counter(), Counter()
    cnt_neg = 0
    used_docs, used_skel = set(), set()
    used_bands: dict[int, list[bytes]] = {}
    selected = []
    remaining = pool[:]
    bands = {id(c): band_keys(c["sig"]) if c.get("sig") else [] for c in pool}

    def usable(c) -> bool:
        return (c["doc_id"] not in used_docs and c["skel"] not in used_skel
                and not _too_similar(c, bands[id(c)], used_bands))

    def score(c) -> float:
        dt = c["doc_type"]
        if cnt_dt[dt] >= cap[dt]:
            return -1e9
        s = 2.0 * (1.0 - cnt_dt[dt] / target[dt])
        if c["types"]:
            gains = [1.0 / math.sqrt(1.0 + cnt_t[t]) for t in c["types"]]
            s += 8.0 * sum(gains) / len(gains) + 0.08 * len(c["types"])
        hk = c["hard"]
        if hk:
            s += 3.0 * sum(1.0 / math.sqrt(1.0 + cnt_h[k]) for k in hk) / len(hk) + 0.1 * len(hk)
        s += 1.0 / (1.0 + cnt_v[c["variant"]])
        s += 0.5 / (1.0 + cnt_len[_bucket(c["n"])] / (n / len(LEN_BUCKETS)))
        if mode == "corrections":
            s += 4.0 * ("CUSTOM" in c["types"]) + 0.6 * len(hk)
        elif c["neg"]:
            s += 3.0 if cnt_neg < neg_target else -4.0
        return s

    while len(selected) < n and remaining:
        best_i, best_s = -1, -1e18
        tries = 0
        for _ in range(samples):
            i = rng.randrange(len(remaining))
            c = remaining[i]
            if not usable(c):
                continue
            tries += 1
            sc = score(c)
            if sc > best_s:
                best_i, best_s = i, sc
        if best_i < 0 or best_s <= -1e8:
            # sampled only unusable candidates: purge them and retry
            remaining = [c for c in remaining if usable(c) and cnt_dt[c["doc_type"]] < cap[c["doc_type"]]]
            if not remaining:
                break
            continue
        c = remaining[best_i]
        remaining[best_i] = remaining[-1]
        remaining.pop()
        selected.append(c)
        used_docs.add(c["doc_id"])
        used_skel.add(c["skel"])
        for k in bands[id(c)]:
            used_bands.setdefault(k, []).append(c["sig"])
        cnt_dt[c["doc_type"]] += 1
        for t in c["types"]:
            cnt_t[t] += 1
        for k in c["hard"]:
            cnt_h[k] += 1
        cnt_v[c["variant"]] += 1
        cnt_len[_bucket(c["n"])] += 1
        cnt_neg += c["neg"]
    return selected


def _too_similar(c: dict, keys: list[int], used_bands: dict[int, list[bytes]]) -> bool:
    for k in keys:
        for sig in used_bands.get(k, ()):
            if jaccard_est(c["sig"], sig) >= SELECT_MAX_J:
                return True
    return False


def water_fill(avail: Counter, n: int) -> dict[str, float]:
    """Even share per doc type; a type with fewer candidates than its share gives the rest away."""
    quota = {}
    left = dict(avail)
    budget = float(min(n, sum(avail.values())))
    while left:
        share = budget / len(left)
        small = {t: a for t, a in left.items() if a <= share}
        if not small:
            for t in left:
                quota[t] = share
            break
        for t, a in small.items():
            quota[t] = float(a)
            budget -= a
            del left[t]
    return quota


def select_eval(pool: list[dict], n: int, rng: random.Random) -> list[dict]:
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for c in pool:
        if not c.get("doc_neardup"):
            by_doc[c["doc_id"]].append(c)
    by_type: dict[str, list[str]] = defaultdict(list)
    for d, cs in sorted(by_doc.items()):
        by_type[cs[0]["doc_type"]].append(d)
    for v in by_type.values():
        rng.shuffle(v)
    types = sorted(by_type)
    out: list[dict] = []
    ptr = {t: 0 for t in types}
    active = True
    while len(out) < n and active:
        active = False
        for t in types:
            lst = by_type[t]
            while ptr[t] < len(lst):
                cs = by_doc[lst[ptr[t]]]
                ptr[t] += 1
                if len(out) + len(cs) <= n:
                    out.extend(sorted(cs, key=lambda c: c["chunk_id"]))
                    active = True
                    break
            if len(out) >= n:
                break
    return out


def select_all(index: list[dict], seed: int, sizes: dict[str, int] | None = None) -> dict[str, list[dict]]:
    sizes = sizes or {"mubit_round1": 3000, "mubit_round2": 2000, "mubit_corrections": 200, "mubit_eval": 1500}
    by_split: dict[str, list[dict]] = defaultdict(list)
    for c in index:
        by_split[c["split"]].append(c)
    return {
        "mubit_round1": greedy(list(by_split["train"]), sizes["mubit_round1"], random.Random(f"{seed}:r1")),
        "mubit_round2": greedy(list(by_split["fresh"]), sizes["mubit_round2"], random.Random(f"{seed}:r2")),
        "mubit_corrections": greedy(list(by_split["corrections"]), sizes["mubit_corrections"],
                                    random.Random(f"{seed}:corr"), mode="corrections", cap_factor=1.5),
        "mubit_eval": select_eval(list(by_split["eval"]), sizes["mubit_eval"], random.Random(f"{seed}:eval")),
    }
