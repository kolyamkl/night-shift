"""bitext/Bitext-customer-support-llm-chatbot-training-dataset -> canonical (pool A). See bitext.py for the fill rules."""
from collections import Counter

from .bitext import DATASETS, convert_key

DATASET = {
    "id": DATASETS["cs"]["id"],
    "dir": "bitext__Bitext-customer-support-llm-chatbot-training-dataset",
    "short": "btxc",
    "license": "CDLA-Sharing-1.0",
    "pool": "A",
    "revision": DATASETS["cs"]["revision"],
}


def convert(stats: Counter):
    yield from convert_key("cs", stats)
