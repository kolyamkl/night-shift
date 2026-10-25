"""Document type registry.

Each generator is ``fn(rng: random.Random, neg: bool) -> Doc``. ``neg=True`` asks for a
document with no personal data at all (only registered with ``neg_weight > 0``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..core import Doc


@dataclass
class DocType:
    name: str
    fn: Callable
    weight: float       # share among positive documents
    neg_weight: float   # share among negative documents (0 = cannot be negative)
    short: bool = False  # short message type (prompt, chat, sms)


REGISTRY: dict[str, DocType] = {}


def register(name: str, weight: float, neg_weight: float = 0.0, short: bool = False):
    def deco(fn):
        REGISTRY[name] = DocType(name, fn, weight, neg_weight, short)
        return fn
    return deco


def load_all() -> dict[str, DocType]:
    # import modules for their side effect of registering generators
    from . import prompts, finance, contracts, letters, people_docs, messages  # noqa: F401
    return REGISTRY
