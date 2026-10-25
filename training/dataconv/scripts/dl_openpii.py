"""Download only the English byte ranges of ai4privacy/pii-masking-openpii-1m train.jsonl.

The file is sorted by (language, region) (probed). We bisect byte offsets with HTTP range
requests to find the en-GB block, download it whole, and download a few evenly spaced
slices of the en-CA / en-IN / en-US (and any other en-*) blocks. Every row is re-filtered
by language/region at conversion time, so slightly loose boundaries are harmless.
"""
import json
import urllib.request
from pathlib import Path

REPO = "ai4privacy/pii-masking-openpii-1m"
REV = "ecfdc547f4a0955600cfe6ab98ba2a162207fcc0"
URL = f"https://huggingface.co/datasets/{REPO}/resolve/{REV}/data/train.jsonl"
SIZE = 3690456830
OUT = Path(__file__).resolve().parents[3] / "data" / "external" / "raw" / "ai4privacy__pii-masking-openpii-1m"


def fetch(a: int, b: int) -> bytes:
    req = urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b}"})
    return urllib.request.urlopen(req, timeout=120).read()


def key_at(off: int):
    data = fetch(off, off + 200_000)
    i = data.index(b"\n") + 1 if off > 0 else 0
    j = data.index(b"\n", i)
    r = json.loads(data[i:j])
    return (r["language"], r["region"])


def first_offset_ge(target, lo=0, hi=SIZE - 300_000, tol=1_000_000):
    """Smallest offset (within tol) whose row key >= target."""
    while hi - lo > tol:
        mid = (lo + hi) // 2
        if key_at(mid) >= target:
            hi = mid
        else:
            lo = mid
    return lo, hi


def main():
    bounds = {}
    for t in [("en", ""), ("en", "GB"), ("en", "H"), ("en", "IN"), ("en", "J"), ("en", "US"), ("en", "ZZ")]:
        bounds[t] = first_offset_ge(t)
        print(t, bounds[t], flush=True)
    slices = []
    gb = (bounds[("en", "GB")][0], bounds[("en", "H")][1])
    slices.append(("GB_full", gb[0], gb[1]))
    # other English regions: before GB (CA etc.), between GB and US (IN etc.), US
    others = [
        ("pre_GB", bounds[("en", "")][0], bounds[("en", "GB")][1]),
        ("GB_to_US", bounds[("en", "H")][0], bounds[("en", "US")][1]),
        ("US", bounds[("en", "US")][0], bounds[("en", "ZZ")][1]),
    ]
    piece = 4_000_000
    for name, a, b in others:
        for k in range(4):
            s = a + (b - a - piece) * k // 3
            slices.append((f"{name}_{k}", s, s + piece))
    manifest = {"repo": REPO, "revision": REV, "file": "data/train.jsonl", "file_size": SIZE,
                "bounds": {f"{k[0]}-{k[1]}": v for k, v in bounds.items()}, "slices": []}
    for name, a, b in slices:
        p = OUT / f"train_bytes_{name}_{a}_{b}.jsonl.part"
        if not p.exists():
            data = fetch(a, b)
            # trim to whole lines
            i = data.index(b"\n") + 1 if a > 0 else 0
            j = data.rindex(b"\n") + 1
            p.write_bytes(data[i:j])
        manifest["slices"].append({"name": name, "byte_start": a, "byte_end": b, "path": p.name})
        print("saved", p.name, p.stat().st_size, flush=True)
    (OUT / "download_manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
