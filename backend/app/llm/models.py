"""The two model calls as the app sees them, built once at startup and injected into the services."""

from collections.abc import Callable
from dataclasses import dataclass

from ..domain.pipeline import T1Result
from .clients import make_t1_factory, make_t2
from .settings import T1_CHUNK_CHARS, Settings, find_key, load_settings

T1Factory = Callable[[str], Callable[[str], T1Result]]  # doc_id -> one T1 call per chunk
T2 = Callable[[str, str], tuple[str, str | None]]  # (question, redacted text) -> (answer, mreq_id)


@dataclass
class Models:
    t1_factory: T1Factory | None
    t2: T2 | None
    t1_prompt: str
    t1_model: str
    t2_model: str
    key_source: str | None  # "env", "backend/.env" or ".env"; never the key itself

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "Models":
        settings = settings or load_settings()
        key, source = find_key()
        return cls(make_t1_factory(key, settings.t1_prompt, settings.evalkit_model), make_t2(key, settings.t2_model),
                   settings.t1_prompt, settings.t1_model, settings.t2_model, source)

    @property
    def on(self) -> bool:
        return self.t1_factory is not None

    @property
    def chunk_chars(self) -> int:
        return T1_CHUNK_CHARS[self.t1_prompt]

    def health(self) -> dict:
        return {"model": "on" if self.on else "off", "t1_model": self.t1_model if self.on else None,
                "t1_prompt": self.t1_prompt, "t2_model": self.t2_model if self.t2 else None,
                "key_source": self.key_source if self.on else None}
