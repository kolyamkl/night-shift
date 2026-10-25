"""Probe a large remote JSONL by byte offset (HTTP range) to find where a language block starts/ends."""
import json
import sys
import urllib.request

URL = sys.argv[1]
SIZE = int(sys.argv[2])


def probe(off: int, n: int = 200_000):
    req = urllib.request.Request(URL, headers={"Range": f"bytes={off}-{off + n}"})
    data = urllib.request.urlopen(req).read()
    i = data.index(b"\n") + 1 if off > 0 else 0
    j = data.index(b"\n", i)
    r = json.loads(data[i:j])
    return r["language"], r["region"], off + i


for k in range(0, 41):
    off = int(SIZE * k / 40)
    if off >= SIZE - 300_000:
        off = SIZE - 300_000
    print(k, off, probe(off)[:2], flush=True)
