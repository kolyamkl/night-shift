"""Print repo info (sha, gated, files with sizes) and save the card for HF datasets."""
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

RAW = Path(__file__).resolve().parents[3] / "data" / "external" / "raw"
api = HfApi()
for rid in sys.argv[1:]:
    info = api.dataset_info(rid, files_metadata=True)
    print("=" * 80)
    print(rid, "sha", info.sha, "gated", info.gated, "private", info.private, "lastModified", info.last_modified)
    print("card license:", (info.card_data or {}).get("license") if info.card_data else None)
    for s in info.siblings:
        print(f"  {s.rfilename}  {s.size}")
    d = RAW / rid.replace("/", "__")
    d.mkdir(parents=True, exist_ok=True)
    if not info.gated:
        p = hf_hub_download(rid, "README.md", repo_type="dataset", revision=info.sha, local_dir=d)
        print("card saved", p)
