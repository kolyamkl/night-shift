"""bitext/Bitext-retail-banking-llm-chatbot-training-dataset -> canonical (pool A). See bitext.py for the fill rules."""
from collections import Counter

from .bitext import DATASETS, convert_key

DATASET = {
    "id": DATASETS["bank"]["id"],
    "dir": "bitext__Bitext-retail-banking-llm-chatbot-training-dataset",
    "short": "btxb",
    "license": "CDLA-Sharing-1.0",
    "pool": "A",
    "revision": DATASETS["bank"]["revision"],
}


def convert(stats: Counter):
    yield from convert_key("bank", stats)
